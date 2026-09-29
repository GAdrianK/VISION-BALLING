import numpy as np
import pytest

from app.video_analysis.ball_tracker import BallTrackManager, create_ball_track_config_v2
from app.video_analysis.detectors import ObjectDetector, RawDetection
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
    FrameTrackingResult,
    FrameTrackingRuntime,
    PlayerTrackObservation,
    TrackingState,
)
from app.video_analysis.unified_pipeline import PipelineProfileStats, UnifiedTrackingPipeline


class SpyDetector(ObjectDetector):
    """Mock detector to inspect call counts and simulate detections."""

    def __init__(self, detections_by_frame: dict[int, list[RawDetection]] | None = None) -> None:
        self.detections_by_frame = detections_by_frame or {}
        self.detect_call_count = 0
        self.loaded = False

    def load(self) -> None:
        self.loaded = True

    def detect(self, frame: np.ndarray, **kwargs) -> list[RawDetection]:
        self.detect_call_count += 1
        return []

    def detect_for_tracking_with_timings(
        self,
        frame: np.ndarray,
        *,
        person_min_confidence: float = 0.10,
        ball_min_confidence: float = 0.25,
    ) -> tuple[list[RawDetection], dict[str, float]]:
        self.detect_call_count += 1
        dets = self.detections_by_frame.get(self.detect_call_count, [])
        filtered = [
            d for d in dets
            if (d.class_name == "person" and d.confidence > person_min_confidence)
            or (d.class_name in ("sports ball", "ball") and d.confidence >= ball_min_confidence)
        ]
        timings = {
            "preprocess_ms": 0.5,
            "inference_ms": 15.0,
            "postprocess_ms": 1.0,
            "total_detector_ms": 16.5,
        }
        return filtered, timings

    def metadata(self) -> dict:
        return {"model_id": "spy-rf-detr-small"}


def test_pipeline_default_tracker_is_botsort():
    """Phase 1: PlayerBoTSORT + GMC is wired by default, strictly without ReID."""
    assert DEFAULT_PLAYER_TRACKER_TYPE == "botsort"

    detector = SpyDetector()
    pipeline = UnifiedTrackingPipeline(detector=detector, fps=25.0)

    assert isinstance(pipeline.player_tracker, PlayerBoTSORT)
    assert pipeline.player_tracker.config.gmc_method == "sparseOptFlow"
    assert pipeline.player_tracker.config.with_reid is False
    assert pipeline.player_tracker.config.model == "none"


def test_pipeline_bytetrack_remains_available():
    """Phase 1: ByteTrack remains available as fallback/reference."""
    detector = SpyDetector()
    bt = create_player_tracker("bytetrack", fps=25.0)
    assert isinstance(bt, PlayerByteTrack)

    pipeline = UnifiedTrackingPipeline(detector=detector, player_tracker=bt, fps=25.0)
    assert isinstance(pipeline.player_tracker, PlayerByteTrack)
    assert pipeline.player_tracker.config.track_activation_threshold == 0.45


def test_pipeline_ball_tracker_is_v2():
    """BallTrackManager V2 with bounded gating and lifecycle is wired by default."""
    detector = SpyDetector()
    pipeline = UnifiedTrackingPipeline(detector=detector, fps=25.0)

    assert isinstance(pipeline.ball_tracker, BallTrackManager)
    assert pipeline.ball_tracker.config.enable_track_lifecycle is True
    assert pipeline.ball_tracker.config.spatial_gate_max_radius == 500.0
    assert pipeline.ball_tracker.config.max_gap_interpolation == 0


def test_single_detector_inference_per_frame():
    """Phase 2: RF-DETR must run ONCE per frame; no separate detector runs for player and ball."""
    detector = SpyDetector()
    pipeline = UnifiedTrackingPipeline(detector=detector, fps=25.0)

    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    for f in range(1, 6):
        res, _ = pipeline.process_frame(frame, frame_index=f)

    assert detector.detect_call_count == 5


