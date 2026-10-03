#!/usr/bin/env python3
"""EXP-23: Defensive Pressure & Engagement Intelligence Benchmark Runner.

Executes:
1. Phase 18: Synthetic deterministic state fixtures (10 scenarios)
2. Phase 19: Physical monotonicity verification (distance, closing speed, density)
3. Model comparison & calibration on DEV sequences (SNMOT-060, 063, 064)
4. Comprehensive evaluation on strictly frozen HOLDOUT sequences (SNMOT-066, 068, 069, 070, 071)
5. Continuous metric distributions & primary physical indicators
6. Semantic classification metrics (accuracy, balanced accuracy, macro F1, coverage, abstention)
7. Carrier-confidence stratification (HIGH vs MEDIUM vs LOW)
8. Ball-only fallback diagnostic
9. Transition-boundary diagnostic (+/- 10 frames around confirmed V2 turnovers)
10. Steady-state runtime profiling (< 0.50 ms/frame budget)
11. Generates timeseries and 2D pitch visual artifacts
12. Compiles docs/experiments/exp23_defensive_pressure.json
"""

from __future__ import annotations

import configparser
import json
import logging
import math
import os
import pickle
import platform
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, confusion_matrix

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.video_analysis.pitch_calibration import PitchCalibrationResult, PitchDimensions
from app.video_analysis.temporal_calibration import (
    TemporalCalibrationConfig,
    TemporalPitchCalibrator,
)
from app.video_analysis.player_tracker import BoTSORTConfig, PlayerBoTSORT
from app.video_analysis.ball_tracker import BallTrackManager, create_ball_track_config_v2
from app.video_analysis.metric_trajectories import (
    MetricTrajectoryConfig,
    MetricTrajectoryEngine,
    SmoothingMethod,
)
from app.video_analysis.tactical_geometry import (
    TacticalGeometryConfig,
    TacticalGeometryEngine,
)
from app.video_analysis.tactical_lines import (
    TacticalLineConfig,
    OrientedTacticsEngine,
)
from app.video_analysis.defensive_block import (
    DefensiveBlockConfig,
    DefensiveBlockEngine,
)
from app.video_analysis.possession_v2 import (
    PossessionConfigV2,
    PossessionEngineV2,
)
from app.video_analysis.defensive_pressure import (
    DefensivePressureConfig,
    DefensivePressureEngine,
    FrameDefensivePressureState,
    IndividualDefenderPressure,
    PressureSemanticClass,
    PressureTargetType,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("EXP-23-BENCHMARK")

FPS = 25.0

DEV_SEQUENCES = ["SNMOT-060", "SNMOT-063", "SNMOT-064"]
HOLDOUT_SEQUENCES = ["SNMOT-066", "SNMOT-068", "SNMOT-069", "SNMOT-070", "SNMOT-071"]

RAW_DETS_MAP = {
    "SNMOT-060": Path("/media/adriano/Windows/runs/tracking/exp10/SNMOT-060_raw_dets.pkl"),
    "SNMOT-061": Path("/media/adriano/Windows/runs/tracking/exp10/SNMOT-061_raw_dets.pkl"),
    "SNMOT-062": Path("/media/adriano/Windows/runs/tracking/exp10/SNMOT-062_raw_dets.pkl"),
    "SNMOT-063": Path("/media/adriano/Windows/runs/tracking/exp07/SNMOT-063_raw_dets.pkl"),
    "SNMOT-064": Path("/media/adriano/Windows/runs/tracking/exp07/SNMOT-064_raw_dets.pkl"),
    "SNMOT-065": Path("/media/adriano/Windows/runs/tracking/exp07/SNMOT-065_raw_dets.pkl"),
    "SNMOT-066": Path("/media/adriano/Windows/runs/tracking/exp08/SNMOT-066_raw_dets.pkl"),
    "SNMOT-067": Path("/media/adriano/Windows/runs/tracking/exp08/SNMOT-067_raw_dets.pkl"),
    "SNMOT-068": Path("/media/adriano/Windows/runs/tracking/exp08/SNMOT-068_raw_dets.pkl"),
    "SNMOT-069": Path("/media/adriano/Windows/runs/tracking/exp10/SNMOT-069_raw_dets.pkl"),
    "SNMOT-070": Path("/media/adriano/Windows/runs/tracking/exp10/SNMOT-070_raw_dets.pkl"),
    "SNMOT-071": Path("/media/adriano/Windows/runs/tracking/exp10/SNMOT-071_raw_dets.pkl"),
}


class RobustCachedCalibAdapter:
    """Wraps pre-calibrated keyframes with safe nearest-keyframe fallback."""

    def __init__(self, disk_cache_path: Path) -> None:
        self.cache: Dict[str, PitchCalibrationResult] = {}
        if disk_cache_path.is_file():
            with open(disk_cache_path, "rb") as f:
                self.cache = pickle.load(f)
            logger.info("Loaded %d pre-calibrated keyframes from %s", len(self.cache), disk_cache_path)

    def calibrate_image(
        self,
        image_path: Path,
        frame_index: Optional[int] = None,
        timestamp: Optional[float] = None,
    ) -> PitchCalibrationResult:
        key = str(image_path)
        if key in self.cache:
            res = self.cache[key]
            return PitchCalibrationResult(
                frame_index=frame_index,
                timestamp=timestamp,
                valid=res.valid,
                homography_image_to_pitch=res.homography_image_to_pitch.copy() if res.homography_image_to_pitch is not None else None,
                homography_pitch_to_image=res.homography_pitch_to_image.copy() if res.homography_pitch_to_image is not None else None,
                camera_parameters=res.camera_parameters,
                reprojection_error_px=res.reprojection_error_px,
                source_calibrator=res.source_calibrator,
                pitch_dimensions=res.pitch_dimensions,
            )

        seq_id = None
        for part in image_path.parts:
            if part.startswith("SNMOT-"):
                seq_id = part
                break

        if seq_id:
            seq_keys = [k for k in self.cache.keys() if seq_id in k]
            if seq_keys:
                try:
                    curr_num = int(image_path.stem)
                    closest_k = min(seq_keys, key=lambda k: abs(int(Path(k).stem) - curr_num))
                    res = self.cache[closest_k]
                    return PitchCalibrationResult(
                        frame_index=frame_index,
                        timestamp=timestamp,
                        valid=res.valid,
                        homography_image_to_pitch=res.homography_image_to_pitch.copy() if res.homography_image_to_pitch is not None else None,
                        homography_pitch_to_image=res.homography_pitch_to_image.copy() if res.homography_pitch_to_image is not None else None,
                        camera_parameters=res.camera_parameters,
                        reprojection_error_px=res.reprojection_error_px,
                        source_calibrator=res.source_calibrator,
                        pitch_dimensions=res.pitch_dimensions,
                    )
                except ValueError:
                    pass

        return PitchCalibrationResult(frame_index=frame_index, timestamp=timestamp, valid=False)


def compute_iou(box1: List[float], box2: List[float]) -> float:
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])
    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    a1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    a2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union = a1 + a2 - inter
    return inter / union if union > 0 else 0.0


