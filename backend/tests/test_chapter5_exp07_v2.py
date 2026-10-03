"""
Unit tests for Chapter 5 EXP-07 Ball Tracker V2.
Tests multi-ball lifecycle management, bounded spatial gating,
anchor consistency, and conservative short-gap interpolation.
"""
from __future__ import annotations

import pytest
from app.video_analysis.ball_tracker import (
    BallTrackConfig,
    BallTrackManager,
    create_ball_track_config_v2,
)
from app.video_analysis.detectors import RawDetection
from app.video_analysis.tracking_schemas import (
    BallLifecycleState,
    BallObservationState,
    BallTrackObservation,
)


def _make_det(bbox: tuple[float, float, float, float], conf: float = 0.8) -> RawDetection:
    return RawDetection(
        class_name="sports ball",
        football_role="ball",
        confidence=conf,
        bbox=tuple(int(round(x)) for x in bbox),  # type: ignore[arg-type]
    )


def test_v1_backwards_compatibility():
    """Default BallTrackConfig maintains V1 behavior and defaults."""
    cfg = BallTrackConfig()
    assert cfg.version == "1.0.0"
    assert cfg.enable_track_lifecycle is False
    assert cfg.spatial_gate_max_radius is None
    assert cfg.max_gap_interpolation == 15

    mgr = BallTrackManager(cfg)
    assert mgr.current_track_id == 1
    assert mgr.recovered_gaps_count == 0


def test_v2_factory_defaults():
    """Factory create_ball_track_config_v2 sets explicit V2 parameters."""
    cfg = create_ball_track_config_v2()
    assert cfg.version == "2.0.0"
    assert cfg.enable_track_lifecycle is True
    assert cfg.spatial_gate_max_radius == 500.0
    assert cfg.spatial_gate_growth_per_frame == 35.0
    assert cfg.max_gap_interpolation == 0
    assert cfg.max_safe_interpolation_gap == 0
    assert cfg.lost_timeout_frames == 25
    assert cfg.reacquisition_max_distance == 300.0
    assert cfg.anchor_consistency_max_speed == 60.0


def test_bounded_spatial_gate():
    """Spatial gate radius expands sub-linearly and strictly caps at spatial_gate_max_radius."""
    cfg = create_ball_track_config_v2(spatial_gate_max_radius=220.0)
    mgr = BallTrackManager(cfg)

    # dt = 1: base distance 150
    assert mgr._gate_radius(1) == 150.0
    # dt = 2: 150 + 35 = 185 <= 220
    assert mgr._gate_radius(2) == 185.0
    # dt = 3: min(150 + 70, 220) = 220
    assert mgr._gate_radius(3) == 220.0
    # dt = 4: min(150 + 105, 220) = 220
    assert mgr._gate_radius(4) == 220.0
    # dt = 10: strictly capped at 220 (never reaches 1200)
    assert mgr._gate_radius(10) == 220.0
    assert mgr._gate_radius(50) == 220.0


def test_lifecycle_single_track_continuity():
    """Continuous detections stay on track_id = 1 with ACTIVE lifecycle."""
    cfg = create_ball_track_config_v2()
    mgr = BallTrackManager(cfg)

    # Frame 1: first detection
    obs1 = mgr.update(1, 0.0, [_make_det((100.0, 100.0, 120.0, 120.0))])
    assert obs1.observation_state == BallObservationState.DETECTED
    assert obs1.track_id == 1
    assert obs1.lifecycle_state == BallLifecycleState.ACTIVE
    assert mgr.current_track_id == 1
    assert mgr.lifecycle_state == BallLifecycleState.ACTIVE

    # Frame 2: consecutive detection close
    obs2 = mgr.update(2, 0.033, [_make_det((105.0, 105.0, 125.0, 125.0))])
    assert obs2.observation_state == BallObservationState.DETECTED
    assert obs2.track_id == 1
    assert obs2.lifecycle_state == BallLifecycleState.ACTIVE


def test_lifecycle_timeout_and_track_increment():
    """Lost ball exceeding timeout transitions to TERMINATED, spawning track_id = 2 on next ball."""
    cfg = create_ball_track_config_v2(lost_timeout_frames=5, max_gap_interpolation=2)
    mgr = BallTrackManager(cfg)

    # Frame 1: Detection
    mgr.update(1, 0.0, [_make_det((100.0, 100.0, 120.0, 120.0))])
    assert mgr.current_track_id == 1

    # Frames 2-3: gap <= 2 -> PREDICTED, ACTIVE
    mgr.update(2, 0.033, [])
    mgr.update(3, 0.066, [])
    assert mgr.history[3].observation_state == BallObservationState.PREDICTED

    # Frame 4: gap > 2 -> LOST
    mgr.update(4, 0.100, [])
    assert mgr.lifecycle_state == BallLifecycleState.LOST

    # Frames 5..9: misses reach timeout (> 5) -> TERMINATED
    for f in range(5, 10):
        mgr.update(f, f * 0.033, [])
    assert mgr.lifecycle_state == BallLifecycleState.TERMINATED

    # Frame 10: New ball appears across the pitch
    obs10 = mgr.update(10, 0.33, [_make_det((800.0, 800.0, 820.0, 820.0))])
    assert obs10.observation_state == BallObservationState.DETECTED
    assert obs10.track_id == 2
    assert mgr.current_track_id == 2
    assert mgr.lifecycle_state == BallLifecycleState.ACTIVE


