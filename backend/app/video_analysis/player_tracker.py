from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from app.video_analysis.detectors import RawDetection
from app.video_analysis.tracking_schemas import PlayerTrackObservation, TrackingState


@dataclass(frozen=True)
class ByteTrackConfig:
    """Explicit, frozen configuration for Player ByteTrack baseline."""

    track_activation_threshold: float = 0.45  # Matches locked canonical person threshold
    low_confidence_threshold: float = 0.10    # Low-confidence threshold for ByteTrack 2nd stage association
    lost_track_buffer: int = 30               # Retain lost tracks for ~1s at 30 fps (or 25 frames at 25 fps)
    minimum_matching_threshold: float = 0.8   # Standard ByteTrack IoU association threshold
    frame_rate: float = 30.0                  # FPS of input sequence
    minimum_consecutive_frames: int = 1       # Confirmation age in consecutive frames
    version: str = "1.1.0"


def filter_detections_for_tracking(
    detections: list[RawDetection],
    *,
    person_min_confidence: float = 0.10,
    ball_min_confidence: float = 0.25,
) -> list[RawDetection]:
    """
    Tracking-specific detection adapter:
    - Exposes person detections with confidence > 0.10 for ByteTrack's 2-stage association.
    - Exposes ball detections with confidence >= 0.25 for BallTrackManager.
    """
    return [
        d
        for d in detections
        if (d.class_name == "person" and d.confidence > person_min_confidence)
        or (d.class_name in ("sports ball", "ball") and d.confidence >= ball_min_confidence)
    ]


class PlayerByteTrack:
    """
    Player tracking baseline using ByteTrack on person detections.
    Treats player tracking strictly independently from ball tracking.
    Preserves original detector confidence values and maintains persistent IDs across occlusions.
    """

    def __init__(self, config: ByteTrackConfig | None = None) -> None:
        self.config = config or ByteTrackConfig()
        try:
            import supervision as sv
        except ImportError as exc:
            raise RuntimeError(
                "Le tracker bytetrack exige le paquet supervision. "
                "Installez backend/requirements-video.txt."
            ) from exc

        self._sv = sv
        self._supervision_version = getattr(sv, "__version__", "unknown")
        self.reset()

    def reset(self) -> None:
        """Resets tracker internal state and track ID counter."""
        self._tracker = self._sv.ByteTrack(
            track_activation_threshold=self.config.track_activation_threshold,
            lost_track_buffer=self.config.lost_track_buffer,
            minimum_matching_threshold=self.config.minimum_matching_threshold,
            frame_rate=self.config.frame_rate,
            minimum_consecutive_frames=self.config.minimum_consecutive_frames,
        )

    def update_tracks(
        self,
        frame_index: int,
        timestamp: float,
        detections: list[RawDetection],
        source_detector: str = "rf-detr-small",
        frame_image: np.ndarray | None = None,
    ) -> list[PlayerTrackObservation]:
        """
        Updates player tracks from raw detections.
        Filters strictly for class_name == 'person' and confidence > low_confidence_threshold.
        Preserves original detector confidences.
        """
        person_indices = [
            i
            for i, d in enumerate(detections)
            if d.class_name == "person" and d.confidence > self.config.low_confidence_threshold
        ]
        if not person_indices:
            # Still invoke tracker with empty detections to advance lost-track buffers
            empty_sv = self._sv.Detections.empty()
            self._tracker.update_with_detections(empty_sv)
            return []

        boxes = np.array([detections[i].bbox for i in person_indices], dtype=float)
        confs = np.array([detections[i].confidence for i in person_indices], dtype=float)
        class_ids = np.ones(len(person_indices), dtype=int)

        sv_detections = self._sv.Detections(
            xyxy=boxes,
            confidence=confs,
            class_id=class_ids,
            data={"source_index": np.array(person_indices)},
        )

        tracked = self._tracker.update_with_detections(sv_detections)
        tracker_ids = tracked.tracker_id if tracked.tracker_id is not None else []
        source_indices = tracked.data.get("source_index", [])

        observations: list[PlayerTrackObservation] = []
        for source_idx, track_id in zip(source_indices, tracker_ids):
            idx = int(source_idx)
            raw = detections[idx]
            obs = PlayerTrackObservation(
                track_id=int(track_id),
                frame_index=frame_index,
                timestamp=timestamp,
                bbox=(float(raw.bbox[0]), float(raw.bbox[1]), float(raw.bbox[2]), float(raw.bbox[3])),
                confidence=float(raw.confidence),
                class_id=1,
                class_name="person",
                source_detector=source_detector,
                tracking_state=TrackingState.CONFIRMED,
            )
            observations.append(obs)

        return observations

    def metadata(self) -> dict[str, Any]:
        """Returns complete, frozen provenance and parameters."""
        data = asdict(self.config)
        data.update({
            "name": "bytetrack_player",
            "supervision_version": self._supervision_version,
            "target_class": "person",
        })
        return data