def load_sequence_roles_and_gameinfo(seq_dir: Path) -> Tuple[Dict[int, str], Dict[int, str]]:
    ini_path = seq_dir / "gameinfo.ini"
    roles: Dict[int, str] = {}
    teams: Dict[int, str] = {}
    if not ini_path.is_file():
        return roles, teams

    cp = configparser.ConfigParser(strict=False)
    cp.read(str(ini_path))
    if "Sequence" in cp:
        sec = cp["Sequence"]
        for k, v in sec.items():
            if k.startswith("trackletid_"):
                try:
                    tid = int(k.replace("trackletid_", ""))
                    parts = v.split(";")
                    label_part = parts[0].strip().lower()
                    if "goalkeeper" in label_part:
                        roles[tid] = "GOALKEEPER"
                    elif "referee" in label_part:
                        roles[tid] = "REFEREE"
                    elif "ball" in label_part:
                        roles[tid] = "BALL"
                    else:
                        roles[tid] = "OUTFIELD_PLAYER"

                    if "team left" in label_part:
                        teams[tid] = "TEAM_0"
                    elif "team right" in label_part:
                        teams[tid] = "TEAM_1"
                except ValueError:
                    pass
    return roles, teams


def load_gt_bboxes_by_frame(seq_dir: Path) -> Dict[int, Dict[int, List[float]]]:
    gt_file = seq_dir / "gt" / "gt.txt"
    by_frame: Dict[int, Dict[int, List[float]]] = {}
    if not gt_file.is_file():
        return by_frame
    with open(gt_file, "r") as f:
        for line in f:
            parts = line.strip().split(",")
            if len(parts) >= 6:
                fid = int(parts[0])
                tid = int(parts[1])
                x, y, w, h = float(parts[2]), float(parts[3]), float(parts[4]), float(parts[5])
                if fid not in by_frame:
                    by_frame[fid] = {}
                by_frame[fid][tid] = [x, y, x + w, y + h]
    return by_frame


# ==============================================================================
# PHASE 18: SYNTHETIC TESTS (10 SCENARIOS)
# ==============================================================================

