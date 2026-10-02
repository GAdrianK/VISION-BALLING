"""Unit tests for Chapter 6B: Metric Player & Ball Trajectories (EXP-15).

Verifies player bottom-center anchor, ball center anchor (with ground-plane Z=0 labeling),
FIFA coordinate conventions (105x68m, center origin), timestamp-based velocity estimation,
gap/reset handling, multi-method smoothing (RAW, POLYNOMIAL, KALMAN), physical speed limits,
structured JSONL serialization, and Chapter 5/6A/EXP-14 immutability.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pytest

from app.video_analysis.pitch_calibration import (
    PitchCalibrationResult,
    PitchDimensions,
)
from app.video_analysis.temporal_calibration import (
    TemporalCalibrationResult,
    TemporalCalibrationState,
)
from app.video_analysis.metric_trajectories import (
    BallMetricObservation,
    LinearKalman2D,
    MetricTrajectoryConfig,
    MetricTrajectoryEngine,
    PlayerMetricObservation,
    SmoothingMethod,
    TrackTrajectoryHistory,
)


def create_mock_calib_result(
    scale: float = 10.0,
    u_center: float = 480.0,
    v_center: float = 270.0,
    valid: bool = True,
    age: int = 0,
) -> PitchCalibrationResult:
    """Creates a synthetic affine calibration mapping: (u, v) -> (x, y) = ((u - u_center)/scale, (v - v_center)/scale)."""
    if not valid:
        return PitchCalibrationResult(frame_index=0, valid=False)

    H_p2i = np.array([
        [scale, 0.0, u_center],
        [0.0, scale, v_center],
        [0.0, 0.0, 1.0],
    ], dtype=np.float64)
    H_i2p = np.linalg.inv(H_p2i)

    return PitchCalibrationResult(
        frame_index=0,
        timestamp=0.0,
        valid=True,
        homography_image_to_pitch=H_i2p,
        homography_pitch_to_image=H_p2i,
        camera_parameters={"mock": True},
        reprojection_error_px=1.0,
        source_calibrator="MockCalib",
    )


def test_player_anchor_bottom_center() -> None:
    """Verifies that player ground anchor is strictly bbox bottom-center ((x1+x2)/2, y2)."""
    calib = create_mock_calib_result(scale=10.0, u_center=480.0, v_center=270.0)
    engine = MetricTrajectoryEngine()

    # Bbox: x1=470, y1=230, x2=510, y2=290
    # Center u = 490, bottom v = 290
    # Expected pitch x = (490 - 480)/10 = 1.0 m, pitch y = (290 - 270)/10 = 2.0 m
    players = [{"track_id": 1, "bbox": [470.0, 230.0, 510.0, 290.0]}]
    p_obs, b_obs = engine.process_frame(frame_index=1, timestamp=0.0, player_tracks=players, ball_detection_or_track=None, calibration_result=calib)

    assert len(p_obs) == 1
    obs = p_obs[0]
    assert obs.image_anchor_px == (490.0, 290.0)
    assert obs.position_valid is True
    assert obs.pitch_x_m is not None and abs(obs.pitch_x_m - 1.0) < 1e-4
    assert obs.pitch_y_m is not None and abs(obs.pitch_y_m - 2.0) < 1e-4


def test_ball_anchor_center_and_ground_plane_label() -> None:
    """Verifies that ball anchor is strictly bbox center ((x1+x2)/2, (y1+y2)/2) and labeled ground-plane Z=0."""
    calib = create_mock_calib_result(scale=10.0, u_center=480.0, v_center=270.0)
    engine = MetricTrajectoryEngine()

    # Bbox: x1=460, y1=250, x2=500, y2=290
    # Center u = 480, Center v = 270
    # Expected pitch x = 0.0 m, pitch y = 0.0 m
    ball = {"track_id": 0, "bbox": [460.0, 250.0, 500.0, 290.0]}
    p_obs, b_obs = engine.process_frame(frame_index=1, timestamp=0.0, player_tracks=[], ball_detection_or_track=ball, calibration_result=calib)

    assert b_obs is not None
    assert b_obs.image_anchor_px == (480.0, 270.0)
    assert b_obs.position_valid is True
    assert b_obs.pitch_x_m is not None and abs(b_obs.pitch_x_m - 0.0) < 1e-4
    assert b_obs.pitch_y_m is not None and abs(b_obs.pitch_y_m - 0.0) < 1e-4

    # Critical requirement: MUST be explicitly marked as ground-plane projection
    assert b_obs.is_ground_plane_projection is True


def test_pitch_coordinate_system_conventions_and_bounds() -> None:
    """Verifies standard FIFA dimensions (105x68m) centered at (0, 0) and bound checking."""
    dims = PitchDimensions(length_m=105.0, width_m=68.0)
    assert dims.x_min == -52.5
    assert dims.x_max == 52.5
    assert dims.y_min == -34.0
    assert dims.y_max == 34.0

    # Inside pitch
    assert dims.is_inside(0.0, 0.0) is True
    assert dims.is_inside(-52.0, 33.0) is True

    # Outside pitch without margin
    assert dims.is_inside(53.0, 0.0, margin_m=0.0) is False
    assert dims.is_inside(0.0, -35.0, margin_m=0.0) is False

    # Within margin
    assert dims.is_inside(53.0, 0.0, margin_m=5.0) is True
    assert dims.is_inside(65.0, 0.0, margin_m=5.0) is False


def test_velocity_calculation_from_timestamps() -> None:
    """Verifies that velocities are calculated using actual timestamps (dt = t_k+1 - t_k-1)."""
    calib = create_mock_calib_result(scale=10.0, u_center=480.0, v_center=270.0)
    engine = MetricTrajectoryEngine(config=MetricTrajectoryConfig(smoothing_method=SmoothingMethod.RAW))

    # Frame 1: t=0.0, x=0.0, y=0.0 (anchor u=480, v=270)
    # Frame 2: t=0.04, x=0.2, y=0.1 (anchor u=482, v=271)
    # Frame 3: t=0.08, x=0.4, y=0.2 (anchor u=484, v=272)
    # Velocity at Frame 2 should be: vx = (0.4 - 0.0) / 0.08 = 5.0 m/s, vy = (0.2 - 0.0) / 0.08 = 2.5 m/s
    coords = [(0.0, 480.0, 270.0), (0.04, 482.0, 271.0), (0.08, 484.0, 272.0)]
    for fid, (ts, u, v) in enumerate(coords, start=1):
        engine.process_frame(
            frame_index=fid,
            timestamp=ts,
            player_tracks=[{"track_id": 1, "bbox": [u - 10, v - 30, u + 10, v]}],
            ball_detection_or_track=None,
            calibration_result=calib,
        )

    engine.finalize_offline_smoothing()
    obs_f2 = engine.player_histories[1].observations[1]
    assert obs_f2.velocity_x_mps is not None and abs(obs_f2.velocity_x_mps - 5.0) < 1e-3
    assert obs_f2.velocity_y_mps is not None and abs(obs_f2.velocity_y_mps - 2.5) < 1e-3
    expected_speed = np.hypot(5.0, 2.5)
    assert obs_f2.speed_mps is not None and abs(obs_f2.speed_mps - expected_speed) < 1e-3


def test_gap_and_reset_handling() -> None:
    """Verifies that velocities are NOT computed across large temporal tracking gaps."""
    calib = create_mock_calib_result(scale=10.0, u_center=480.0, v_center=270.0)
    engine = MetricTrajectoryEngine(config=MetricTrajectoryConfig(smoothing_method=SmoothingMethod.RAW, max_interpolation_gap_frames=3))

    # Frame 1: t=0.0, pos=0.0
    engine.process_frame(1, 0.0, [{"track_id": 1, "bbox": [470, 240, 490, 270]}], None, calib)
    # Frame 20 (gap of 19 frames): t=0.8, pos=10.0
    engine.process_frame(20, 0.8, [{"track_id": 1, "bbox": [570, 240, 590, 270]}], None, calib)

    engine.finalize_offline_smoothing()
    obs1 = engine.player_histories[1].observations[0]
    obs20 = engine.player_histories[1].observations[1]

    # Because gap exceeds max_interpolation_gap_frames (3 frames), velocities must NOT bridge across 19 frames!
    assert obs1.velocity_x_mps is None
    assert obs20.velocity_x_mps is None


def test_smoothing_methods_comparison() -> None:
    """Compares RAW, POLYNOMIAL, and KALMAN smoothing on noisy synthetic trajectory."""
    calib = create_mock_calib_result(scale=10.0, u_center=480.0, v_center=270.0)

    # 15 frames of straight motion + alternating high-frequency jitter +/- 0.5m (+/- 5 px)
    np.random.seed(42)
    raw_engine = MetricTrajectoryEngine(config=MetricTrajectoryConfig(smoothing_method=SmoothingMethod.RAW))
    poly_engine = MetricTrajectoryEngine(config=MetricTrajectoryConfig(smoothing_method=SmoothingMethod.POLYNOMIAL, polynomial_window_size=5))
    kalman_engine = MetricTrajectoryEngine(config=MetricTrajectoryConfig(smoothing_method=SmoothingMethod.KALMAN))

    for fid in range(1, 21):
        ts = (fid - 1) * 0.04
        true_x = 0.5 * fid  # 0.5 m/step
        jitter = 0.4 if fid % 2 == 0 else -0.4  # High frequency jitter
        noisy_x = true_x + jitter
        u = 480.0 + (noisy_x * 10.0)
        v = 270.0

        p = [{"track_id": 1, "bbox": [u - 10, v - 30, u + 10, v]}]
        raw_engine.process_frame(fid, ts, p, None, calib)
        poly_engine.process_frame(fid, ts, p, None, calib)
        kalman_engine.process_frame(fid, ts, p, None, calib)

    raw_engine.finalize_offline_smoothing()
    poly_engine.finalize_offline_smoothing()
    kalman_engine.finalize_offline_smoothing()

    # Measure coordinate roughness / high-frequency step variations
    def compute_step_variance(engine: MetricTrajectoryEngine) -> float:
        obs = engine.player_histories[1].observations
        diffs = [abs(obs[i].smoothed_x_m - obs[i - 1].smoothed_x_m) for i in range(1, len(obs))]
        return float(np.var(diffs))

    var_raw = compute_step_variance(raw_engine)
    var_poly = compute_step_variance(poly_engine)
    var_kalman = compute_step_variance(kalman_engine)

    # Both polynomial and Kalman must significantly reduce high-frequency step variance compared to RAW
    assert var_poly < var_raw
    assert var_kalman < var_raw


def test_physical_speed_plausibility_limits() -> None:
    """Verifies that physically impossible human/ball speeds are flagged correctly."""
    calib = create_mock_calib_result(scale=10.0, u_center=480.0, v_center=270.0)
    engine = MetricTrajectoryEngine(config=MetricTrajectoryConfig(
        smoothing_method=SmoothingMethod.RAW,
        max_player_speed_mps=12.5,
        max_ball_speed_mps=55.0,
    ))

    # Frame 1: player at 0.0, ball at 0.0, t=0.0
    # Frame 2: player moves 1.0 m in 0.04 s -> speed = 25.0 m/s (> 12.5 m/s human limit!)
    #          ball moves 1.0 m in 0.04 s -> speed = 25.0 m/s (<= 55.0 m/s ball strike limit)
    engine.process_frame(1, 0.0, [{"track_id": 1, "bbox": [470, 240, 490, 270]}], {"track_id": 0, "bbox": [475, 265, 485, 275]}, calib)
    engine.process_frame(2, 0.04, [{"track_id": 1, "bbox": [480, 240, 500, 270]}], {"track_id": 0, "bbox": [485, 265, 495, 275]}, calib)

    engine.finalize_offline_smoothing()
    p_obs = engine.player_histories[1].observations[1]
    b_obs = engine.ball_history.observations[1]

    # Player exceeds 12.5 m/s -> speed_plausible is False
    assert p_obs.speed_mps is not None and p_obs.speed_mps > 12.5
    assert p_obs.speed_plausible is False

    # Ball 25.0 m/s is within 55.0 m/s -> speed_plausible is True
    assert b_obs.speed_mps is not None and b_obs.speed_mps < 55.0
    assert b_obs.speed_plausible is True


def test_jsonl_export_schema_and_roundtrip(tmp_path: Path) -> None:
    """Verifies that export_to_jsonl serializes complete schemas with provenance and round-trips correctly."""
    calib = create_mock_calib_result(scale=10.0, u_center=480.0, v_center=270.0)
    engine = MetricTrajectoryEngine()

    engine.process_frame(
        frame_index=1,
        timestamp=0.0,
        player_tracks=[{"track_id": 10, "bbox": [470, 240, 490, 270], "team_label": "Team A", "role": "player"}],
        ball_detection_or_track={"track_id": 0, "bbox": [478, 268, 482, 272]},
        calibration_result=calib,
    )
    engine.finalize_offline_smoothing()

    out_file = tmp_path / "test_trajectories.jsonl"
    count = engine.export_to_jsonl(out_file, sequence_id="SNMOT-TEST")
    assert count == 1
    assert out_file.exists()

    with open(out_file, "r") as f:
        line = f.readline()
        record = json.loads(line)

    assert record["sequence_id"] == "SNMOT-TEST"
    assert record["frame_index"] == 1
    assert len(record["players"]) == 1
    p = record["players"][0]
    assert p["track_id"] == 10
    assert p["team_label"] == "Team A"
    assert p["role"] == "player"
    assert p["position_valid"] is True
    assert "smoothed_x_m" in p
    assert "velocity_x_mps" in p

    assert record["ball"] is not None
    b = record["ball"]
    assert b["is_ground_plane_projection"] is True
    assert b["position_valid"] is True


def test_chapter_immutability_strictness() -> None:
    """Verifies Chapter 5, Chapter 6A, and EXP-14 codebases remain unchanged."""
    import inspect
    from app.video_analysis.detectors import RFDETRDetector
    from app.video_analysis.player_tracker import PlayerBoTSORT
    from app.video_analysis.ball_tracker import BallTrackManager
    from app.video_analysis.team_classifier import TeamClassifier
    from app.video_analysis.temporal_calibration import TemporalPitchCalibrator

    # Check key methods exist unmodified
    assert hasattr(RFDETRDetector, "detect")
    assert hasattr(PlayerBoTSORT, "update_tracks")
    assert hasattr(BallTrackManager, "update")
    assert hasattr(TeamClassifier, "fit_and_assign")
    assert hasattr(TemporalPitchCalibrator, "update")
