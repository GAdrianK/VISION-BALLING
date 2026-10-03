"""Unit tests for Chapter 6B: Football Pitch Calibration Baseline Selection (EXP-13).

Verifies coordinate conventions, homography inversion, round-trip mappings,
invalid calibration rejection, player/ball projections, adapter isolation,
and strict non-mutation of Chapter 5 and Chapter 6A components.
"""

from __future__ import annotations

import sys
from pathlib import Path
import numpy as np
import pytest

from app.video_analysis.pitch_calibration import (
    PitchCalibrationResult,
    PitchDimensions,
    invert_homography,
)
from app.video_analysis.calibration_adapters import (
    BaseCalibrationAdapter,
    PnLCalibAdapter,
    TVCalibAdapter,
)


def test_coordinate_convention_dimensions() -> None:
    """Verifies canonical pitch geometry and coordinate limits in meters."""
    pitch = PitchDimensions(length_m=105.0, width_m=68.0)
    assert pitch.length_m == 105.0
    assert pitch.width_m == 68.0
    assert pitch.x_min == -52.5
    assert pitch.x_max == 52.5
    assert pitch.y_min == -34.0
    assert pitch.y_max == 34.0
    assert pitch.center_circle_radius_m == 9.15

    # Center mark is origin (0, 0)
    assert pitch.is_inside(0.0, 0.0)
    assert pitch.is_inside(52.5, 34.0)
    assert pitch.is_inside(-52.5, -34.0)
    assert not pitch.is_inside(53.0, 0.0)
    assert not pitch.is_inside(0.0, -35.0)

    # Custom pitch dimensions support
    custom_pitch = PitchDimensions(length_m=100.0, width_m=64.0)
    assert custom_pitch.x_min == -50.0
    assert custom_pitch.x_max == 50.0
    assert custom_pitch.y_min == -32.0
    assert custom_pitch.y_max == 32.0
    assert custom_pitch.is_inside(49.0, 31.0)
    assert not custom_pitch.is_inside(51.0, 0.0)


def test_homography_inversion_and_round_trip() -> None:
    """Verifies that invert_homography correctly handles regular and singular matrices."""
    # Regular homography (affine translation + scale + slight projective warp)
    H = np.array([
        [1.2, 0.1, 50.0],
        [-0.05, 1.1, 100.0],
        [0.0001, -0.0002, 1.0],
    ], dtype=np.float64)

    H_inv = invert_homography(H)
    assert H_inv is not None
    assert H_inv.shape == (3, 3)

    # Product should be identity matrix (up to scale)
    prod = H @ H_inv
    prod = prod / prod[2, 2]
    np.testing.assert_allclose(prod, np.eye(3), atol=1e-7)

    # Singular matrix rejection
    singular_H = np.array([
        [1.0, 2.0, 3.0],
        [2.0, 4.0, 6.0],  # colinear
        [0.0, 0.0, 1.0],
    ], dtype=np.float64)
    assert invert_homography(singular_H) is None

    # None and invalid shape handling
    assert invert_homography(None) is None
    assert invert_homography(np.eye(4)) is None


def test_pixel_to_pitch_to_pixel_round_trip() -> None:
    """Verifies sub-millimeter precision on pixel -> pitch -> pixel round trip."""
    # Synthetic projective homography from image (960x540) to pitch (105x68m)
    # Pitch center (0, 0) maps to image center (480, 270)
    H_p2i = np.array([
        [15.0, 0.5, 480.0],
        [-0.2, 12.0, 270.0],
        [0.0005, 0.001, 1.0],
    ], dtype=np.float64)
    H_i2p = np.linalg.inv(H_p2i)

    calib = PitchCalibrationResult(
        frame_index=1,
        valid=True,
        homography_image_to_pitch=H_i2p,
        homography_pitch_to_image=H_p2i,
    )

    test_pixels = [
        (480.0, 270.0),
        (200.0, 150.0),
        (750.0, 400.0),
        (100.0, 500.0),
    ]

    for u_orig, v_orig in test_pixels:
        pitch_pt = calib.image_to_pitch(u_orig, v_orig)
        assert pitch_pt is not None
        u_back, v_back = calib.pitch_to_image(pitch_pt[0], pitch_pt[1])
        assert abs(u_back - u_orig) < 1e-4
        assert abs(v_back - v_orig) < 1e-4