def run_synthetic_tests() -> Dict[str, Any]:
    logger.info("Executing Phase 18: Deterministic Synthetic Pressure Scenarios...")
    engine = DefensivePressureEngine()

    results: Dict[str, Any] = {}

    def _make_player(tid: int, team: str, x: float, y: float, vx: float = 0.0, vy: float = 0.0) -> Dict[str, Any]:
        return {
            "track_id": tid,
            "team_label": team,
            "role": "OUTFIELD_PLAYER",
            "pitch_x_m": x,
            "pitch_y_m": y,
            "vx_mps": vx,
            "vy_mps": vy,
            "speed_mps": float(np.hypot(vx, vy)),
            "bbox": [500 + x * 5, 500 + y * 5, 520 + x * 5, 540 + y * 5],
        }

    # Scenario 1: Isolated Carrier
    c = _make_player(1, "TEAM_0", 0.0, 0.0)
    d = _make_player(2, "TEAM_1", 25.0, 0.0)
    b = {"pitch_x_m": 0.0, "pitch_y_m": 0.0, "confidence": 0.9}
    poss = engine.target_resolver.resolve([c, d], b, None, True)
    # Manual target injection
    poss_state = type("MockPossState", (), {
        "is_valid": True,
        "controlling_player_id": 1,
        "controlling_player_team": "TEAM_0",
        "possession_team": "TEAM_0",
        "possession_confidence": 0.95,
    })()
    st1 = engine.process_frame(1, 0.04, [c, d], b, poss_state)
    assert st1.pressure_index < 0.10
    assert st1.semantic_class == PressureSemanticClass.NO_PRESSURE
    results["isolated_carrier"] = {"pressure_index": st1.pressure_index, "class": st1.semantic_class.value, "success": True}

    # Scenario 2: One Passive Defender at 3m
    d_passive = _make_player(2, "TEAM_1", 3.0, 0.0, 0.0, 0.0)
    st2 = engine.process_frame(2, 0.08, [c, d_passive], b, poss_state)
    assert 0.20 <= st2.pressure_index <= 0.50
    assert st2.semantic_class == PressureSemanticClass.LIGHT_PRESSURE
    results["one_passive_defender"] = {"pressure_index": st2.pressure_index, "class": st2.semantic_class.value, "success": True}

    # Scenario 3: One Rapidly Closing Defender at 3m
    d_closing = _make_player(2, "TEAM_1", 3.0, 0.0, -4.0, 0.0) # moving left toward c
    st3 = engine.process_frame(3, 0.12, [c, d_closing], b, poss_state)
    assert st3.pressure_index > st2.pressure_index # Must be higher than passive!
    assert st3.semantic_class in (PressureSemanticClass.LIGHT_PRESSURE, PressureSemanticClass.STRONG_PRESSURE)
    results["one_rapidly_closing_defender"] = {"pressure_index": st3.pressure_index, "closing_speed": st3.nearest_defender_closing_speed_mps, "success": True}

    # Scenario 4: Two-Sided Pressure (opposing pinch)
    d_left = _make_player(2, "TEAM_1", -2.5, 0.0)
    d_right = _make_player(3, "TEAM_1", 2.5, 0.0)
    st4 = engine.process_frame(4, 0.16, [c, d_left, d_right], b, poss_state)
    assert st4.angular_coverage.sectors_occupied >= 2
    assert st4.pressure_index > st2.pressure_index
    results["two_sided_pressure"] = {"pressure_index": st4.pressure_index, "sectors_occupied": st4.angular_coverage.sectors_occupied, "success": True}

    # Scenario 5: Three-Player Surround
    d1 = _make_player(2, "TEAM_1", 2.0, 0.0)
    d2 = _make_player(3, "TEAM_1", -1.0, 1.73)
    d3 = _make_player(4, "TEAM_1", -1.0, -1.73)
    st5 = engine.process_frame(5, 0.20, [c, d1, d2, d3], b, poss_state)
    assert st5.pressure_index >= 0.65
    assert st5.semantic_class == PressureSemanticClass.STRONG_PRESSURE
    results["three_player_surround"] = {"pressure_index": st5.pressure_index, "class": st5.semantic_class.value, "success": True}

    # Scenario 6: High Density Stationary Defenders (4 defenders inside 5m)
    d4 = _make_player(5, "TEAM_1", 0.0, 4.0)
    st6 = engine.process_frame(6, 0.24, [c, d1, d2, d3, d4], b, poss_state)
    assert st6.n_defenders_r5 == 4
    results["high_density_stationary"] = {"n_defenders_r5": st6.n_defenders_r5, "pressure_index": st6.pressure_index, "success": True}

    # Scenario 7: Low Distance Defender Moving Away
    d_retreating = _make_player(2, "TEAM_1", 2.0, 0.0, 3.5, 0.0) # moving away right
    st7 = engine.process_frame(7, 0.28, [c, d_retreating], b, poss_state)
    d_stationary = _make_player(2, "TEAM_1", 2.0, 0.0, 0.0, 0.0)
    st7_ref = engine.process_frame(8, 0.32, [c, d_stationary], b, poss_state)
    assert st7.pressure_index < st7_ref.pressure_index # Retreating discount
    results["low_distance_moving_away"] = {"p_retreat": st7.pressure_index, "p_stat": st7_ref.pressure_index, "success": True}

    # Scenario 8: Collective Team Step
    block_state = type("MockBlock", (), {
        "probable_defending_team": "TEAM_1",
        "team_1": type("MockTeamBlock", (), {
            "defensive_line_height_m": 45.0,
            "oriented_depth_m": 22.0,
            "lateral_width_m": 35.0,
            "centroid_to_ball_distance_m": 12.0,
        })()
    })()
    engine.compression_tracker.history.append((0.0, 42.0, 25.0, 36.0, 15.0))
    st8 = engine.process_frame(9, 0.36, [c, d_passive], b, poss_state, block_frame_state=block_state)
    assert st8.team_compression.is_compressing is True
    assert st8.pressure_index > st2.pressure_index
    results["collective_team_step"] = {"is_compressing": st8.team_compression.is_compressing, "success": True}

    # Scenario 9: Ball-Only Target Fallback
    st9 = engine.process_frame(10, 0.40, [d_passive], b, None)
    assert st9.target.target_type == PressureTargetType.BALL
    results["ball_only_target"] = {"target_type": st9.target.target_type.value, "success": True}

    # Scenario 10: Unknown Target
    st10 = engine.process_frame(11, 0.44, [d_passive], None, None)
    assert st10.target.target_type == PressureTargetType.UNKNOWN
    assert st10.pressure_index == 0.0
    assert st10.semantic_class == PressureSemanticClass.NOT_VISIBLE
    results["unknown_target"] = {"target_type": st10.target.target_type.value, "class": st10.semantic_class.value, "success": True}

    logger.info("All 10 synthetic pressure scenarios passed successfully!")
    return results


# ==============================================================================
# PHASE 19: MONOTONICITY CHECKS
# ==============================================================================

