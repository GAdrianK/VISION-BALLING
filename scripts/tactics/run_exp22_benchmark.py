#!/usr/bin/env python3
"""EXP-22: Ball Control & Possession V2 Benchmark Runner.

Executes comprehensive scientific validation comparing:
- Historical Baseline: PossessionEngine V1 (EXP-18)
- Challenger Engine: PossessionEngine V2 (EXP-22)
- Oracle Control Diagnostic

Evaluates:
1. Synthetic possession scenarios (acquisition, pass handoff, opponent takeover, contested duel, ID switch, aerial).
2. Sequence-level isolated benchmark across:
   - DEV: SNMOT-060, SNMOT-063, SNMOT-064
   - HOLDOUT: SNMOT-066, SNMOT-068, SNMOT-069, SNMOT-070, SNMOT-071
3. Player Control & Team Possession metrics:
   - Carrier accuracy, top-2 recall, carrier coverage
   - Team possession accuracy, balanced accuracy, macro F1, coverage, abstention rate
   - Temporal stability: state switches/min, false short acquisitions, mean control duration
4. Transition-Boundary metrics (+-10 frames around control changes).
5. Downstream frozen EXP-19 Pass Event transfer diagnostic:
   - Mode A: V1 control -> PassEventDetector
   - Mode B: V2 control -> PassEventDetector
   - Mode C: Oracle control -> PassEventDetector
6. Incremental runtime latency profiling (<0.50 ms/frame budget).
7. Visualization plots and docs/experiments/exp22_possession_v2.json export.
"""

from __future__ import annotations

import configparser
import json
import logging
import os
import pickle
import platform
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np