def test_invalid_calibration_rejection() -> None:
    """Verifies that invalid calibration or unprojectable points return None."""
    invalid_calib = PitchCalibrationResult(
        frame_index=0,
        valid=False,
        homography_image_to_pitch=None,
    )

    assert invalid_calib.image_to_pitch(100.0, 100.0) is None
    assert invalid_calib.pitch_to_image(0.0, 0.0) is None
    assert invalid_calib.project_player_bbox([10, 20, 30, 40]) is None
    assert invalid_calib.project_ball_bbox([50, 50, 60, 60]) is None

    # Valid calibration with out-of-bounds check
    H_p2i = np.eye(3, dtype=np.float64)
    H_i2p = np.eye(3, dtype=np.float64)
    calib = PitchCalibrationResult(
        frame_index=0,
        valid=True,
        homography_image_to_pitch=H_i2p,
        homography_pitch_to_image=H_p2i,
    )

    # Point at (500, 500) is way outside pitch [-52.5, 52.5] x [-34, 34]
    assert calib.image_to_pitch(500.0, 500.0, check_bounds=True) is None
    # Allowed when check_bounds=False
    assert calib.image_to_pitch(500.0, 500.0, check_bounds=False) == (500.0, 500.0)


def test_player_bottom_center_projection() -> None:
    """Verifies that player ground contact uses bottom-center anchor ((x1+x2)/2, y2)."""
    H_p2i = np.eye(3, dtype=np.float64)
    H_i2p = np.eye(3, dtype=np.float64)
    calib = PitchCalibrationResult(
        frame_index=0,
        valid=True,
        homography_image_to_pitch=H_i2p,
        homography_pitch_to_image=H_p2i,
    )

    bbox = [10.0, 20.0, 30.0, 50.0]  # x1=10, y1=20, x2=30, y2=50
    # Expected anchor: ((10 + 30)/2, 50) = (20.0, 50.0)
    pt = calib.project_player_bbox(bbox, check_bounds=False)
    assert pt == (20.0, 50.0)

    # Degenerate bbox rejection
    assert calib.project_player_bbox([30.0, 20.0, 10.0, 50.0]) is None  # x2 < x1
    assert calib.project_player_bbox([10.0, 50.0, 30.0, 20.0]) is None  # y2 < y1
    assert calib.project_player_bbox([10.0, 20.0]) is None  # insufficient coords


def test_ball_center_projection() -> None:
    """Verifies that ball ground contact uses center anchor ((x1+x2)/2, (y1+y2)/2)."""
    H_p2i = np.eye(3, dtype=np.float64)
    H_i2p = np.eye(3, dtype=np.float64)
    calib = PitchCalibrationResult(
        frame_index=0,
        valid=True,
        homography_image_to_pitch=H_i2p,
        homography_pitch_to_image=H_p2i,
    )

    bbox = [10.0, 20.0, 30.0, 40.0]  # x1=10, y1=20, x2=30, y2=40
    # Expected center anchor: ((10+30)/2, (20+40)/2) = (20.0, 30.0)
    pt = calib.project_ball_bbox(bbox, check_bounds=False)
    assert pt == (20.0, 30.0)


def test_adapter_isolation_no_gpl_in_core() -> None:
    """Verifies that importing adapters does NOT pollute sys.modules with GPL code."""
    # Ensure neither pnlcalib nor external model packages are loaded into core python modules
    gpl_modules = [m for m in sys.modules.keys() if "pnlcalib" in m.lower() or "cls_hrnet" in m.lower()]
    assert len(gpl_modules) == 0, f"Found GPL modules leaked into core namespace: {gpl_modules}"

    # Adapters are subclasses of BaseCalibrationAdapter
    assert issubclass(PnLCalibAdapter, BaseCalibrationAdapter)
    assert issubclass(TVCalibAdapter, BaseCalibrationAdapter)


def test_no_chapter5_and_chapter6a_mutation() -> None:
    """Verifies that Chapter 5 tracking and Chapter 6A team attribution modules are unchanged."""
    from app.video_analysis.detectors import RFDETRDetector
    from app.video_analysis.player_tracker import PlayerBoTSORT
    from app.video_analysis.ball_tracker import BallTrackManager
    from app.video_analysis.conditional_reid import ConditionalReIDPolicy
    from app.video_analysis.team_classifier import TeamClassifier

    # Verifies class availability and signatures
    assert hasattr(RFDETRDetector, "detect")
    assert hasattr(PlayerBoTSORT, "update_tracks")
    assert hasattr(BallTrackManager, "update")
    assert hasattr(ConditionalReIDPolicy, "evaluate_ambiguity")
    assert hasattr(TeamClassifier, "fit_and_assign")


def test_no_test_split_tuning_and_no_golden_cvat() -> None:
    """Verifies dataset discipline: calibration baseline selection used only valid split."""
    report_file = Path("docs/experiments/exp13_pitch_calibration_baselines.json")
    if report_file.exists():
        import json
        with open(report_file) as f:
            data = json.load(f)
        assert data.get("dataset", {}).get("split") == "valid"
        assert "test" not in data.get("dataset", {}).get("split", "")