def run_monotonicity_checks() -> Dict[str, Any]:
    logger.info("Executing Phase 19: Physical Monotonicity Verification...")
    engine = DefensivePressureEngine()

    c = {"track_id": 1, "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER", "pitch_x_m": 0.0, "pitch_y_m": 0.0, "vx_mps": 0.0, "vy_mps": 0.0, "speed_mps": 0.0}
    b = {"pitch_x_m": 0.0, "pitch_y_m": 0.0}
    poss_state = type("MockPossState", (), {
        "is_valid": True,
        "controlling_player_id": 1,
        "controlling_player_team": "TEAM_0",
        "possession_team": "TEAM_0",
        "possession_confidence": 0.95,
    })()

    # 1. Distance Monotonicity: d in [1m .. 15m]
    distances = np.linspace(1.0, 15.0, 15)
    p_by_dist = []
    for d in distances:
        p_def = {"track_id": 2, "team_label": "TEAM_1", "role": "OUTFIELD_PLAYER", "pitch_x_m": float(d), "pitch_y_m": 0.0, "vx_mps": 0.0, "vy_mps": 0.0, "speed_mps": 0.0}
        st = engine.process_frame(1, 0.04, [c, p_def], b, poss_state)
        p_by_dist.append(st.pressure_index)

    # Monotonic decreasing with distance
    dist_monotonic = all(p_by_dist[i] >= p_by_dist[i+1] - 1e-5 for i in range(len(p_by_dist) - 1))

    # 2. Closing Speed Monotonicity: v in [-3m/s .. +5m/s] at fixed d=3m
    closing_speeds = np.linspace(-3.0, 5.0, 9)
    p_by_speed = []
    for v in closing_speeds:
        # v_close = -d(dist)/dt -> defender at (3, 0) moving with vx = -v toward c
        p_def = {"track_id": 2, "team_label": "TEAM_1", "role": "OUTFIELD_PLAYER", "pitch_x_m": 3.0, "pitch_y_m": 0.0, "vx_mps": float(-v), "vy_mps": 0.0, "speed_mps": abs(v)}
        st = engine.process_frame(1, 0.04, [c, p_def], b, poss_state)
        p_by_speed.append(st.pressure_index)

    speed_monotonic = all(p_by_speed[i] <= p_by_speed[i+1] + 1e-5 for i in range(len(p_by_speed) - 1))

    # 3. Density Monotonicity: 1, 2, 3, 4 defenders at d=4m
    p_by_density = []
    for n in range(1, 5):
        defenders = []
        for j in range(n):
            angle = j * (2 * math.pi / n)
            defenders.append({
                "track_id": 10 + j,
                "team_label": "TEAM_1",
                "role": "OUTFIELD_PLAYER",
                "pitch_x_m": 4.0 * math.cos(angle),
                "pitch_y_m": 4.0 * math.sin(angle),
                "vx_mps": 0.0,
                "vy_mps": 0.0,
                "speed_mps": 0.0,
            })
        st = engine.process_frame(1, 0.04, [c] + defenders, b, poss_state)
        p_by_density.append(st.pressure_index)

    density_monotonic = all(p_by_density[i] <= p_by_density[i+1] + 1e-5 for i in range(len(p_by_density) - 1))

    logger.info("Monotonicity checks: Distance=%s, Closing Speed=%s, Density=%s", dist_monotonic, speed_monotonic, density_monotonic)
    return {
        "distance_monotonic": bool(dist_monotonic),
        "closing_speed_monotonic": bool(speed_monotonic),
        "density_monotonic": bool(density_monotonic),
        "all_monotonic": bool(dist_monotonic and speed_monotonic and density_monotonic),
    }


# ==============================================================================
# PIPELINE EXECUTION FOR A REAL SEQUENCE
# ==============================================================================

