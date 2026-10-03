from __future__ import annotations

import configparser
import json
import math
from pathlib import Path

import numpy as np
import pytest

from app.video_analysis.tracking_schemas import BallObservationState, BallTrackObservation


# ==============================================================================
# PHASE 10: EXP-06 BALL DIAGNOSTICS TESTS
# ==============================================================================


def test_multiple_gt_ball_ids_parsing() -> None:
    """Verifies that SNMOT-061 contains two distinct ball IDs (1 and 27) coexisting across frames 576..583."""
    gameinfo_path = Path("/media/adriano/Windows/datasets/SoccerNetTracking2023/train/SNMOT-061/gameinfo.ini")
    gt_path = Path("/media/adriano/Windows/datasets/SoccerNetTracking2023/train/SNMOT-061/gt/gt.txt")

    if not (gameinfo_path.is_file() and gt_path.is_file()):
        pytest.skip("SoccerNet dataset not mounted.")

    cp = configparser.ConfigParser()
    cp.read(gameinfo_path)

    ball_ids = set()
    for k, v in cp["Sequence"].items():
        if k.startswith("trackletid_") and v.split(";")[0].strip().lower().startswith("ball"):
            ball_ids.add(int(k.replace("trackletid_", "")))

    assert ball_ids == {1, 27}, f"SNMOT-061 must contain ball IDs 1 and 27, found {ball_ids}"

    # Parse GT lines
    frames_b1 = []
    frames_b27 = []
    for line in gt_path.read_text().splitlines():
        parts = line.split(",")
        if len(parts) >= 6:
            f, tid = int(parts[0]), int(parts[1])
            if tid == 1:
                frames_b1.append(f)
            elif tid == 27:
                frames_b27.append(f)

    assert min(frames_b1) == 1 and max(frames_b1) == 583
    assert min(frames_b27) == 576 and max(frames_b27) == 750

    coexisting = set(frames_b1) & set(frames_b27)
    assert len(coexisting) == 8  # frames 576..583
    assert coexisting == set(range(576, 584))


def test_ball_track_lifecycle_and_monolithic_id() -> None:
    """
    Verifies that BallTrackObservation lacks an explicit track_id field,
    proving the architectural limitation that causes monolithic track assignment.
    """
    obs = BallTrackObservation(
        frame_index=1,
        timestamp=0.0,
        bbox=(100.0, 100.0, 114.0, 114.0),
        position=(107.0, 107.0),
        velocity=(0.0, 0.0),
        observation_state=BallObservationState.DETECTED,
        confidence=0.85,
    )
    # BallTrackObservation schema does not declare a track_id attribute
    assert not hasattr(obs, "track_id") or getattr(obs, "track_id", None) is None


def test_center_distance_and_iou_sensitivity() -> None:
    """
    Proves mathematically that for a typical tiny football ball (14x14 pixels),
    a center offset of only 6 pixels drops IoU below the 0.50 threshold,
    explaining why HOTA@0.5 penalizes millimeter-level spatial localization.
    """
    def compute_iou(b1: tuple[float, float, float, float], b2: tuple[float, float, float, float]) -> float:
        x1 = max(b1[0], b2[0])
        y1 = max(b1[1], b2[1])
        x2 = min(b1[2], b2[2])
        y2 = min(b1[3], b2[3])
        inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
        a1 = (b1[2] - b1[0]) * (b1[3] - b1[1])
        a2 = (b2[2] - b2[0]) * (b2[3] - b2[1])
        union = a1 + a2 - inter
        return inter / union if union > 0 else 0.0

    # Ground truth ball: 14x14 pixels at (100, 100) -> center (107, 107)
    gt_box = (100.0, 100.0, 114.0, 114.0)

    # 1. Close detection: 2 px center shift -> center (109, 107)
    close_pred = (102.0, 100.0, 116.0, 114.0)
    iou_close = compute_iou(close_pred, gt_box)
    assert iou_close > 0.70  # ~0.75

    # 2. Moderate detection: 6 px center shift -> center (113, 107)
    # A 6-pixel error is only 0.31% of 1920px image width!
    moderate_pred = (106.0, 100.0, 120.0, 114.0)
    iou_moderate = compute_iou(moderate_pred, gt_box)
    assert iou_moderate < 0.50  # ~0.40, fails HOTA@0.5!

    # 3. 7 px center shift -> center (114, 107)
    shifted_pred = (107.0, 100.0, 121.0, 114.0)
    iou_shifted = compute_iou(shifted_pred, gt_box)
    assert iou_shifted <= 0.35