@dataclass(frozen=True)
class BoTSORTConfig:
    """Explicit, frozen configuration for Player BoT-SORT challenger."""

    track_high_thresh: float = 0.45       # Matches high confidence person activation threshold
    track_low_thresh: float = 0.10        # Low-confidence threshold for BoT-SORT 2nd stage association
    new_track_thresh: float = 0.45        # Confirm new track threshold
    track_buffer: int = 30                # Frames to keep lost tracks alive (~1.2s at 25 fps)
    match_thresh: float = 0.8             # IoU matching threshold
    fuse_score: bool = True               # Fuse detection score with motion/IoU for matching
    gmc_method: str = "sparseOptFlow"     # Camera motion compensation: sparseOptFlow|none
    proximity_thresh: float = 0.5         # Min IoU to consider tracks proximate
    appearance_thresh: float = 0.8        # Min appearance similarity
    with_reid: bool = False               # Strictly disabled (EXP-08)
    model: str = "none"                   # No appearance encoder model
    frame_rate: float = 25.0              # FPS of input sequence
    version: str = "1.0.0"


class PlayerBoTSORT:
    """
    Player tracking challenger using BoT-SORT without appearance ReID.
    Treats player tracking strictly independently from ball tracking.
    Uses motion association with Camera Motion Compensation (GMC).
    Preserves original detector confidences.
    """

    def __init__(self, config: BoTSORTConfig | None = None) -> None:
        self.config = config or BoTSORTConfig()
        try:
            from ultralytics.trackers.bot_sort import BOTSORT
            from ultralytics.engine.results import Boxes
        except ImportError as exc:
            raise RuntimeError(
                "Le tracker BoT-SORT exige le paquet ultralytics. "
                "Installez backend/requirements-training.txt."
            ) from exc

        self._bot_sort_cls = BOTSORT
        self._boxes_cls = Boxes
        self.reset()

    def reset(self) -> None:
        """Resets tracker internal state and track ID counter."""
        import types

        args = types.SimpleNamespace(
            tracker_type="botsort",
            track_high_thresh=self.config.track_high_thresh,
            track_low_thresh=self.config.track_low_thresh,
            new_track_thresh=self.config.new_track_thresh,
            track_buffer=self.config.track_buffer,
            match_thresh=self.config.match_thresh,
            fuse_score=self.config.fuse_score,
            gmc_method=self.config.gmc_method,
            proximity_thresh=self.config.proximity_thresh,
            appearance_thresh=self.config.appearance_thresh,
            with_reid=self.config.with_reid,
            model=self.config.model,
            frame_rate=self.config.frame_rate,
        )
        self._last_gmc_time_ms: float = 0.0
        self._tracker = self._bot_sort_cls(args)
        if hasattr(self._tracker, "gmc") and hasattr(self._tracker.gmc, "apply"):
            orig_apply = self._tracker.gmc.apply

            def timed_apply(*a: Any, **kw: Any) -> Any:
                import time
                t0 = time.perf_counter()
                res = orig_apply(*a, **kw)
                self._last_gmc_time_ms = (time.perf_counter() - t0) * 1000.0
                return res

            self._tracker.gmc.apply = timed_apply

    @property
    def last_gmc_time_ms(self) -> float:
        """Returns execution time of optical flow GMC on most recent update in ms."""
        return self._last_gmc_time_ms

    def update_tracks(
        self,
        frame_index: int,
        timestamp: float,
        detections: list[RawDetection],
        source_detector: str = "rf-detr-small",
        frame_image: np.ndarray | None = None,
    ) -> list[PlayerTrackObservation]:
        """
        Updates player tracks from raw detections.
        Filters strictly for class_name == 'person' and confidence > track_low_thresh.
        Preserves original detector confidences.
        """
        self._last_gmc_time_ms = 0.0
        person_detections = [
            d
            for d in detections
            if d.class_name == "person" and d.confidence > self.config.track_low_thresh
        ]
        if not person_detections:
            import torch

            empty_boxes = self._boxes_cls(
                torch.zeros((0, 6), dtype=torch.float32), orig_shape=(1080, 1920)
            )
            self._tracker.update(empty_boxes, img=frame_image)
            return []

        import torch

        boxes_tensor = torch.tensor(
            [[*d.bbox, d.confidence, 0] for d in person_detections],
            dtype=torch.float32,
        )
        boxes = self._boxes_cls(boxes_tensor, orig_shape=(1080, 1920))

        tracked_output = self._tracker.update(boxes, img=frame_image)
        if len(tracked_output) == 0:
            return []

        observations: list[PlayerTrackObservation] = []
        for row in tracked_output:
            track_id = int(row[4])
            conf = float(row[5])
            bbox = (float(row[0]), float(row[1]), float(row[2]), float(row[3]))
            det_idx = int(row[7]) if len(row) > 7 else -1
            if 0 <= det_idx < len(person_detections):
                raw_det = person_detections[det_idx]
                conf = float(raw_det.confidence)

            obs = PlayerTrackObservation(
                track_id=track_id,
                frame_index=frame_index,
                timestamp=timestamp,
                bbox=bbox,
                confidence=conf,
                class_id=1,
                class_name="person",
                source_detector=source_detector,
                tracking_state=TrackingState.CONFIRMED,
            )
            observations.append(obs)

        return observations

    def metadata(self) -> dict[str, Any]:
        """Returns complete, frozen provenance and parameters."""
        data = asdict(self.config)
        data.update({
            "name": "botsort_player_no_reid",
            "target_class": "person",
            "camera_motion_compensation": self.config.gmc_method,
            "reid_enabled": False,
        })
        return data