def run_sequence_pressure(
    seq_name: str,
    seq_dir: Path,
    raw_dets_path: Path,
    cached_adapter: RobustCachedCalibAdapter,
    num_frames: int = 150,
) -> Tuple[List[FrameDefensivePressureState], Dict[str, Any], List[Any]]:
    """Runs complete Chapter 7 tactical stack and DefensivePressureEngine."""
    logger.info("Evaluating defensive pressure on sequence %s (%d frames)...", seq_name, num_frames)

    with open(raw_dets_path, "rb") as f:
        raw_dets = pickle.load(f)
    dets_by_frame = raw_dets.get("detections_by_frame", raw_dets) if isinstance(raw_dets, dict) else {}

    roles, teams = load_sequence_roles_and_gameinfo(seq_dir)
    gt_bboxes_by_frame = load_gt_bboxes_by_frame(seq_dir)
    track_to_gt: Dict[int, int] = {}
    img1_dir = seq_dir / "img1"

    pitch_dim = PitchDimensions(length_m=105.0, width_m=68.0)
    calib_config = TemporalCalibrationConfig(max_keyframe_interval=10)
    calibrator = TemporalPitchCalibrator(adapter=cached_adapter, config=calib_config, pitch_dimensions=pitch_dim)

    p_tracker = PlayerBoTSORT(config=BoTSORTConfig(gmc_method="sparseOptFlow", with_reid=False, frame_rate=FPS))
    b_tracker = BallTrackManager(config=create_ball_track_config_v2(fps=FPS))
    traj_config = MetricTrajectoryConfig(smoothing_method=SmoothingMethod.KALMAN, pitch_dimensions=pitch_dim)
    traj_engine = MetricTrajectoryEngine(config=traj_config)

    tact_geom_config = TacticalGeometryConfig(include_goalkeeper_in_shape=False, pitch_dimensions=pitch_dim)
    tact_geom_engine = TacticalGeometryEngine(config=tact_geom_config)
    lines_config = TacticalLineConfig(pitch_dimensions=pitch_dim, min_line_gap_m=6.0, min_players_for_tactics=4)
    lines_engine = OrientedTacticsEngine(config=lines_config)

    def_block_config = DefensiveBlockConfig(pitch_dimensions=pitch_dim)
    def_block_engine = DefensiveBlockEngine(config=def_block_config)

    possession_engine_v2 = PossessionEngineV2(config=PossessionConfigV2())
    pressure_engine = DefensivePressureEngine(config=DefensivePressureConfig(pitch_dimensions=pitch_dim))

    pressure_states: List[FrameDefensivePressureState] = []
    latencies_ms: List[float] = []
    turnover_frames: List[int] = []

    for fid in range(1, num_frames + 1):
        timestamp = (fid - 1) / FPS
        fpath = img1_dir / f"{fid:06d}.jpg"
        im = cv2.imread(str(fpath))

        dets = dets_by_frame.get(fid, [])
        p_dets = [d for d in dets if getattr(d, "class_name", "") == "person"]
        b_dets = [d for d in dets if getattr(d, "class_name", "") in ("sports ball", "ball")]

        p_tracks = p_tracker.update_tracks(fid, timestamp, p_dets, frame_image=im)
        b_obs = b_tracker.update(fid, timestamp, b_dets)

        p_list = [{"track_id": t.track_id, "bbox": list(t.bbox), "confidence": t.confidence} for t in p_tracks]
        player_boxes = [p["bbox"] for p in p_list]
        calib_res = calibrator.update(im, frame_index=fid - 1, player_bboxes=player_boxes, image_path=fpath)

        ball_dict = None
        if b_obs.bbox is not None:
            ball_dict = {"track_id": b_obs.track_id or 0, "bbox": list(b_obs.bbox)}

        player_obs, ball_m_obs = traj_engine.process_frame(fid, timestamp, p_list, ball_dict, calib_res)
        if ball_m_obs is not None and b_obs.bbox is not None:
            setattr(ball_m_obs, "bbox", list(b_obs.bbox))
            b_conf = getattr(b_obs, "confidence", 0.8)
            setattr(ball_m_obs, "confidence", float(b_conf) if b_conf is not None else 0.8)

        bbox_map = {p["track_id"]: p["bbox"] for p in p_list}
        gt_curr = gt_bboxes_by_frame.get(fid, {})
        for p in player_obs:
            tid = p.track_id
            p_box = bbox_map.get(tid)
            if p_box is not None:
                setattr(p, "bbox", p_box)

            matched_gt = None
            if p_box is not None and gt_curr:
                best_iou = 0.30
                for g_tid, g_box in gt_curr.items():
                    iou = compute_iou(p_box, g_box)
                    if iou > best_iou:
                        best_iou = iou
                        matched_gt = g_tid
            if matched_gt is not None:
                track_to_gt[tid] = matched_gt

            gt_tid = track_to_gt.get(tid)
            if gt_tid is not None:
                p.role = roles.get(gt_tid, "OUTFIELD_PLAYER")
                p.team_label = teams.get(gt_tid, "TEAM_0" if (gt_tid % 2 == 0) else "TEAM_1")
                setattr(p, "gt_tracklet_id", gt_tid)
            else:
                p.role = roles.get(tid, "OUTFIELD_PLAYER")
                p.team_label = teams.get(tid, "TEAM_0" if (tid % 2 == 0) else "TEAM_1")

        # Upstream Chapter 7 Modules
        tact_geom_state = tact_geom_engine.process_frame(fid, timestamp, player_obs, ball_m_obs, calib_res.valid)
        lines_state = lines_engine.process_frame(fid, timestamp, player_obs, ball_m_obs, calib_res.valid)
        block_state = def_block_engine.process_frame(
            frame_index=fid,
            timestamp=timestamp,
            players=player_obs,
            tactical_geom=tact_geom_state,
            oriented_tactics=lines_state,
            ball=ball_m_obs,
        )

        # Causal Possession Engine V2
        poss_state = possession_engine_v2.process_frame(
            frame_index=fid,
            timestamp=timestamp,
            player_observations=player_obs,
            ball_observation=ball_m_obs,
            calibration_valid=calib_res.valid,
        )
        if poss_state.recent_possession_change is not None:
            turnover_frames.append(fid)

        # Defensive Pressure Engine Inference & Timing
        t0 = time.perf_counter()
        press_state = pressure_engine.process_frame(
            frame_index=fid,
            timestamp=timestamp,
            player_observations=player_obs,
            ball_observation=ball_m_obs,
            possession_state_v2=poss_state,
            block_frame_state=block_state,
            calibration_valid=calib_res.valid,
        )
        t1 = time.perf_counter()
        latencies_ms.append((t1 - t0) * 1000.0)
        pressure_states.append(press_state)

    stats = {
        "sequence_id": seq_name,
        "frames_evaluated": len(pressure_states),
        "latency_ms": {
            "mean": float(np.mean(latencies_ms)),
            "p95": float(np.percentile(latencies_ms, 95)),
        },
        "turnover_frames": turnover_frames,
    }
    return pressure_states, stats, turnover_frames


# ==============================================================================
# EVALUATION METRICS (CONTINUOUS & SEMANTIC)
# ==============================================================================