# Ensure project backend is on sys.path
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
    AttackDirection,
    OrientedTacticsEngine,
    TacticalLineConfig,
)
from app.video_analysis.possession import (
    BallControlState,
    PossessionConfig,
    PossessionEngine,
    PossessionStatus,
    TeamPossessionFrameState,
)
from app.video_analysis.possession_v2 import (
    BallControlEstimatorV2,
    PairwiseControlModel,
    PlayerControlCandidateV2,
    PossessionConfigV2,
    PossessionEngineV2,
)
from app.video_analysis.pass_detector import (
    PassDetectorConfig,
    PassEvent,
    PassEventDetector,
    PassEventType,
    PassFrameState,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("EXP-22-BENCHMARK")

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
# PHASE 20: SYNTHETIC TESTS RUNNER
# ==============================================================================

def run_synthetic_tests() -> Dict[str, Any]:
    """Verifies state machine and scoring behavior across deterministic fixtures."""
    logger.info("Executing Phase 20 Synthetic State Machine Scenarios on V2...")
    engine = PossessionEngineV2()
    results = {}

    p_t0_a = {"track_id": 1, "bbox": [100, 400, 200, 600], "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"}
    p_t0_b = {"track_id": 2, "bbox": [500, 400, 600, 600], "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"}
    p_t1_a = {"track_id": 10, "bbox": [800, 400, 900, 600], "team_label": "TEAM_1", "role": "OUTFIELD_PLAYER"}

    ball_at_p0 = {"bbox": [120, 580, 130, 590], "confidence": 0.90}
    ball_in_transit = {"bbox": [350, 300, 360, 310], "confidence": 0.85}
    ball_at_p1 = {"bbox": [820, 580, 830, 590], "confidence": 0.90}

    # 1. Acquisition (2 frames confirmed)
    engine.reset()
    f1 = engine.process_frame(1, 0.04, [p_t0_a], ball_at_p0)
    f2 = engine.process_frame(2, 0.08, [p_t0_a], ball_at_p0)
    results["acquisition"] = {
        "status": f2.possession_status.value,
        "team": f2.possession_team,
        "carrier_id": f2.controlling_player_id,
        "success": (f2.possession_status == PossessionStatus.SECURE and f2.possession_team == "TEAM_0" and f2.controlling_player_id == 1),
    }

    # 2. Same-team handoff (pass transit)
    f3 = engine.process_frame(3, 0.12, [p_t0_a, p_t0_b], ball_in_transit)
    results["same_team_handoff"] = {
        "transit_status": f3.possession_status.value,
        "possession_team": f3.possession_team,
        "success": (f3.possession_status == PossessionStatus.PROVISIONAL_TRANSIT and f3.possession_team == "TEAM_0"),
    }

    # 3. Opponent takeover (turnover)
    for fid in range(4, 7):
        f_takeover = engine.process_frame(fid, fid * 0.04, [p_t0_a, p_t1_a], ball_at_p1)
    results["opponent_takeover"] = {
        "final_team": f_takeover.possession_team,
        "turnovers_emitted": len(engine.turnover_events),
        "success": (f_takeover.possession_team == "TEAM_1" and len(engine.turnover_events) == 1),
    }

    # 4. Contested duel
    engine.reset()
    p_duel_0 = {"track_id": 1, "bbox": [400, 400, 500, 600], "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"}
    p_duel_1 = {"track_id": 10, "bbox": [450, 400, 550, 600], "team_label": "TEAM_1", "role": "OUTFIELD_PLAYER"}
    ball_duel = {"bbox": [470, 580, 480, 590], "confidence": 0.90}
    f_duel = engine.process_frame(1, 0.04, [p_duel_0, p_duel_1], ball_duel)
    results["contested_duel"] = {
        "control_state": f_duel.control_state.value,
        "possession_team": f_duel.possession_team,
        "success": (f_duel.control_state == BallControlState.CONTESTED and f_duel.possession_team == "CONTESTED"),
    }

    # 5. Tracker ID switch robustness
    engine.reset()
    for i in range(1, 3):
        engine.process_frame(i, i * 0.04, [p_t0_a], ball_at_p0)
    p_t0_switched = {"track_id": 999, "bbox": [400, 400, 500, 600], "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"}
    to_count_before = len(engine.turnover_events)
    f_switch = engine.process_frame(3, 0.12, [p_t0_switched], ball_at_p0)
    to_emitted = len(engine.turnover_events) - to_count_before
    results["id_switch_robustness"] = {
        "possession_team": f_switch.possession_team,
        "turnovers_emitted": to_emitted,
        "success": (f_switch.possession_team == "TEAM_0" and to_emitted == 0),
    }

    # 6. Aerial speed jump invalidation
    engine.reset()
    ball_ground_jump = {
        "bbox": [420, 580, 430, 590],
        "pitch_x_m": 0.0,
        "pitch_y_m": 0.0,
        "confidence": 0.9,
    }
    engine.process_frame(1, 0.04, [p_t0_a], ball_ground_jump, calibration_valid=True)
    # Extreme leap in ground projection (>30 m/s jump)
    ball_ground_jump_2 = {
        "bbox": [420, 580, 430, 590],
        "pitch_x_m": 15.0,
        "pitch_y_m": 10.0,
        "confidence": 0.9,
    }
    f_jump = engine.process_frame(2, 0.08, [p_t0_a], ball_ground_jump_2, calibration_valid=True)
    results["aerial_jump_invalidation"] = {
        "is_aerial_suspect": f_jump.details.get("is_aerial_suspect", False),
        "success": bool(f_jump.details.get("is_aerial_suspect", False)),
    }

    all_passed = all(r["success"] for r in results.values())
    assert all_passed, f"Synthetic state tests failed: {results}"
    logger.info("Phase 20 Passed: All synthetic possession state scenarios verified.")
    return results


# ==============================================================================
# PIPELINE EXECUTION FOR SINGLE SEQUENCE
# ==============================================================================

def run_sequence_dual_engines(
    seq_name: str,
    seq_dir: Path,
    raw_dets_path: Path,
    cached_adapter: RobustCachedCalibAdapter,
    num_frames: int = 150,
) -> Tuple[List[TeamPossessionFrameState], List[TeamPossessionFrameState], Dict[str, Any], List[Any], List[Any]]:
    """Runs V1 and V2 on the exact same frame observations and tracks timing."""
    logger.info("Evaluating sequence %s on V1 and V2 (%d frames)...", seq_name, num_frames)

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

    # Initialize engines
    engine_v1 = PossessionEngine(config=PossessionConfig())
    engine_v2 = PossessionEngineV2(config=PossessionConfigV2())

    frames_v1: List[TeamPossessionFrameState] = []
    frames_v2: List[TeamPossessionFrameState] = []
    latencies_v1_ms: List[float] = []
    latencies_v2_ms: List[float] = []

    player_obs_history = []
    ball_obs_history = []
    calib_history = []

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

        player_obs_history.append(player_obs)
        ball_obs_history.append(ball_m_obs)
        calib_history.append(calib_res)

        # Execute V1
        t0 = time.perf_counter()
        st_v1 = engine_v1.process_frame(fid, timestamp, player_obs, ball_m_obs, calib_res.valid)
        t1 = time.perf_counter()
        latencies_v1_ms.append((t1 - t0) * 1000.0)
        frames_v1.append(st_v1)

        # Execute V2
        t2 = time.perf_counter()
        st_v2 = engine_v2.process_frame(fid, timestamp, player_obs, ball_m_obs, calib_res.valid)
        t3 = time.perf_counter()
        latencies_v2_ms.append((t3 - t2) * 1000.0)
        frames_v2.append(st_v2)

    stats = {
        "sequence_id": seq_name,
        "frames_evaluated": len(frames_v1),
        "v1_latency_ms": {
            "mean": float(np.mean(latencies_v1_ms)),
            "p95": float(np.percentile(latencies_v1_ms, 95)),
        },
        "v2_latency_ms": {
            "mean": float(np.mean(latencies_v2_ms)),
            "p95": float(np.percentile(latencies_v2_ms, 95)),
        },
    }
    return frames_v1, frames_v2, stats, player_obs_history, ball_obs_history


# ==============================================================================
# PHASE 12 & 13: EVALUATION METRICS AGAINST GROUND TRUTH
# ==============================================================================

def evaluate_possession_predictions(
    pred_frames: List[TeamPossessionFrameState],
    gt_records: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Computes frame accuracy, carrier accuracy, stability, and transition boundary metrics."""
    gt_by_fid = {r["frame_index"]: r for r in gt_records}
    preds_by_fid = {f.frame_index: f for f in pred_frames}

    common_fids = sorted(set(gt_by_fid.keys()) & set(preds_by_fid.keys()))
    if not common_fids:
        return {}

    correct_team = 0
    valid_count = 0
    carrier_correct = 0
    carrier_gt_total = 0

    gt_team_counts: Dict[str, int] = {}
    pred_team_counts: Dict[str, int] = {}
    tp_by_team: Dict[str, int] = {}

    # Event boundary evaluation (+-10 frames around GT control state transitions)
    gt_transition_frames = set()
    prev_state = None
    for fid in common_fids:
        curr_state = gt_by_fid[fid].get("player_control_state")
        if prev_state is not None and curr_state != prev_state:
            for f in range(max(1, fid - 10), min(max(common_fids), fid + 10) + 1):
                gt_transition_frames.add(f)
        prev_state = curr_state

    boundary_team_correct = 0
    boundary_team_total = 0
    boundary_carrier_correct = 0
    boundary_carrier_total = 0

    # Temporal stability metrics
    state_switches = 0
    short_acquisitions = 0
    carrier_durations = []
    curr_run = 0
    prev_carrier = None

    for fid in common_fids:
        gt = gt_by_fid[fid]
        pred = preds_by_fid[fid]

        gt_team = gt["team_possession"]
        pred_team = pred.possession_team

        # Normalize terminology
        gt_norm = "NEUTRAL" if gt_team in ("FREE_BALL", "NEUTRAL") else gt_team
        pred_norm = "NEUTRAL" if pred_team in ("FREE_BALL", "NEUTRAL") else pred_team

        gt_team_counts[gt_norm] = gt_team_counts.get(gt_norm, 0) + 1
        pred_team_counts[pred_norm] = pred_team_counts.get(pred_norm, 0) + 1

        if pred_norm != "UNKNOWN":
            valid_count += 1

        if gt_norm == pred_norm:
            correct_team += 1
            tp_by_team[gt_norm] = tp_by_team.get(gt_norm, 0) + 1

        # Carrier metric
        gt_c = gt.get("carrier_track_id")
        if gt_c is not None:
            carrier_gt_total += 1
            pred_c = pred.controlling_player_id
            pred_gt_c = pred.controlling_player_gt_id
            if pred_c == gt_c or pred_gt_c == gt_c:
                carrier_correct += 1

        # Boundary metrics
        if fid in gt_transition_frames:
            boundary_team_total += 1
            if gt_norm == pred_norm:
                boundary_team_correct += 1
            if gt_c is not None:
                boundary_carrier_total += 1
                pred_c = pred.controlling_player_id
                pred_gt_c = pred.controlling_player_gt_id
                if pred_c == gt_c or pred_gt_c == gt_c:
                    boundary_carrier_correct += 1

        # Stability tracking
        pred_c = pred.controlling_player_id
        if pred_c != prev_carrier:
            state_switches += 1
            if curr_run > 0:
                carrier_durations.append(curr_run)
                if curr_run < 3:
                    short_acquisitions += 1
            curr_run = 1
        else:
            curr_run += 1
        prev_carrier = pred_c

    total_frames = len(common_fids)
    frame_acc = float(correct_team / total_frames * 100.0)
    coverage = float(valid_count / total_frames * 100.0)

    # Macro F1
    all_states = sorted(set(gt_team_counts.keys()) | set(pred_team_counts.keys()))
    f1s = []
    per_state: Dict[str, Any] = {}
    for st in all_states:
        tp = tp_by_team.get(st, 0)
        fp = pred_team_counts.get(st, 0) - tp
        fn = gt_team_counts.get(st, 0) - tp
        prec = tp / max(1, tp + fp)
        rec = tp / max(1, tp + fn)
        f1 = 2 * prec * rec / max(1e-6, prec + rec)
        f1s.append(f1)
        per_state[st] = {
            "precision": float(prec),
            "recall": float(rec),
            "f1": float(f1),
            "support": gt_team_counts.get(st, 0),
        }

    macro_f1 = float(np.mean(f1s)) if f1s else 0.0
    carrier_acc = float(carrier_correct / carrier_gt_total * 100.0) if carrier_gt_total > 0 else 0.0

    duration_mins = (total_frames / FPS) / 60.0
    switches_per_min = float(state_switches / max(1e-3, duration_mins))

    return {
        "frames_compared": total_frames,
        "team_possession_frame_accuracy_pct": frame_acc,
        "valid_prediction_coverage_pct": coverage,
        "macro_f1": macro_f1,
        "carrier_accuracy_pct": carrier_acc,
        "unambiguous_carrier_frames": carrier_gt_total,
        "temporal_stability": {
            "switches_per_minute": switches_per_min,
            "false_short_acquisitions": short_acquisitions,
            "mean_control_duration_seconds": float(np.mean(carrier_durations) / FPS) if carrier_durations else 0.0,
        },
        "event_boundary_metrics": {
            "boundary_frames_evaluated": boundary_team_total,
            "boundary_team_accuracy_pct": float(boundary_team_correct / max(1, boundary_team_total) * 100.0),
            "boundary_carrier_accuracy_pct": float(boundary_carrier_correct / max(1, boundary_carrier_total) * 100.0),
        },
        "per_state_breakdown": per_state,
    }


# ==============================================================================
# PHASE 15: EXP-19 DOWNSTREAM PASS DETECTION BENCHMARK
# ==============================================================================

def run_exp19_downstream_evaluation(
    seq_name: str,
    frames_possession: List[TeamPossessionFrameState],
    player_obs_history: List[Any],
    ball_obs_history: List[Any],
    calib_history: List[Any],
    gt_pass_events: List[Dict[str, Any]],
) -> Tuple[List[PassEvent], Dict[str, Any]]:
    """Feeds possession frame states into frozen EXP-19 PassEventDetector without retuning."""
    detector = PassEventDetector(config=PassDetectorConfig())
    lines_config = TacticalLineConfig(pitch_dimensions=PitchDimensions(105.0, 68.0), min_line_gap_m=6.0, min_players_for_tactics=4)
    lines_engine = OrientedTacticsEngine(config=lines_config)

    for fid in range(1, len(frames_possession) + 1):
        idx = fid - 1
        timestamp = idx / FPS
        p_obs = player_obs_history[idx]
        b_obs = ball_obs_history[idx]
        cal_res = calib_history[idx]
        poss_st = frames_possession[idx]

        lines_st = lines_engine.process_frame(fid, timestamp, p_obs, b_obs, cal_res.valid)
        att_dirs = {
            "TEAM_0": lines_st.team_0.attack_direction,
            "TEAM_1": lines_st.team_1.attack_direction,
        }

        detector.process_frame(
            frame_index=fid,
            timestamp=timestamp,
            player_observations=p_obs,
            ball_observation=b_obs,
            possession_state=poss_st,
            calibration_valid=cal_res.valid,
            attack_directions=att_dirs,
            sequence_id=seq_name,
        )

    pred_events = list(detector.finalized_events)

    # Evaluate against GT pass events
    rel_tolerance = 5
    rec_tolerance = 8
    matched_gt: set = set()
    matched_pred: set = set()

    candidate_matches = []
    for g_idx, g in enumerate(gt_pass_events):
        g_rel = g["release_frame"]
        g_rec = g.get("reception_frame")
        for p_idx, p in enumerate(pred_events):
            rel_diff = abs(p.release_frame - g_rel)
            if rel_diff <= rel_tolerance:
                rec_diff = 0
                if g_rec is not None and p.reception_frame is not None:
                    rec_diff = abs(p.reception_frame - g_rec)
                    if rec_diff > rec_tolerance:
                        continue
                total_diff = rel_diff + rec_diff
                candidate_matches.append((total_diff, g_idx, p_idx, rel_diff, rec_diff))

    candidate_matches.sort(key=lambda x: x[0])
    matches = []
    for total_diff, g_idx, p_idx, rel_diff, rec_diff in candidate_matches:
        if g_idx not in matched_gt and p_idx not in matched_pred:
            matched_gt.add(g_idx)
            matched_pred.add(p_idx)
            matches.append({
                "gt_idx": g_idx,
                "pred_idx": p_idx,
                "rel_frame_diff": rel_diff,
                "rec_frame_diff": rec_diff,
            })

    gt_pass_indices = {i for i, g in enumerate(gt_pass_events) if g["event_type"] in ("PASS_COMPLETED", "PASS_INTERCEPTED")}
    pred_pass_indices = {i for i, p in enumerate(pred_events) if (p.event_type.value if hasattr(p.event_type, "value") else str(p.event_type)) in ("PASS_COMPLETED", "PASS_INTERCEPTED")}

    matched_transfer_gt = {m["gt_idx"] for m in matches if m["gt_idx"] in gt_pass_indices and m["pred_idx"] in pred_pass_indices}
    matched_transfer_pred = {m["pred_idx"] for m in matches if m["gt_idx"] in gt_pass_indices and m["pred_idx"] in pred_pass_indices}

    tp = len(matched_transfer_gt)
    fn = len(gt_pass_indices - matched_transfer_gt)
    fp = len(pred_pass_indices - matched_transfer_pred)
    prec = float(tp / max(1, tp + fp))
    rec = float(tp / max(1, tp + fn))
    f1 = float(2 * prec * rec / max(1e-6, prec + rec))

    rel_diffs = [m["rel_frame_diff"] for m in matches]
    rec_diffs = [m["rec_frame_diff"] for m in matches]

    metrics = {
        "pred_events_count": len(pred_events),
        "gt_events_count": len(gt_pass_events),
        "matched_events": len(matches),
        "transfer_precision": prec,
        "transfer_recall": rec,
        "transfer_f1": f1,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "mean_release_frame_error": float(np.mean(rel_diffs)) if rel_diffs else 0.0,
        "mean_reception_frame_error": float(np.mean(rec_diffs)) if rec_diffs else 0.0,
    }
    return pred_events, metrics


# ==============================================================================
# MAIN BENCHMARK RUNNER
# ==============================================================================

def main() -> None:
    logger.info("Executing EXP-22 Ball Control & Possession V2 Benchmark...")
    data_dir = Path("/media/adriano/Windows/datasets/SoccerNetTracking2023/train")
    tactics_runs_dir = Path("/media/adriano/Windows/runs/tactics")
    tactics_runs_dir.mkdir(parents=True, exist_ok=True)
    visuals_dir = tactics_runs_dir / "visuals"
    visuals_dir.mkdir(parents=True, exist_ok=True)

    calib_cache_path = tactics_runs_dir / "calib_cache.pkl"
    cached_adapter = RobustCachedCalibAdapter(disk_cache_path=calib_cache_path)

    # 1. Run Phase 20 Synthetic Verification
    synthetic_results = run_synthetic_tests()

    # 2. Load Ground Truth Datasets
    gt_control_path = PROJECT_ROOT / "docs/experiments/ball_control_gt_v2.json"
    with open(gt_control_path, "r") as f:
        gt_control_data = json.load(f)

    gt_pass_path = PROJECT_ROOT / "docs/experiments/pass_events_gt_v1.json"
    with open(gt_pass_path, "r") as f:
        gt_pass_data = json.load(f)
    gt_holdout_pass_events = gt_pass_data.get("HOLDOUT", [])

    # 3. Evaluate DEV Sequences
    dev_results_v1 = {}
    dev_results_v2 = {}
    for seq in DEV_SEQUENCES:
        raw_dets = RAW_DETS_MAP[seq]
        gt_records = gt_control_data["CONTROL_DEV"][seq]
        f_v1, f_v2, s_meta, p_obs_h, b_obs_h = run_sequence_dual_engines(
            seq, data_dir / seq, raw_dets, cached_adapter, num_frames=150
        )
        dev_results_v1[seq] = evaluate_possession_predictions(f_v1, gt_records)
        dev_results_v2[seq] = evaluate_possession_predictions(f_v2, gt_records)

    # 4. Evaluate HOLDOUT Sequences (Exact Same Sequences for V1 vs V2)
    holdout_results_v1 = {}
    holdout_results_v2 = {}
    downstream_v1 = {}
    downstream_v2 = {}
    downstream_oracle = {}
    all_latencies_v2 = []

    for seq in HOLDOUT_SEQUENCES:
        raw_dets = RAW_DETS_MAP[seq]
        gt_records = gt_control_data["CONTROL_HOLDOUT"][seq]
        seq_pass_gt = [e for e in gt_holdout_pass_events if e["sequence_id"] == seq]

        f_v1, f_v2, s_meta, p_obs_h, b_obs_h = run_sequence_dual_engines(
            seq, data_dir / seq, raw_dets, cached_adapter, num_frames=150
        )
        all_latencies_v2.append(s_meta["v2_latency_ms"]["mean"])

        holdout_results_v1[seq] = evaluate_possession_predictions(f_v1, gt_records)
        holdout_results_v2[seq] = evaluate_possession_predictions(f_v2, gt_records)

        # Downstream EXP-19 Transfer Evaluation
        # Mode A: V1 control
        _, down_v1 = run_exp19_downstream_evaluation(
            seq, f_v1, p_obs_h, b_obs_h, [cached_adapter.calibrate_image(data_dir / seq / "img1" / f"{i:06d}.jpg") for i in range(1, 151)], seq_pass_gt
        )
        downstream_v1[seq] = down_v1

        # Mode B: V2 control
        _, down_v2 = run_exp19_downstream_evaluation(
            seq, f_v2, p_obs_h, b_obs_h, [cached_adapter.calibrate_image(data_dir / seq / "img1" / f"{i:06d}.jpg") for i in range(1, 151)], seq_pass_gt
        )
        downstream_v2[seq] = down_v2

        # Mode C: Oracle Control (where GT carrier is directly injected)
        f_oracle = []
        for fid, f in enumerate(f_v2, 1):
            gt_r = next((r for r in gt_records if r["frame_index"] == fid), None)
            c_gt = gt_r.get("carrier_track_id") if gt_r else None
            t_gt = gt_r.get("carrier_team") if gt_r else None
            status_oracle = PossessionStatus.SECURE if c_gt is not None else PossessionStatus.PROVISIONAL_TRANSIT
            f_o = TeamPossessionFrameState(
                frame_index=fid,
                timestamp=(fid - 1) / FPS,
                possession_team=t_gt or "UNKNOWN",
                possession_status=status_oracle,
                possession_confidence=1.0,
                controlling_player_id=c_gt,
                controlling_player_gt_id=c_gt,
                controlling_player_team=t_gt,
                control_state=BallControlState.CONTROLLED if c_gt is not None else BallControlState.FREE_BALL,
            )
            f_oracle.append(f_o)

        _, down_orc = run_exp19_downstream_evaluation(
            seq, f_oracle, p_obs_h, b_obs_h, [cached_adapter.calibrate_image(data_dir / seq / "img1" / f"{i:06d}.jpg") for i in range(1, 151)], seq_pass_gt
        )
        downstream_oracle[seq] = down_orc

    # 5. Aggregate Macro Performance
    def _macro(results_dict: Dict[str, Dict[str, Any]], key: str) -> float:
        vals = [r[key] for r in results_dict.values() if key in r]
        return float(np.mean(vals)) if vals else 0.0

    macro_dev_v1_acc = _macro(dev_results_v1, "team_possession_frame_accuracy_pct")
    macro_dev_v2_acc = _macro(dev_results_v2, "team_possession_frame_accuracy_pct")
    macro_dev_v1_f1 = _macro(dev_results_v1, "macro_f1")
    macro_dev_v2_f1 = _macro(dev_results_v2, "macro_f1")

    macro_holdout_v1_acc = _macro(holdout_results_v1, "team_possession_frame_accuracy_pct")
    macro_holdout_v2_acc = _macro(holdout_results_v2, "team_possession_frame_accuracy_pct")
    macro_holdout_v1_f1 = _macro(holdout_results_v1, "macro_f1")
    macro_holdout_v2_f1 = _macro(holdout_results_v2, "macro_f1")
    macro_holdout_v1_carrier = _macro(holdout_results_v1, "carrier_accuracy_pct")
    macro_holdout_v2_carrier = _macro(holdout_results_v2, "carrier_accuracy_pct")

    # Downstream Pass Macro
    def _down_macro(down_dict: Dict[str, Dict[str, Any]], key: str) -> float:
        vals = [r[key] for r in down_dict.values() if key in r]
        return float(np.mean(vals)) if vals else 0.0

    down_v1_prec = _down_macro(downstream_v1, "transfer_precision")
    down_v1_rec = _down_macro(downstream_v1, "transfer_recall")
    down_v1_f1 = _down_macro(downstream_v1, "transfer_f1")

    down_v2_prec = _down_macro(downstream_v2, "transfer_precision")
    down_v2_rec = _down_macro(downstream_v2, "transfer_recall")
    down_v2_f1 = _down_macro(downstream_v2, "transfer_f1")

    down_orc_prec = _down_macro(downstream_oracle, "transfer_precision")
    down_orc_rec = _down_macro(downstream_oracle, "transfer_recall")
    down_orc_f1 = _down_macro(downstream_oracle, "transfer_f1")

    mean_v2_latency = float(np.mean(all_latencies_v2))

    logger.info("================================================================================")
    logger.info("EXP-22 BENCHMARK SUMMARY:")
    logger.info("  DEV Team Acc     : V1 = %.2f%%  |  V2 = %.2f%%  (Delta: %+.2f%%)",
                macro_dev_v1_acc, macro_dev_v2_acc, macro_dev_v2_acc - macro_dev_v1_acc)
    logger.info("  DEV Macro F1     : V1 = %.4f   |  V2 = %.4f   (Delta: %+.4f)",
                macro_dev_v1_f1, macro_dev_v2_f1, macro_dev_v2_f1 - macro_dev_v1_f1)
    logger.info("  HOLDOUT Team Acc : V1 = %.2f%%  |  V2 = %.2f%%  (Delta: %+.2f%%)",
                macro_holdout_v1_acc, macro_holdout_v2_acc, macro_holdout_v2_acc - macro_holdout_v1_acc)
    logger.info("  HOLDOUT Macro F1 : V1 = %.4f   |  V2 = %.4f   (Delta: %+.4f)",
                macro_holdout_v1_f1, macro_holdout_v2_f1, macro_holdout_v2_f1 - macro_holdout_v1_f1)
    logger.info("  HOLDOUT Carrier  : V1 = %.2f%%  |  V2 = %.2f%%  (Delta: %+.2f%%)",
                macro_holdout_v1_carrier, macro_holdout_v2_carrier, macro_holdout_v2_carrier - macro_holdout_v1_carrier)
    logger.info("  DOWNSTREAM TRANSFER (FROZEN EXP-19 HOLDOUT):")
    logger.info("    Mode A (V1)    : Prec = %.2f%% | Rec = %.2f%% | F1 = %.4f",
                down_v1_prec * 100.0, down_v1_rec * 100.0, down_v1_f1)
    logger.info("    Mode B (V2)    : Prec = %.2f%% | Rec = %.2f%% | F1 = %.4f",
                down_v2_prec * 100.0, down_v2_rec * 100.0, down_v2_f1)
    logger.info("    Mode C (Oracle): Prec = %.2f%% | Rec = %.2f%% | F1 = %.4f",
                down_orc_prec * 100.0, down_orc_rec * 100.0, down_orc_f1)
    logger.info("  V2 MEAN LATENCY  : %.4f ms/frame (Budget: <0.50 ms/frame)", mean_v2_latency)
    logger.info("================================================================================")

    # 6. Render Visualizations for SNMOT-060 and SNMOT-069
    # Timeseries plot for SNMOT-069
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), dpi=150, sharex=True)
    fids = list(range(1, 151))
    v1_teams = [f.possession_team for f in f_v1]
    v2_teams = [f.possession_team for f in f_v2]

    team_map = {"TEAM_0": 1, "TEAM_1": -1, "CONTESTED": 0, "NEUTRAL": 0.5, "UNKNOWN": -0.5}
    ax1.plot(fids, [team_map.get(t, 0) for t in v1_teams], label="V1 (Heuristic)", color="#ff5722", lw=2.0)
    ax1.plot(fids, [team_map.get(t, 0) for t in v2_teams], label="V2 (Challenger)", color="#4caf50", lw=2.5, ls="--")
    ax1.set_yticks([-1, -0.5, 0, 0.5, 1])
    ax1.set_yticklabels(["TEAM_1", "UNKNOWN", "CONTESTED", "NEUTRAL", "TEAM_0"])
    ax1.set_title("EXP-22 Team Possession Timeseries Comparison (SNMOT-069)")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    v1_car = [1 if f.controlling_player_id is not None else 0 for f in f_v1]
    v2_car = [1 if f.controlling_player_id is not None else 0 for f in f_v2]
    ax2.plot(fids, v1_car, label="V1 Carrier Active", color="#ff5722", alpha=0.7)
    ax2.plot(fids, v2_car, label="V2 Carrier Active", color="#4caf50", lw=2.0)
    ax2.set_xlabel("Frame Index")
    ax2.set_ylabel("Carrier Confirmed")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    plot_ts_path = visuals_dir / "SNMOT-069_possession_v2_timeseries.png"
    plt.savefig(plot_ts_path)
    plt.close()
    logger.info("Saved timeseries visualization to %s", plot_ts_path)

    # 7. Compile Final Output JSON
    output_report = {
        "experiment": "EXP-22",
        "description": "Ball Control & Possession V2 Challenger Benchmark",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "synthetic_scenarios": synthetic_results,
        "performance_summary": {
            "dev_team_accuracy_v1": macro_dev_v1_acc,
            "dev_team_accuracy_v2": macro_dev_v2_acc,
            "dev_macro_f1_v1": macro_dev_v1_f1,
            "dev_macro_f1_v2": macro_dev_v2_f1,
            "holdout_team_accuracy_v1": macro_holdout_v1_acc,
            "holdout_team_accuracy_v2": macro_holdout_v2_acc,
            "holdout_macro_f1_v1": macro_holdout_v1_f1,
            "holdout_macro_f1_v2": macro_holdout_v2_f1,
            "holdout_carrier_accuracy_v1": macro_holdout_v1_carrier,
            "holdout_carrier_accuracy_v2": macro_holdout_v2_carrier,
            "holdout_carrier_delta_pct": macro_holdout_v2_carrier - macro_holdout_v1_carrier,
            "holdout_team_delta_pct": macro_holdout_v2_acc - macro_holdout_v1_acc,
        },
        "downstream_frozen_exp19_transfer": {
            "mode_a_v1_precision": down_v1_prec,
            "mode_a_v1_recall": down_v1_rec,
            "mode_a_v1_f1": down_v1_f1,
            "mode_b_v2_precision": down_v2_prec,
            "mode_b_v2_recall": down_v2_rec,
            "mode_b_v2_f1": down_v2_f1,
            "mode_c_oracle_precision": down_orc_prec,
            "mode_c_oracle_recall": down_orc_rec,
            "mode_c_oracle_f1": down_orc_f1,
            "downstream_f1_delta": down_v2_f1 - down_v1_f1,
        },
        "runtime": {
            "mean_v2_latency_ms": mean_v2_latency,
            "target_ms": 0.50,
            "is_budget_compliant": bool(mean_v2_latency < 0.50),
        },
        "decision_gate": {
            "is_holdout_control_improved": bool(macro_holdout_v2_carrier > macro_holdout_v1_carrier),
            "is_downstream_pass_improved": bool(down_v2_f1 > down_v1_f1),
            "verdict": "CASE_A_POSSESSION_V2_ADOPTED" if (macro_holdout_v2_carrier > macro_holdout_v1_carrier and down_v2_f1 >= down_v1_f1) else ("CASE_B_POSSESSION_IMPROVED_PASS_INDEPENDENT" if macro_holdout_v2_carrier > macro_holdout_v1_carrier else "CASE_C_NOT_SUPERIOR"),
        },
        "dev_sequences": {
            "v1": dev_results_v1,
            "v2": dev_results_v2,
        },
        "holdout_sequences": {
            "v1": holdout_results_v1,
            "v2": holdout_results_v2,
            "downstream_v1": downstream_v1,
            "downstream_v2": downstream_v2,
            "downstream_oracle": downstream_oracle,
        },
    }

    report_out_path = PROJECT_ROOT / "docs/experiments/exp22_possession_v2.json"
    with open(report_out_path, "w") as f:
        json.dump(output_report, f, indent=2)
    logger.info("Saved EXP-22 Benchmark Report to %s", report_out_path)


if __name__ == "__main__":
    main()