def test_lifecycle_distant_reacquisition_spawns_new_id():
    """When LOST, a detection exceeding reacquisition_max_distance spawns a new track ID."""
    cfg = create_ball_track_config_v2(
        lost_timeout_frames=5,
        max_gap_interpolation=2,
        reacquisition_max_distance=200.0,
    )
    mgr = BallTrackManager(cfg)

    # Frame 1: Ball 1 detected at (100, 100)
    mgr.update(1, 0.0, [_make_det((100.0, 100.0, 114.0, 114.0))])

    # Frames 2-6: misses -> reaches timeout
    for f in range(2, 7):
        mgr.update(f, f * 0.033, [])
    assert mgr.lifecycle_state in (BallLifecycleState.LOST, BallLifecycleState.TERMINATED)

    # Frame 7: Detection appears at (600, 600) -> distance > 200px
    obs7 = mgr.update(7, 0.23, [_make_det((600.0, 600.0, 614.0, 614.0))])
    assert obs7.observation_state == BallObservationState.DETECTED
    assert obs7.track_id == 2
    assert mgr.current_track_id == 2


def test_lifecycle_close_reacquisition_preserves_id():
    """When LOST within timeout, a detection within reacquisition_max_distance keeps same track ID."""
    cfg = create_ball_track_config_v2(
        lost_timeout_frames=50,
        max_gap_interpolation=2,
        reacquisition_max_distance=200.0,
    )
    mgr = BallTrackManager(cfg)

    # Frame 1: Ball 1 detected at (100, 100)
    mgr.update(1, 0.0, [_make_det((100.0, 100.0, 114.0, 114.0))])

    # Frames 2-5: misses -> becomes LOST
    for f in range(2, 6):
        mgr.update(f, f * 0.033, [])
    assert mgr.lifecycle_state == BallLifecycleState.LOST

    # Frame 6: Detection appears at (140, 140) -> distance ~ 56px <= 200px
    obs6 = mgr.update(6, 0.20, [_make_det((140.0, 140.0, 154.0, 154.0))])
    assert obs6.observation_state == BallObservationState.DETECTED
    assert obs6.track_id == 1
    assert mgr.current_track_id == 1


def test_distractor_anchor_rejection():
    """If anchor velocity across gap exceeds anchor_consistency_max_speed, interpolation is rejected."""
    cfg = create_ball_track_config_v2(
        max_safe_interpolation_gap=3,
        max_gap_interpolation=5,
        anchor_consistency_max_speed=50.0,
        spatial_gate_max_radius=300.0,
    )
    mgr = BallTrackManager(cfg)

    # Frame 1: Ball detected at (100, 100)
    mgr.update(1, 0.0, [_make_det((95.0, 95.0, 105.0, 105.0))])

    # Frame 2: Gap frame (predicted)
    mgr.update(2, 0.033, [])
    assert mgr.history[2].observation_state == BallObservationState.PREDICTED

    # Frame 3: Detection at (280, 100). dt=2, dist=180px, speed=90px/frame > 50px/frame ceiling!
    mgr.update(3, 0.066, [_make_det((275.0, 95.0, 285.0, 105.0))])

    # The anchor was rejected for excessive jump speed!
    assert mgr.rejected_anchor_count == 1
    # Frame 2 was cleaned to LOST rather than hallucinating an interpolated box
    assert mgr.history[2].observation_state == BallObservationState.LOST
    assert mgr.history[2].bbox == (0.0, 0.0, 0.0, 0.0)


def test_conservative_interpolation_short_gap():
    """Gaps <= max_safe_interpolation_gap (3) with valid anchors are cleanly interpolated."""
    cfg = create_ball_track_config_v2(
        max_gap_interpolation=3,
        max_safe_interpolation_gap=3,
    )
    mgr = BallTrackManager(cfg)

    # Frame 1: center at (100, 100)
    mgr.update(1, 0.0, [_make_det((95.0, 95.0, 105.0, 105.0))])

    # Frames 2, 3: missing
    mgr.update(2, 0.033, [])
    mgr.update(3, 0.066, [])

    # Frame 4: center at (130, 100) -> dt=3, dist=30px, speed=10px/frame (smooth)
    mgr.update(4, 0.100, [_make_det((125.0, 95.0, 135.0, 105.0))])

    assert mgr.history[2].observation_state == BallObservationState.INTERPOLATED
    assert mgr.history[3].observation_state == BallObservationState.INTERPOLATED
    assert mgr.recovered_gaps_count == 1
    assert mgr.recovered_frames_count == 2
    # Verify interpolated positions
    assert abs(mgr.history[2].position[0] - 110.0) < 1e-4
    assert abs(mgr.history[3].position[0] - 120.0) < 1e-4


def test_ball_track_observation_schema_v2():
    """BallTrackObservation correctly serializes track_id and lifecycle_state."""
    obs = BallTrackObservation(
        frame_index=1,
        timestamp=0.033,
        bbox=(10.0, 20.0, 30.0, 40.0),
        position=(20.0, 30.0),
        velocity=(1.0, 2.0),
        observation_state=BallObservationState.DETECTED,
        gap_length=0,
        confidence=0.85,
        track_id=2,
        lifecycle_state=BallLifecycleState.ACTIVE,
    )
    d = obs.to_dict()
    assert d["track_id"] == 2
    assert d["lifecycle_state"] == "ACTIVE"