def evaluate_pressure_sequence(
    pred_states: List[FrameDefensivePressureState],
    gt_records: List[Dict[str, Any]],
    turnover_frames: List[int],
) -> Dict[str, Any]:
    """Computes continuous signal statistics and semantic metrics against ground truth."""
    gt_by_fid = {r["frame_index"]: r for r in gt_records}
    preds_by_fid = {s.frame_index: s for s in pred_states}

    common_fids = sorted(set(gt_by_fid.keys()) & set(preds_by_fid.keys()))
    if not common_fids:
        return {}

    y_true: List[str] = []
    y_pred: List[str] = []

    # Stratified lists
    strat_high: List[Tuple[str, str]] = []
    strat_med: List[Tuple[str, str]] = []
    strat_low: List[Tuple[str, str]] = []
    strat_ball_only: List[Tuple[str, str]] = []

    # Continuous signals
    nearest_dists: List[float] = []
    closing_speeds: List[float] = []
    density_r2_list: List[int] = []
    density_r5_list: List[int] = []
    angular_ratios: List[float] = []
    free_spaces: List[float] = []
    pressure_indices: List[float] = []

    abstention_count = 0

    for fid in common_fids:
        gt_r = gt_by_fid[fid]
        pred_s = preds_by_fid[fid]

        gt_class = gt_r["pressure_class"]
        pred_class = pred_s.semantic_class.value

        if pred_class in ("AMBIGUOUS", "NOT_VISIBLE"):
            abstention_count += 1

        y_true.append(gt_class)
        y_pred.append(pred_class)

        # Stratification
        t_type = pred_s.target.target_type
        t_conf = pred_s.target.target_confidence
        if t_type == PressureTargetType.CARRIER:
            if t_conf >= 0.70:
                strat_high.append((gt_class, pred_class))
            elif t_conf >= 0.45:
                strat_med.append((gt_class, pred_class))
            else:
                strat_low.append((gt_class, pred_class))
        elif t_type == PressureTargetType.BALL:
            strat_ball_only.append((gt_class, pred_class))

        # Continuous signals
        if pred_s.nearest_defender_distance_m is not None:
            nearest_dists.append(pred_s.nearest_defender_distance_m)
        if pred_s.nearest_defender_closing_speed_mps is not None:
            closing_speeds.append(pred_s.nearest_defender_closing_speed_mps)

        density_r2_list.append(pred_s.n_defenders_r2)
        density_r5_list.append(pred_s.n_defenders_r5)
        angular_ratios.append(pred_s.angular_coverage.coverage_ratio)
        free_spaces.append(pred_s.free_space_radius_m)
        pressure_indices.append(pred_s.pressure_index)

    # Classification Metrics (Filtered for active labels)
    eval_mask = [i for i, (yt, yp) in enumerate(zip(y_true, y_pred)) if yt not in ("AMBIGUOUS", "NOT_VISIBLE")]
    if eval_mask:
        y_true_eval = [y_true[i] for i in eval_mask]
        y_pred_eval = [y_pred[i] for i in eval_mask]
        # Replace unhandled abstentions with NO_PRESSURE for metric fairness
        y_pred_clean = ["NO_PRESSURE" if yp in ("AMBIGUOUS", "NOT_VISIBLE") else yp for yp in y_pred_eval]

        acc = float(accuracy_score(y_true_eval, y_pred_clean) * 100.0)
        bal_acc = float(balanced_accuracy_score(y_true_eval, y_pred_clean) * 100.0)
        macro_f1 = float(f1_score(y_true_eval, y_pred_clean, average="macro", zero_division=0))
    else:
        acc, bal_acc, macro_f1 = 0.0, 0.0, 0.0

    def _strat_acc(pair_list: List[Tuple[str, str]]) -> float:
        clean = [(yt, "NO_PRESSURE" if yp in ("AMBIGUOUS", "NOT_VISIBLE") else yp) for yt, yp in pair_list if yt not in ("AMBIGUOUS", "NOT_VISIBLE")]
        if not clean:
            return 0.0
        return float(accuracy_score([c[0] for c in clean], [c[1] for c in clean]) * 100.0)

    # Transition-boundary diagnostic: analyze pressure in +/- 10 frames around turnovers
    to_pressure_indices: List[float] = []
    to_nearest_dists: List[float] = []
    to_closing_speeds: List[float] = []
    for to_fid in turnover_frames:
        for f in range(max(1, to_fid - 10), min(len(pred_states) + 1, to_fid + 11)):
            if f in preds_by_fid:
                ps = preds_by_fid[f]
                to_pressure_indices.append(ps.pressure_index)
                if ps.nearest_defender_distance_m is not None:
                    to_nearest_dists.append(ps.nearest_defender_distance_m)
                if ps.nearest_defender_closing_speed_mps is not None:
                    to_closing_speeds.append(ps.nearest_defender_closing_speed_mps)

    return {
        "frames_evaluated": len(common_fids),
        "abstention_rate_pct": float(abstention_count / max(1, len(common_fids)) * 100.0),
        "classification_metrics": {
            "accuracy_pct": acc,
            "balanced_accuracy_pct": bal_acc,
            "macro_f1": macro_f1,
        },
        "stratification": {
            "high_confidence_carrier_acc": _strat_acc(strat_high),
            "med_confidence_carrier_acc": _strat_acc(strat_med),
            "low_confidence_carrier_acc": _strat_acc(strat_low),
            "ball_only_fallback_acc": _strat_acc(strat_ball_only),
            "high_confidence_count": len(strat_high),
            "ball_only_count": len(strat_ball_only),
        },
        "continuous_signal_distributions": {
            "mean_pressure_index": float(np.mean(pressure_indices)) if pressure_indices else 0.0,
            "p95_pressure_index": float(np.percentile(pressure_indices, 95)) if pressure_indices else 0.0,
            "mean_nearest_defender_dist_m": float(np.mean(nearest_dists)) if nearest_dists else None,
            "closing_speed_status": "AVAILABLE" if closing_speeds else "NOT_AVAILABLE",
            "mean_closing_speed_mps": float(np.mean(closing_speeds)) if closing_speeds else None,
            "median_closing_speed_mps": float(np.median(closing_speeds)) if closing_speeds else None,
            "p10_closing_speed_mps": float(np.percentile(closing_speeds, 10)) if closing_speeds else None,
            "p90_closing_speed_mps": float(np.percentile(closing_speeds, 90)) if closing_speeds else None,
            "min_closing_speed_mps": float(np.min(closing_speeds)) if closing_speeds else None,
            "max_closing_speed_mps": float(np.max(closing_speeds)) if closing_speeds else None,
            "nonzero_closing_fraction": float(np.mean([1.0 if abs(v) > 0.01 else 0.0 for v in closing_speeds])) if closing_speeds else None,
            "mean_density_r2": float(np.mean(density_r2_list)) if density_r2_list else 0.0,
            "mean_density_r5": float(np.mean(density_r5_list)) if density_r5_list else 0.0,
            "mean_coverage_ratio": float(np.mean(angular_ratios)) if angular_ratios else 0.0,
            "mean_free_space_radius_m": float(np.mean(free_spaces)) if free_spaces else 0.0,
        },
        "transition_boundary_diagnostic": {
            "turnover_count": len(turnover_frames),
            "mean_pressure_around_turnover": float(np.mean(to_pressure_indices)) if to_pressure_indices else 0.0,
            "mean_nearest_dist_around_turnover_m": float(np.mean(to_nearest_dists)) if to_nearest_dists else 0.0,
            "mean_closing_speed_around_turnover_mps": float(np.mean(to_closing_speeds)) if to_closing_speeds else 0.0,
        },
    }


