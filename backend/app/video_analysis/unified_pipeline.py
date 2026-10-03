from __future__ import annotations

import collections
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

import cv2
import numpy as np

from app.video_analysis.ball_tracker import BallTrackConfig, BallTrackManager, create_ball_track_config_v2
from app.video_analysis.detectors import ObjectDetector, RFDETRDetector, RawDetection
from app.video_analysis.player_tracker import (
    DEFAULT_PLAYER_TRACKER_TYPE,
    BoTSORTConfig,
    ByteTrackConfig,
    PlayerBoTSORT,
    PlayerByteTrack,
    create_player_tracker,
)
from app.video_analysis.tracking_schemas import (
    BallObservationState,
    BallTrackObservation,
    FrameTrackingResult,
    FrameTrackingRuntime,
    PlayerTrackObservation,
    TrackingState,
)
from app.video_analysis.tracking_visualizer import visualize_frame_tracks

logger = logging.getLogger("football.unified_tracking_pipeline")


@dataclass(frozen=True)
class PipelineProfileStats:
    """Statistical summary (mean, median, P90, P95, min, max) for latency."""

    mean_ms: float
    median_ms: float
    p90_ms: float
    p95_ms: float
    min_ms: float
    max_ms: float

    @classmethod
    def from_series(cls, series: Sequence[float]) -> PipelineProfileStats:
        if not series:
            return cls(0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        arr = np.array(series, dtype=float)
        return cls(
            mean_ms=round(float(np.mean(arr)), 3),
            median_ms=round(float(np.median(arr)), 3),
            p90_ms=round(float(np.percentile(arr, 90)), 3),
            p95_ms=round(float(np.percentile(arr, 95)), 3),
            min_ms=round(float(np.min(arr)), 3),
            max_ms=round(float(np.max(arr)), 3),
        )

    def to_dict(self) -> dict[str, float]:
        return {
            "mean_ms": self.mean_ms,
            "median_ms": self.median_ms,
            "p90_ms": self.p90_ms,
            "p95_ms": self.p95_ms,
            "min_ms": self.min_ms,
            "max_ms": self.max_ms,
        }


@dataclass
class SequenceBenchmarkReport:
    """Full execution summary of the unified tracking pipeline on a sequence."""

    sequence_name: str
    total_frames: int
    fps: float
    duration_seconds: float
    mode: str  # "MODE_A" (core) or "MODE_B" (debug_video)
    effective_fps: float
    total_latency_stats: PipelineProfileStats
    per_stage_stats: dict[str, PipelineProfileStats]
    player_summary: dict[str, Any]
    ball_summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence_name": self.sequence_name,
            "total_frames": self.total_frames,
            "fps": self.fps,
            "duration_seconds": round(self.duration_seconds, 3),
            "mode": self.mode,
            "effective_fps": round(self.effective_fps, 2),
            "total_latency_stats": self.total_latency_stats.to_dict(),
            "per_stage_stats": {k: v.to_dict() for k, v in self.per_stage_stats.items()},
            "player_summary": self.player_summary,
            "ball_summary": self.ball_summary,
        }