def test_class_separation_and_output_contract():
    """Phase 2 & 3: Proper class separation into person and ball, adhering to common output contract."""
    frame_dets = {
        1: [
            RawDetection(class_name="person", football_role="player_candidate", confidence=0.88, bbox=(10, 10, 30, 60)),
            RawDetection(class_name="sports ball", football_role="ball_candidate", confidence=0.75, bbox=(50, 50, 60, 60)),
        ]
    }
    detector = SpyDetector(detections_by_frame=frame_dets)
    pipeline = UnifiedTrackingPipeline(detector=detector, fps=25.0)

    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    res, _ = pipeline.process_frame(frame, frame_index=1)

    assert isinstance(res, FrameTrackingResult)
    assert res.frame_index == 1
    assert res.timestamp == 0.0
    assert len(res.players) == 1
    assert res.players[0].confidence == 0.88
    assert res.players[0].tracking_state == TrackingState.CONFIRMED

    assert res.ball is not None
    assert res.ball.observation_state == BallObservationState.DETECTED
    assert res.ball.confidence == 0.75

    # Check common output dictionary schema
    d = res.to_dict()
    assert "frame_index" in d
    assert "timestamp" in d
    assert "players" in d
    assert "ball" in d
    assert "runtime" in d
    assert d["runtime"]["detector_ms"] > 0
    assert d["runtime"]["player_tracking_ms"] >= 0
    assert d["runtime"]["ball_tracking_ms"] >= 0
    assert "team" not in d["players"][0]
    assert "jersey" not in d["players"][0]
    assert "pitch_coord" not in d["players"][0]


def test_strict_state_reset_between_sequences():
    """Phase 4: No track IDs or motion state leak between videos."""
    frame_dets = {
        1: [
            RawDetection(class_name="person", football_role="player_candidate", confidence=0.9, bbox=(10, 10, 30, 60)),
            RawDetection(class_name="sports ball", football_role="ball_candidate", confidence=0.8, bbox=(50, 50, 60, 60)),
        ],
        2: [
            RawDetection(class_name="person", football_role="player_candidate", confidence=0.9, bbox=(12, 12, 32, 62)),
            RawDetection(class_name="sports ball", football_role="ball_candidate", confidence=0.8, bbox=(52, 52, 62, 62)),
        ],
    }
    detector1 = SpyDetector(detections_by_frame=frame_dets)
    pipeline = UnifiedTrackingPipeline(detector=detector1, fps=25.0)

    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    # Run sequence 1
    res1_1, _ = pipeline.process_frame(frame, frame_index=1)
    res1_2, _ = pipeline.process_frame(frame, frame_index=2)

    # Reset
    pipeline.reset()
    detector1.detect_call_count = 0

    # Run sequence 2 (fresh state)
    res2_1, _ = pipeline.process_frame(frame, frame_index=1)

    # Player and ball should start with identical initial IDs as fresh run
    assert res1_1.players[0].track_id == res2_1.players[0].track_id
    assert res1_1.ball.track_id == res2_1.ball.track_id
    assert pipeline.ball_tracker.total_spawned_tracks == 1


def test_rendering_does_not_affect_tracking_outputs():
    """Debug rendering in MODE_B does not alter numerical tracking predictions."""
    frame_dets = {
        1: [
            RawDetection(class_name="person", football_role="player_candidate", confidence=0.9, bbox=(10, 10, 30, 60)),
            RawDetection(class_name="sports ball", football_role="ball_candidate", confidence=0.8, bbox=(50, 50, 60, 60)),
        ]
    }
    detector = SpyDetector(detections_by_frame=frame_dets)
    pipeline = UnifiedTrackingPipeline(detector=detector, fps=25.0)

    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    # Run without rendering
    res_no_render, img_no_render = pipeline.process_frame(frame, frame_index=1, render=False)
    assert img_no_render is None

    pipeline.reset()
    detector.detect_call_count = 0

    # Run with rendering
    res_with_render, img_with_render = pipeline.process_frame(frame, frame_index=1, render=True)
    assert img_with_render is not None

    assert res_no_render.players[0].track_id == res_with_render.players[0].track_id
    assert res_no_render.players[0].bbox == res_with_render.players[0].bbox
    assert res_no_render.ball.position == res_with_render.ball.position
    assert res_no_render.ball.track_id == res_with_render.ball.track_id


def test_timestamps_preserved():
    """Timestamps are strictly computed from source fps without drift."""
    detector = SpyDetector()
    pipeline = UnifiedTrackingPipeline(detector=detector, fps=25.0)

    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    for f in (1, 26, 51):
        res, _ = pipeline.process_frame(frame, frame_index=f)
        expected_ts = (f - 1) / 25.0
        assert res.timestamp == pytest.approx(expected_ts, abs=1e-5)


def test_pipeline_profile_stats():
    """PipelineProfileStats correctly computes percentiles and mean."""
    series = [10.0, 20.0, 30.0, 40.0, 50.0]
    stats = PipelineProfileStats.from_series(series)
    assert stats.mean_ms == 30.0
    assert stats.median_ms == 30.0
    assert stats.min_ms == 10.0
    assert stats.max_ms == 50.0
    assert stats.p95_ms > 45.0