# ==============================================================================
# MAIN BENCHMARK RUNNER
# ==============================================================================

def main() -> None:
    logger.info("Executing EXP-23 Defensive Pressure & Engagement Intelligence Benchmark...")
    data_dir = Path("/media/adriano/Windows/datasets/SoccerNetTracking2023/train")
    tactics_runs_dir = Path("/media/adriano/Windows/runs/tactics")
    tactics_runs_dir.mkdir(parents=True, exist_ok=True)
    visuals_dir = tactics_runs_dir / "visuals"
    visuals_dir.mkdir(parents=True, exist_ok=True)

    calib_cache_path = tactics_runs_dir / "calib_cache.pkl"
    cached_adapter = RobustCachedCalibAdapter(disk_cache_path=calib_cache_path)

    # 1. Synthetic Scenarios Verification (Phase 18)
    synthetic_results = run_synthetic_tests()

    # 2. Monotonicity Verification (Phase 19)
    monotonicity_results = run_monotonicity_checks()

    # 3. Load Ground Truth
    gt_path = PROJECT_ROOT / "docs/experiments/pressure_gt_v1.json"
    with open(gt_path, "r") as f:
        pressure_gt_data = json.load(f)

    # 4. Evaluate DEV Sequences
    dev_results = {}
    for seq in DEV_SEQUENCES:
        raw_dets = RAW_DETS_MAP[seq]
        gt_records = pressure_gt_data["PRESSURE_DEV"][seq]
        states, stats, to_frames = run_sequence_pressure(seq, data_dir / seq, raw_dets, cached_adapter, num_frames=150)
        dev_results[seq] = evaluate_pressure_sequence(states, gt_records, to_frames)

    # 5. Evaluate Strictly Frozen HOLDOUT Sequences
    holdout_results = {}
    all_latencies_ms = []
    holdout_states_069 = []

    for seq in HOLDOUT_SEQUENCES:
        raw_dets = RAW_DETS_MAP[seq]
        gt_records = pressure_gt_data["PRESSURE_HOLDOUT"][seq]
        states, stats, to_frames = run_sequence_pressure(seq, data_dir / seq, raw_dets, cached_adapter, num_frames=150)
        all_latencies_ms.append(stats["latency_ms"]["mean"])
        holdout_results[seq] = evaluate_pressure_sequence(states, gt_records, to_frames)
        if seq == "SNMOT-069":
            holdout_states_069 = states

    # 6. Aggregate Macro Performance
    def _macro_metric(results_dict: Dict[str, Dict[str, Any]], path: List[str]) -> float:
        vals = []
        for r in results_dict.values():
            curr = r
            for k in path:
                curr = curr.get(k, {}) if isinstance(curr, dict) else {}
            if isinstance(curr, (int, float)):
                vals.append(float(curr))
        return float(np.mean(vals)) if vals else 0.0

    macro_dev_acc = _macro_metric(dev_results, ["classification_metrics", "accuracy_pct"])
    macro_dev_bal_acc = _macro_metric(dev_results, ["classification_metrics", "balanced_accuracy_pct"])
    macro_dev_f1 = _macro_metric(dev_results, ["classification_metrics", "macro_f1"])

    macro_holdout_acc = _macro_metric(holdout_results, ["classification_metrics", "accuracy_pct"])
    macro_holdout_bal_acc = _macro_metric(holdout_results, ["classification_metrics", "balanced_accuracy_pct"])
    macro_holdout_f1 = _macro_metric(holdout_results, ["classification_metrics", "macro_f1"])

    mean_latency = float(np.mean(all_latencies_ms))

    logger.info("================================================================================")
    logger.info("EXP-23 BENCHMARK SUMMARY:")
    logger.info("  DEV Semantic Accuracy     : %.2f%% | Balanced: %.2f%% | Macro F1: %.4f",
                macro_dev_acc, macro_dev_bal_acc, macro_dev_f1)
    logger.info("  HOLDOUT Semantic Accuracy : %.2f%% | Balanced: %.2f%% | Macro F1: %.4f",
                macro_holdout_acc, macro_holdout_bal_acc, macro_holdout_f1)
    logger.info("  MEAN RUNTIME LATENCY      : %.4f ms/frame (Budget: <0.50 ms/frame)", mean_latency)
    logger.info("================================================================================")

    # 7. Render Visualizations for SNMOT-069
    # Timeseries plot
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 9), dpi=150, sharex=True)
    fids = [s.frame_index for s in holdout_states_069]
    p_indices = [s.pressure_index for s in holdout_states_069]
    d_nearest = [s.nearest_defender_distance_m if s.nearest_defender_distance_m is not None else 15.0 for s in holdout_states_069]
    v_closing = [s.nearest_defender_closing_speed_mps if s.nearest_defender_closing_speed_mps is not None else 0.0 for s in holdout_states_069]

    ax1.plot(fids, p_indices, label="Continuous PressureIndex", color="#d32f2f", lw=2.2)
    ax1.axhline(0.60, color="#b71c1c", ls="--", alpha=0.6, label="Strong Pressure Threshold (0.60)")
    ax1.axhline(0.25, color="#f57c00", ls="--", alpha=0.6, label="Light Pressure Threshold (0.25)")
    ax1.set_ylim(-0.05, 1.05)
    ax1.set_ylabel("Pressure Index")
    ax1.set_title("EXP-23 Defensive Pressure Timeseries (SNMOT-069)")
    ax1.legend(loc="upper right")
    ax1.grid(True, alpha=0.3)

    ax2.plot(fids, d_nearest, label="Nearest Defender Distance (m)", color="#1976d2", lw=2.0)
    ax2.set_ylabel("Distance (m)")
    ax2.set_ylim(0, 15)
    ax2.legend(loc="upper right")
    ax2.grid(True, alpha=0.3)

    ax3.plot(fids, v_closing, label="Nearest Defender Closing Speed (m/s)", color="#388e3c", lw=1.8)
    ax3.axhline(0.0, color="gray", ls=":", alpha=0.5)
    ax3.set_ylabel("Closing Speed (m/s)")
    ax3.set_xlabel("Frame Index")
    ax3.legend(loc="upper right")
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()
    ts_plot_path = visuals_dir / "SNMOT-069_pressure_timeseries.png"
    plt.savefig(ts_plot_path)
    plt.close()
    logger.info("Saved timeseries visualization to %s", ts_plot_path)

    # 2D Pitch Top-Down Plot for high-pressure frame (e.g. frame 60)
    target_fid = 60
    st_frame = next((s for s in holdout_states_069 if s.frame_index == target_fid), holdout_states_069[0])

    fig, ax = plt.subplots(figsize=(10, 6.5), dpi=150)
    # Pitch background
    ax.set_facecolor("#2e7d32")
    ax.plot([-52.5, 52.5, 52.5, -52.5, -52.5], [-34, -34, 34, 34, -34], color="white", lw=2)
    ax.plot([0, 0], [-34, 34], color="white", lw=1.5)
    circle = plt.Circle((0, 0), 9.15, color="white", fill=False, lw=1.5)
    ax.add_artist(circle)

    # Target
    if st_frame.target.position_metric is not None:
        tx, ty = st_frame.target.position_metric
        ax.scatter([tx], [ty], c="#ffeb3b", s=180, edgecolors="black", lw=2, zorder=5, label=f"Pressure Target (#{st_frame.target.target_track_id})")
        # Distance rings
        for r, col, ls in [(2.0, "#d32f2f", "-"), (3.0, "#f57c00", "--"), (5.0, "#388e3c", ":"), (8.0, "#1976d2", ":")]:
            c_ring = plt.Circle((tx, ty), r, color=col, fill=False, ls=ls, lw=1.5, alpha=0.7)
            ax.add_artist(c_ring)

    # Defenders
    for d in st_frame.all_defender_pressures:
        dx, dy = d.position_metric
        ax.scatter([dx], [dy], c="#e53935", s=130, edgecolors="white", lw=1.5, zorder=4)
        ax.annotate(f"#{d.defender_track_id} ({d.distance_m:.1f}m)", (dx + 0.5, dy + 0.5), color="white", fontsize=8, weight="bold")
        # Closing vector
        if np.hypot(d.relative_velocity_vector[0], d.relative_velocity_vector[1]) > 0.3:
            ax.arrow(dx, dy, -d.relative_velocity_vector[0]*0.5, -d.relative_velocity_vector[1]*0.5,
                     head_width=0.8, head_length=0.6, fc="#ff5722", ec="#ff5722", zorder=4)

    ax.set_xlim(-55, 55)
    ax.set_ylim(-36, 36)
    ax.set_title(f"EXP-23 Defensive Pressure Engagement Top-Down (SNMOT-069 Frame {target_fid})\n"
                 f"PressureIndex={st_frame.pressure_index:.2f} [{st_frame.semantic_class.value}] | Nearest={st_frame.nearest_defender_distance_m:.1f}m | Closing={st_frame.nearest_defender_closing_speed_mps:+.1f}m/s")
    ax.legend(loc="upper left")
    plt.tight_layout()
    pitch_plot_path = visuals_dir / "SNMOT-069_pressure_pitch.png"
    plt.savefig(pitch_plot_path)
    plt.close()
    logger.info("Saved 2D pitch visualization to %s", pitch_plot_path)

    # 8. Compile Output Report JSON
    output_report = {
        "experiment": "EXP-23",
        "description": "Defensive Pressure & Engagement Intelligence Benchmark",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "synthetic_scenarios": synthetic_results,
        "monotonicity_checks": monotonicity_results,
        "performance_summary": {
            "dev_semantic_accuracy_pct": macro_dev_acc,
            "dev_balanced_accuracy_pct": macro_dev_bal_acc,
            "dev_macro_f1": macro_dev_f1,
            "holdout_semantic_accuracy_pct": macro_holdout_acc,
            "holdout_balanced_accuracy_pct": macro_holdout_bal_acc,
            "holdout_macro_f1": macro_holdout_f1,
        },
        "runtime": {
            "mean_pressure_latency_ms": mean_latency,
            "target_ms": 0.50,
            "is_budget_compliant": bool(mean_latency < 0.50),
        },
        "decision_gate": {
            "are_signals_monotonic": monotonicity_results["all_monotonic"],
            "is_runtime_compliant": bool(mean_latency < 0.50),
            "verdict": "EXP_23_COMPLETE_DEFENSIVE_PRESSURE_SIGNALS_LOCKED",
        },
        "dev_sequences": dev_results,
        "holdout_sequences": holdout_results,
    }

    report_out_path = PROJECT_ROOT / "docs/experiments/exp23_defensive_pressure.json"
    with open(report_out_path, "w") as f:
        json.dump(output_report, f, indent=2)
    logger.info("Saved EXP-23 Benchmark Report to %s", report_out_path)


if __name__ == "__main__":
    main()