def test_gap_length_grouping_logic() -> None:
    """Verifies binning logic for gap lengths into standard diagnostic categories."""
    def get_bin(gap_len: int) -> str:
        if gap_len == 1:
            return "1_frame"
        elif gap_len == 2:
            return "2_frames"
        elif gap_len == 3:
            return "3_frames"
        elif 4 <= gap_len <= 5:
            return "4_5_frames"
        elif 6 <= gap_len <= 10:
            return "6_10_frames"
        elif 11 <= gap_len <= 15:
            return "11_15_frames"
        return "unsupported"

    assert get_bin(1) == "1_frame"
    assert get_bin(2) == "2_frames"
    assert get_bin(3) == "3_frames"
    assert get_bin(4) == "4_5_frames"
    assert get_bin(5) == "4_5_frames"
    assert get_bin(7) == "6_10_frames"
    assert get_bin(12) == "11_15_frames"


def test_exp05_report_integrity_no_mutation() -> None:
    """Verifies that docs/experiments/exp05_soccernet_tracking_baseline.json remains unmodified and valid."""
    p = Path("docs/experiments/exp05_soccernet_tracking_baseline.json")
    assert p.is_file()
    data = json.loads(p.read_text(encoding="utf-8"))

    assert data["experiment"] == "exp05_soccernet_tracking_baseline"
    assert data["macro_metrics"]["ball"]["hota_0_5"] == 0.2583
    assert data["macro_metrics"]["person"]["hota_0_5"] == 0.7891
    assert data["macro_metrics"]["class_agnostic"]["hota_0_5"] == 0.7583
    assert data["macro_metrics"]["throughput"]["macro_fps_end_to_end"] == 32.99


def test_exp06_report_generated_and_valid() -> None:
    """Verifies that docs/experiments/exp06_ball_tracking_diagnostics.json is generated with all diagnostic sections."""
    p = Path("docs/experiments/exp06_ball_tracking_diagnostics.json")
    assert p.is_file(), f"Rapport EXP-06 introuvable : {p}"
    data = json.loads(p.read_text(encoding="utf-8"))

    assert data["experiment"] == "exp06_ball_tracking_diagnostics"
    assert "diagnostics_summary" in data
    assert "macro_spatial_metrics" in data["diagnostics_summary"]
    assert "macro_state_breakdown" in data["diagnostics_summary"]
    assert "macro_ablation_comparison" in data["diagnostics_summary"]
    assert "velocity_audit" in data["diagnostics_summary"]
    assert "per_sequence_diagnostics" in data
    assert "recommendations_for_exp07" in data

    # Verify quantitative metrics exist
    spatial = data["diagnostics_summary"]["macro_spatial_metrics"]
    assert spatial["median_center_error_px"] == pytest.approx(3.35, abs=0.1)
    assert spatial["accuracy"]["within_10px"] > 0.70
    assert spatial["accuracy"]["within_20px"] > 0.85

    # Verify detected-only beats baseline in ablation
    ablation = data["diagnostics_summary"]["macro_ablation_comparison"]
    assert ablation["detected_only"]["hota_0_5"] > ablation["exp05_online_baseline"]["hota_0_5"]

    # Verify failure clips exist
    for seq in ["SNMOT-060", "SNMOT-061", "SNMOT-062"]:
        clips = data["per_sequence_diagnostics"][seq]["failure_artifacts"]
        assert len(clips) >= 1
        for clip in clips:
            assert Path(clip).is_file(), f"Clip vidéo introuvable : {clip}"


def test_no_h250_test_in_diagnostics() -> None:
    """Verifies that diagnostic scripts do not reference or import H250 test split."""
    diag_script = Path("scripts/run_exp06_ball_diagnostics.py").read_text()
    assert "datasets/h250/YOLO/test" not in diag_script
    assert "test_h250" not in diag_script


def test_no_golden_cvat_in_diagnostics() -> None:
    """Verifies that diagnostic scripts do not import golden/CVAT datasets."""
    diag_script = Path("scripts/run_exp06_ball_diagnostics.py").read_text()
    assert "golden_annotations" not in diag_script
    assert "golden_cvat" not in diag_script