# ==============================================================================
# CHAPTER 5 ARCHITECTURAL DECISION: PRODUCTION PLAYER TRACKER
# ==============================================================================
# Following EXP-08 controlled benchmark across 6 SoccerNet Tracking sequences
# (4,500 frames), BoT-SORT with Camera Motion Compensation (sparseOptFlow GMC)
# without appearance ReID decisively outperformed ByteTrack:
#   - HOTA: 0.7465 -> 0.7708 (+0.0243)
#   - AssA: 0.6224 -> 0.6578 (+0.0354)
#   - IDF1: 0.7232 -> 0.7528 (+0.0296)
#   - ID Switches: 82.2 -> 64.8 per sequence (-21.1%)
#
# Therefore, PlayerBoTSORT (gmc_method="sparseOptFlow", with_reid=False) is
# locked as the default Chapter 5 player tracker.
#
# ByteTrack (PlayerByteTrack) is preserved in full as:
#   1. Historical baseline (EXP-05)
#   2. High-throughput fallback (570+ FPS)
#   3. Regression reference
# ==============================================================================

DEFAULT_PLAYER_TRACKER_TYPE: str = "botsort"


def create_player_tracker(
    tracker_type: str = DEFAULT_PLAYER_TRACKER_TYPE,
    *,
    fps: float = 25.0,
    gmc_method: str = "sparseOptFlow",
    track_buffer: int = 30,
) -> PlayerBoTSORT | PlayerByteTrack:
    """
    Factory function for Chapter 5 player tracking.
    Defaults to locked production tracker: PlayerBoTSORT + sparseOptFlow GMC.
    Supports 'bytetrack' as historical reference and ultra-fast fallback.
    """
    normalized = tracker_type.strip().lower()
    if normalized in ("botsort", "botsort_player", "default"):
        config = BoTSORTConfig(
            frame_rate=fps,
            gmc_method=gmc_method,
            track_buffer=track_buffer,
            with_reid=False,
            model="none",
        )
        return PlayerBoTSORT(config=config)
    elif normalized in ("bytetrack", "bytetrack_player"):
        bt_config = ByteTrackConfig(
            frame_rate=fps,
            lost_track_buffer=track_buffer,
        )
        return PlayerByteTrack(config=bt_config)
    else:
        raise ValueError(
            f"Unknown player tracker type '{tracker_type}'. "
            f"Supported: 'botsort' (default production), 'bytetrack' (fallback)."
        )
