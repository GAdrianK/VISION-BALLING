"""
Unit tests for Chapter 5 EXP-08 Player BoT-SORT (without ReID).
Validates BoT-SORT adapter input mapping, player-only filtering,
preservation of detector confidence, explicit ReID disabling,
FPS propagation, tracker reset, and ByteTrack / BallTrackManager V2 immutability.
"""
from __future__ import annotations

import numpy as np
import pytest

from app.video_analysis.ball_tracker import BallTrackConfig, BallTrackManager, create_ball_track_config_v2
from app.video_analysis.detectors import RawDetection
from app.video_analysis.player_tracker import (
    BoTSORTConfig,
    ByteTrackConfig,
    PlayerBoTSORT,
    PlayerByteTrack,
)
from app.video_analysis.tracking_schemas import PlayerTrackObservation, TrackingState


def _make_det(bbox: tuple[float, float, float, float], cls_name: str = "person", conf: float = 0.85) -> RawDetection:
    return RawDetection(
        class_name=cls_name,
        football_role="player" if cls_name == "person" else "ball",
        confidence=conf,
        bbox=tuple(int(round(x)) for x in bbox),  # type: ignore[arg-type]
    )


def test_botsort_config_defaults():
    """BoTSORTConfig enforces explicit defaults with with_reid=False."""
    cfg = BoTSORTConfig()
    assert cfg.version == "1.0.0"
    assert cfg.track_high_thresh == 0.45
    assert cfg.track_low_thresh == 0.10
    assert cfg.new_track_thresh == 0.45
    assert cfg.track_buffer == 30
    assert cfg.match_thresh == 0.8
    assert cfg.fuse_score is True
    assert cfg.gmc_method == "sparseOptFlow"
    assert cfg.with_reid is False
    assert cfg.model == "none"


def test_botsort_reid_explicitly_disabled():
    """PlayerBoTSORT metadata and internal tracker guarantee with_reid=False."""
    tracker = PlayerBoTSORT(BoTSORTConfig(with_reid=False, gmc_method="none"))
    meta = tracker.metadata()
    assert meta["reid_enabled"] is False
    assert meta["with_reid"] is False
    assert tracker._tracker.args.with_reid is False


def test_botsort_player_only_filtering():
    """BoT-SORT filters strictly for person detections, rejecting ball detections."""
    tracker = PlayerBoTSORT(BoTSORTConfig(gmc_method="none"))
    dets = [
        _make_det((100.0, 100.0, 200.0, 200.0), cls_name="person", conf=0.88),
        _make_det((500.0, 500.0, 520.0, 520.0), cls_name="sports ball", conf=0.95),
        _make_det((300.0, 300.0, 400.0, 400.0), cls_name="ball", conf=0.80),
    ]
    tracks = tracker.update_tracks(frame_index=1, timestamp=0.0, detections=dets)
    assert len(tracks) == 1
    assert tracks[0].class_name == "person"
    assert tracks[0].track_id == 1


def test_botsort_confidence_preservation():
    """Preserves exact RF-DETR detector confidence on matched tracks."""
    tracker = PlayerBoTSORT(BoTSORTConfig(gmc_method="none"))
    dets = [_make_det((100.0, 100.0, 200.0, 200.0), cls_name="person", conf=0.8765)]
    tracks = tracker.update_tracks(frame_index=1, timestamp=0.0, detections=dets)
    assert len(tracks) == 1
    assert abs(tracks[0].confidence - 0.8765) < 1e-4


def test_botsort_track_persistence():
    """Confirmed tracks maintain persistent track_id across consecutive frames."""
    tracker = PlayerBoTSORT(BoTSORTConfig(gmc_method="none"))
    dets_f1 = [_make_det((100.0, 100.0, 200.0, 200.0), conf=0.90)]
    dets_f2 = [_make_det((105.0, 105.0, 205.0, 205.0), conf=0.88)]

    tracks1 = tracker.update_tracks(1, 0.0, dets_f1)
    tracks2 = tracker.update_tracks(2, 0.04, dets_f2)

    assert len(tracks1) == 1
    assert len(tracks2) == 1
    assert tracks1[0].track_id == tracks2[0].track_id == 1


def test_botsort_reset_between_sequences():
    """Calling reset() clears tracker memory and restarts track IDs."""
    tracker = PlayerBoTSORT(BoTSORTConfig(gmc_method="none"))
    dets = [_make_det((100.0, 100.0, 200.0, 200.0), conf=0.90)]

    tracks1 = tracker.update_tracks(1, 0.0, dets)
    assert tracks1[0].track_id == 1

    tracker.reset()
    tracks_after_reset = tracker.update_tracks(1, 0.0, dets)
    assert tracks_after_reset[0].track_id == 1


def test_botsort_fps_propagation():
    """Sequence FPS is propagated to tracker configuration."""
    cfg25 = BoTSORTConfig(frame_rate=25.0)
    tracker25 = PlayerBoTSORT(cfg25)
    assert tracker25.config.frame_rate == 25.0
    assert tracker25._tracker.args.frame_rate == 25.0


def test_bytetrack_baseline_immutability():
    """PlayerByteTrack config and defaults remain strictly unchanged from EXP-05."""
    cfg = ByteTrackConfig()
    assert cfg.track_activation_threshold == 0.45
    assert cfg.low_confidence_threshold == 0.10
    assert cfg.lost_track_buffer == 30
    assert cfg.minimum_matching_threshold == 0.8
    assert cfg.minimum_consecutive_frames == 1


def test_balltrack_manager_v2_immutability():
    """BallTrackManager V2 defaults from EXP-07 remain strictly unchanged."""
    v2_cfg = create_ball_track_config_v2()
    assert v2_cfg.version == "2.0.0"
    assert v2_cfg.enable_track_lifecycle is True
    assert v2_cfg.spatial_gate_max_radius == 500.0
    assert v2_cfg.max_gap_interpolation == 0
    assert v2_cfg.max_safe_interpolation_gap == 0