class UnifiedTrackingPipeline:
    """
    Unified VISION-BALLING Tracking Pipeline (Chapter 5 Production Standard).

    Single RF-DETR inference per frame, followed by semantic class separation:
      - person detections -> PlayerBoTSORT + GMC (sparseOptFlow)
      - ball detections   -> BallTrackManager V2 (Lifecycle + bounded gate)
    Produces a single FrameTrackingResult per frame with full provenance and latency instrumentation.
    """

    def __init__(
        self,
        detector: ObjectDetector,
        player_tracker: PlayerBoTSORT | PlayerByteTrack | None = None,
        ball_tracker: BallTrackManager | None = None,
        *,
        fps: float = 25.0,
        person_min_confidence: float = 0.10,
        ball_min_confidence: float = 0.25,
        ball_trail_length: int = 15,
    ) -> None:
        self.detector = detector
        self.fps = fps
        self.person_min_confidence = person_min_confidence
        self.ball_min_confidence = ball_min_confidence
        self.ball_trail_length = ball_trail_length

        if player_tracker is not None:
            self.player_tracker = player_tracker
        else:
            self.player_tracker = create_player_tracker(
                DEFAULT_PLAYER_TRACKER_TYPE,
                fps=fps,
                gmc_method="sparseOptFlow",
            )

        if ball_tracker is not None:
            self.ball_tracker = ball_tracker
        else:
            v2_cfg = create_ball_track_config_v2(fps=fps)
            self.ball_tracker = BallTrackManager(config=v2_cfg)

        self._ball_trail: collections.deque[BallTrackObservation] = collections.deque(
            maxlen=ball_trail_length
        )
        self._frame_count: int = 0
        self.reset()

    def reset(self) -> None:
        """
        Guarantees strict state isolation between videos/sequences.
        Resets player tracker (clearing Kalman filters and GMC state)
        and ball tracker (clearing history, gap counts, and lifecycle IDs).
        """
        self.player_tracker.reset()
        self.ball_tracker.reset()
        self._ball_trail.clear()
        self._frame_count = 0

    def process_frame(
        self,
        frame: np.ndarray,
        frame_index: int,
        timestamp: float | None = None,
        *,
        render: bool = False,
        encode_writer: cv2.VideoWriter | None = None,
        decode_ms: float = 0.0,
    ) -> tuple[FrameTrackingResult, np.ndarray | None]:
        """
        Processes a single video frame end-to-end:
          1. Single RF-DETR inference with tracking floors (0.10 person / 0.25 ball)
          2. Class separation
          3. PlayerBoTSORT update (with GMC on frame)
          4. BallTrackManager V2 update
          5. Optional debug rendering & optional video encoding
          6. Packaging FrameTrackingResult
        """
        t_frame_start = time.perf_counter()
        eff_timestamp = (frame_index - 1) / self.fps if timestamp is None else timestamp
        self._frame_count += 1

        # 1. Detector inference (single call)
        preprocess_ms = 0.0
        infer_ms = 0.0
        postprocess_ms = 0.0
        t_det_start = time.perf_counter()

        if hasattr(self.detector, "detect_for_tracking_with_timings"):
            raw_detections, det_timings = self.detector.detect_for_tracking_with_timings(
                frame,
                person_min_confidence=self.person_min_confidence,
                ball_min_confidence=self.ball_min_confidence,
            )
            preprocess_ms = det_timings.get("preprocess_ms", 0.0)
            infer_ms = det_timings.get("inference_ms", 0.0)
            postprocess_ms = det_timings.get("postprocess_ms", 0.0)
            detector_ms = det_timings.get("total_detector_ms", (time.perf_counter() - t_det_start) * 1000.0)
        elif hasattr(self.detector, "detect_for_tracking"):
            raw_detections = self.detector.detect_for_tracking(
                frame,
                person_min_confidence=self.person_min_confidence,
                ball_min_confidence=self.ball_min_confidence,
            )
            detector_ms = (time.perf_counter() - t_det_start) * 1000.0
        else:
            raw_detections = self.detector.detect(frame)
            detector_ms = (time.perf_counter() - t_det_start) * 1000.0

        # 2. Class separation (person vs ball)
        person_detections = [d for d in raw_detections if d.class_name == "person"]
        ball_detections = [d for d in raw_detections if d.class_name in ("sports ball", "ball")]

        # 3. Player tracker update
        t_pt_start = time.perf_counter()
        player_tracks = self.player_tracker.update_tracks(
            frame_index=frame_index,
            timestamp=eff_timestamp,
            detections=person_detections,
            frame_image=frame,
        )
        player_tracking_ms = (time.perf_counter() - t_pt_start) * 1000.0
        gmc_ms = getattr(self.player_tracker, "last_gmc_time_ms", 0.0)

        # 4. Ball tracker update
        t_bt_start = time.perf_counter()
        ball_obs = self.ball_tracker.update(
            frame_index=frame_index,
            timestamp=eff_timestamp,
            detections=ball_detections,
        )
        ball_tracking_ms = (time.perf_counter() - t_bt_start) * 1000.0
        if ball_obs is not None:
            self._ball_trail.append(ball_obs)

        # 5. Optional debug rendering
        annotated_frame: np.ndarray | None = None
        rendering_ms = 0.0
        if render:
            t_rend_start = time.perf_counter()
            annotated_frame = visualize_frame_tracks(
                frame,
                players=player_tracks,
                ball=ball_obs,
                ball_trail=list(self._ball_trail),
            )
            rendering_ms = (time.perf_counter() - t_rend_start) * 1000.0

        # 6. Optional encoding
        encoding_ms = 0.0
        if encode_writer is not None and annotated_frame is not None:
            t_enc_start = time.perf_counter()
            encode_writer.write(annotated_frame)
            encoding_ms = (time.perf_counter() - t_enc_start) * 1000.0

        # 7. Packaging FrameTrackingResult
        t_out_start = time.perf_counter()
        total_frame_ms = (time.perf_counter() - t_frame_start) * 1000.0 + decode_ms
        output_ms = (time.perf_counter() - t_out_start) * 1000.0

        runtime = FrameTrackingRuntime(
            decode_ms=decode_ms,
            preprocess_ms=preprocess_ms,
            detector_inference_ms=infer_ms,
            detector_postprocess_ms=postprocess_ms,
            detector_ms=detector_ms,
            gmc_ms=gmc_ms,
            player_tracking_ms=player_tracking_ms,
            ball_tracking_ms=ball_tracking_ms,
            rendering_ms=rendering_ms,
            encoding_ms=encoding_ms,
            output_ms=output_ms,
            total_ms=total_frame_ms,
        )

        result = FrameTrackingResult(
            frame_index=frame_index,
            timestamp=eff_timestamp,
            players=player_tracks,
            ball=ball_obs,
            runtime=runtime,
        )
        return result, annotated_frame

    def process_sequence(
        self,
        frames_source: Sequence[Path | str] | Path | str,
        *,
        sequence_name: str = "unnamed_sequence",
        mode: str = "MODE_A",  # "MODE_A" = Core Analysis, "MODE_B" = Debug Video
        output_video_path: Path | str | None = None,
        max_frames: int | None = None,
        progress_cb: Callable[[int, int], None] | None = None,
    ) -> tuple[list[FrameTrackingResult], SequenceBenchmarkReport]:
        """
        Executes the unified tracking pipeline over an entire sequence.
        Strictly calls reset() before processing to ensure zero state leakage.
        Supports MODE_A (core benchmarking) and MODE_B (debug video rendering & encoding).
        """
        self.reset()
        is_mode_b = mode.upper() in ("MODE_B", "DEBUG", "DEBUG_VIDEO")
        render_enabled = is_mode_b

        # Resolve frame list or video capture
        frame_files: list[Path] = []
        is_video_file = False
        cap: cv2.VideoCapture | None = None

        if isinstance(frames_source, (Path, str)):
            p = Path(frames_source)
            if p.is_dir():
                # Directory of image frames (e.g. img1/)
                frame_files = sorted(
                    [f for f in p.iterdir() if f.suffix.lower() in (".jpg", ".jpeg", ".png")]
                )
            elif p.is_file():
                # Video file
                is_video_file = True
                cap = cv2.VideoCapture(str(p))
                if not cap.isOpened():
                    raise RuntimeError(f"Failed to open video file: {p}")
            else:
                raise FileNotFoundError(f"Source not found: {frames_source}")
        else:
            frame_files = [Path(f) for f in frames_source]

        total_frames = len(frame_files) if not is_video_file else int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if max_frames is not None:
            total_frames = min(total_frames, max_frames)

        # Video writer setup for MODE_B
        writer: cv2.VideoWriter | None = None
        if is_mode_b and output_video_path is not None:
            out_p = Path(output_video_path)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            # Width/height will be determined on first frame
            writer_target_path = str(out_p)
        else:
            writer_target_path = None

        results: list[FrameTrackingResult] = []
        timing_records: dict[str, list[float]] = {
            "decode_ms": [],
            "preprocess_ms": [],
            "detector_inference_ms": [],
            "detector_postprocess_ms": [],
            "detector_ms": [],
            "gmc_ms": [],
            "player_tracking_ms": [],
            "ball_tracking_ms": [],
            "rendering_ms": [],
            "encoding_ms": [],
            "total_ms": [],
        }

        seq_t0 = time.perf_counter()

        try:
            for f_idx in range(1, total_frames + 1):
                # Frame decode timing
                t_dec_0 = time.perf_counter()
                if is_video_file:
                    assert cap is not None
                    ok, frame = cap.read()
                    if not ok:
                        break
                else:
                    im_path = frame_files[f_idx - 1]
                    frame = cv2.imread(str(im_path))
                    if frame is None:
                        raise RuntimeError(f"Failed to read image frame: {im_path}")
                decode_ms = (time.perf_counter() - t_dec_0) * 1000.0

                # Initialize writer on first frame if MODE_B
                if writer is None and writer_target_path is not None:
                    h, w = frame.shape[:2]
                    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                    writer = cv2.VideoWriter(writer_target_path, fourcc, self.fps, (w, h))

                # Process single frame
                frame_res, _ = self.process_frame(
                    frame=frame,
                    frame_index=f_idx,
                    render=render_enabled,
                    encode_writer=writer,
                    decode_ms=decode_ms,
                )
                results.append(frame_res)

                # Record timings
                rt = frame_res.runtime
                timing_records["decode_ms"].append(rt.decode_ms)
                timing_records["preprocess_ms"].append(rt.preprocess_ms)
                timing_records["detector_inference_ms"].append(rt.detector_inference_ms)
                timing_records["detector_postprocess_ms"].append(rt.detector_postprocess_ms)
                timing_records["detector_ms"].append(rt.detector_ms)
                timing_records["gmc_ms"].append(rt.gmc_ms)
                timing_records["player_tracking_ms"].append(rt.player_tracking_ms)
                timing_records["ball_tracking_ms"].append(rt.ball_tracking_ms)
                timing_records["rendering_ms"].append(rt.rendering_ms)
                timing_records["encoding_ms"].append(rt.encoding_ms)
                timing_records["total_ms"].append(rt.total_ms)

                if progress_cb is not None:
                    progress_cb(f_idx, total_frames)

        finally:
            if cap is not None:
                cap.release()
            if writer is not None:
                writer.release()

        seq_elapsed = time.perf_counter() - seq_t0
        actual_frames = len(results)
        effective_fps = actual_frames / seq_elapsed if seq_elapsed > 0 else 0.0

        # Summaries
        per_stage_stats = {
            k: PipelineProfileStats.from_series(v) for k, v in timing_records.items()
        }
        total_latency_stats = per_stage_stats["total_ms"]

        # Track statistics
        player_track_ids = {p.track_id for r in results for p in r.players}
        ball_obs_counts = collections.Counter(
            r.ball.observation_state.value for r in results if r.ball is not None
        )
        ball_track_ids = {r.ball.track_id for r in results if r.ball is not None and r.ball.track_id is not None}

        player_summary = {
            "unique_player_tracks": len(player_track_ids),
            "total_player_observations": sum(len(r.players) for r in results),
            "mean_players_per_frame": round(
                sum(len(r.players) for r in results) / actual_frames, 2
            )
            if actual_frames
            else 0.0,
        }
        ball_summary = {
            "unique_ball_tracks": len(ball_track_ids),
            "total_spawned_tracks": self.ball_tracker.total_spawned_tracks,
            "observation_states": dict(ball_obs_counts),
            "recovered_gaps_count": self.ball_tracker.recovered_gaps_count,
            "rejected_jump_count": self.ball_tracker.rejected_jump_count,
            "rejected_anchor_count": self.ball_tracker.rejected_anchor_count,
        }

        report = SequenceBenchmarkReport(
            sequence_name=sequence_name,
            total_frames=actual_frames,
            fps=self.fps,
            duration_seconds=seq_elapsed,
            mode="MODE_B" if is_mode_b else "MODE_A",
            effective_fps=effective_fps,
            total_latency_stats=total_latency_stats,
            per_stage_stats=per_stage_stats,
            player_summary=player_summary,
            ball_summary=ball_summary,
        )

        return results, report
