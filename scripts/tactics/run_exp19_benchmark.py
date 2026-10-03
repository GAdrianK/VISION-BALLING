"""EXP-19: Pass Detection & Ball Event Trajectories Benchmark.

Executes controlled scientific validation of:
1. Synthetic pass event scenarios (Phase 22):
   - Completed pass (same team)
   - Intercepted pass (opponent team)
   - Timeout into open space (BALL_RELEASE_UNRESOLVED)
   - High-speed defensive clearance (CLEARANCE_CANDIDATE)
   - Dribble touch rejection (same player, small displacement)
   - Aerial ground jump gating (>25 m/s jump invalidates Z=0 trajectory)
   - Tracker ID switch robustness
2. DEV parameter grid search on max_transit_frames in [25, 35, 45].
3. Full sequence benchmarks on 12 SoccerNet sequences:
   - DEV (SNMOT-060 full 750f, SNMOT-061..065 150f each)
   - HOLDOUT (SNMOT-069 full 750f, SNMOT-066..068, 070..071 150f each)
4. Dual Mode Evaluation (Phase 16):
   - Mode A (End-to-End): using causal EXP-18 possession engine output.
   - Mode B (Oracle Control Diagnostic): using GT carrier intervals to isolate
     upstream possession errors from pass detector mechanics.
5. Evaluation against pass_events_gt_v1 (Precision, Recall, F1, release/reception
   frame timing errors in frames and ms, sender/receiver attribution accuracy).
6. Incremental runtime overhead profiling (< 0.30 ms/frame target).
7. Top-down 2D pass vector pitch diagrams and multi-panel time-series plots.
8. Official JSON export: docs/experiments/exp19_pass_events.json.
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
sys.path.insert(0, "/tmp/sn-calibration")

from app.video_analysis.pitch_calibration import PitchCalibrationResult, PitchDimensions
from app.video_analysis.calibration_adapters import PnLCalibAdapter
from app.video_analysis.temporal_calibration import (
    TemporalPitchCalibrator,
    TemporalCalibrationConfig,
    TemporalCalibrationResult,
)
from app.video_analysis.player_tracker import PlayerBoTSORT, BoTSORTConfig
from app.video_analysis.ball_tracker import BallTrackManager, create_ball_track_config_v2
from app.video_analysis.metric_trajectories import (
    MetricTrajectoryConfig,
    MetricTrajectoryEngine,
    SmoothingMethod,
)
from app.video_analysis.tactical_geometry import (
    FIVE_LANE_BOUNDS,
    TacticalGeometryConfig,
    TacticalGeometryEngine,
)
from app.video_analysis.tactical_lines import (
    AttackDirection,
    OrientedTacticsEngine,
    TacticalLineConfig,
)
from app.video_analysis.possession import (
    BallControlEstimator,
    BallControlEvaluation,
    BallControlState,
    PlayerControlCandidate,
    PossessionChangeEvent,
    PossessionConfig,
    PossessionEngine,
    PossessionStatus,
    TeamPossessionFrameState,
    TeamPossessionStateMachine,
    TeamPossessionState,
)
from app.video_analysis.pass_detector import (
    PassDetectorConfig,
    PassEvent,
    PassEventDetector,
    PassEventType,
    PassFrameState,
    BallTransferTrajectory,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("EXP-19")

PASS_DEV_SEQUENCES = ["SNMOT-060", "SNMOT-061", "SNMOT-062", "SNMOT-063", "SNMOT-064", "SNMOT-065"]
PASS_HOLDOUT_SEQUENCES = ["SNMOT-066", "SNMOT-067", "SNMOT-068", "SNMOT-069", "SNMOT-070", "SNMOT-071"]
FPS = 25.0

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


# ==============================================================================
# CALIBRATION CACHING
# ==============================================================================

class CachedPnLCalibAdapter:
    """Wraps PnLCalibAdapter with batch preloading, in-memory cache, and disk persistence."""

    def __init__(self, base_adapter: PnLCalibAdapter, disk_cache_path: Optional[Path] = None) -> None:
        self.base_adapter = base_adapter
        self.disk_cache_path = disk_cache_path
        self.cache: Dict[str, PitchCalibrationResult] = {}
        self.invocation_count = 0
        self.total_call_time_ms = 0.0

        if self.disk_cache_path and self.disk_cache_path.is_file():
            try:
                with open(self.disk_cache_path, "rb") as f:
                    self.cache = pickle.load(f)
                logger.info("Loaded %d pre-calibrated keyframes from disk cache %s", len(self.cache), self.disk_cache_path)
            except Exception as e:
                logger.warning("Could not load calibration disk cache: %s", e)

    def preload_keyframes(self, image_paths: List[Path], frame_indices: List[int]) -> None:
        needed_paths = [p for p in image_paths if str(p) not in self.cache]
        needed_indices = [idx for p, idx in zip(image_paths, frame_indices) if str(p) not in self.cache]
        if not needed_paths:
            return

        logger.info("Pre-calibrating %d keyframe images in batch pass...", len(needed_paths))
        t0 = time.perf_counter()
        results = self.base_adapter.calibrate_batch(needed_paths, frame_indices=needed_indices)
        t1 = time.perf_counter()
        logger.info("Batch keyframe pre-calibration took %.2f s (%.1f ms/image)", t1 - t0, (t1 - t0) / max(1, len(needed_paths)) * 1000.0)

        for p, res in zip(needed_paths, results):
            self.cache[str(p)] = res

        if self.disk_cache_path:
            try:
                self.disk_cache_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.disk_cache_path, "wb") as f:
                    pickle.dump(self.cache, f)
                logger.info("Persisted %d calibrated keyframes to disk cache %s", len(self.cache), self.disk_cache_path)
            except Exception as e:
                logger.warning("Could not persist calibration cache to disk: %s", e)

    def calibrate_image(
        self,
        image_path: Union[str, Path],
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

        t0 = time.perf_counter()
        res = self.base_adapter.calibrate_image(image_path, frame_index=frame_index, timestamp=timestamp)
        t1 = time.perf_counter()
        call_time = (t1 - t0) * 1000.0
        self.invocation_count += 1
        self.total_call_time_ms += call_time
        self.cache[key] = res
        return res


# ==============================================================================
# GROUND TRUTH PARSING HELPERS
# ==============================================================================

def load_gameinfo_metadata(gameinfo_path: Path) -> Tuple[Dict[int, str], Dict[int, str]]:
    """Loads player roles and team labels from gameinfo.ini."""
    roles: Dict[int, str] = {}
    teams: Dict[int, str] = {}
    if not gameinfo_path.is_file():
        return roles, teams

    parser = configparser.ConfigParser()
    try:
        parser.read(str(gameinfo_path))
    except Exception as e:
        logger.warning("Failed parsing gameinfo.ini: %s", e)
        return roles, teams

    for sec in parser.sections():
        if not sec.startswith("trackletid_"):
            continue
        try:
            tid = int(sec.replace("trackletid_", ""))
        except ValueError:
            continue

        raw_team = parser.get(sec, "team", fallback="").strip().lower()
        if "left" in raw_team or "team1" in raw_team or "team 1" in raw_team:
            t_label = "TEAM_0"
        elif "right" in raw_team or "team2" in raw_team or "team 2" in raw_team:
            t_label = "TEAM_1"
        else:
            t_label = "TEAM_0" if (tid % 2 == 0) else "TEAM_1"
        teams[tid] = t_label

        role_str = parser.get(sec, "role", fallback="").strip().lower()
        if "goalkeeper" in role_str or "gk" in role_str:
            roles[tid] = "GOALKEEPER"
        elif "referee" in role_str:
            roles[tid] = "REFEREE"
        else:
            roles[tid] = "OUTFIELD_PLAYER"

    return roles, teams


def load_gt_player_bboxes(gt_txt_path: Path) -> Dict[int, Dict[int, List[float]]]:
    """Loads ground-truth player bboxes by frame: {fid: {gt_tid: [x1, y1, x2, y2]}}."""
    gt_map: Dict[int, Dict[int, List[float]]] = {}
    if not gt_txt_path.is_file():
        return gt_map

    with open(gt_txt_path, "r") as f:
        for line in f:
            parts = line.strip().split(",")
            if len(parts) < 6:
                continue
            fid = int(parts[0])
            tid = int(parts[1])
            bb_left = float(parts[2])
            bb_top = float(parts[3])
            bb_width = float(parts[4])
            bb_height = float(parts[5])
            bbox = [bb_left, bb_top, bb_left + bb_width, bb_top + bb_height]
            if fid not in gt_map:
                gt_map[fid] = {}
            gt_map[fid][tid] = bbox
    return gt_map


def compute_iou(boxA: List[float], boxB: List[float]) -> float:
    xA = max(boxA[0], boxB[0])
    yA = max(boxA[1], boxB[1])
    xB = min(boxA[2], boxB[2])
    yB = min(boxA[3], boxB[3])
    inter = max(0.0, xB - xA) * max(0.0, yB - yA)
    areaA = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
    areaB = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
    union = areaA + areaB - inter
    return inter / union if union > 0 else 0.0


# ==============================================================================
# PHASE 22: SYNTHETIC STATE MACHINE VERIFICATION
# ==============================================================================

def run_synthetic_state_tests() -> Dict[str, Any]:
    """Validates the 7 core pass event detector scenarios synthetically."""
    logger.info("Executing Phase 22: Synthetic Pass Event State Machine Tests...")
    results = {}

    def _make_p(tid, team, u, v, px=0.0, py=0.0):
        class P:
            pass
        p = P()
        p.track_id = tid
        p.team_label = team
        p.role = "OUTFIELD_PLAYER"
        p.bbox = [u - 15, v - 30, u + 15, v + 30]
        p.pitch_x_m = px
        p.pitch_y_m = py
        p.gt_tracklet_id = tid
        return p

    def _make_b(u, v, px=0.0, py=0.0):
        class B:
            pass
        b = B()
        b.bbox = [u - 5, v - 5, u + 5, v + 5]
        b.pitch_x_m = px
        b.pitch_y_m = py
        b.confidence = 0.95
        return b

    def _make_poss(fid, ts, team, pid, st):
        return TeamPossessionFrameState(
            frame_index=fid,
            timestamp=ts,
            possession_team=team,
            possession_status=st,
            possession_confidence=0.90,
            controlling_player_id=pid,
            controlling_player_team=team,
            control_state=BallControlState.CONTROLLED if pid else BallControlState.FREE_BALL,
        )

    # 1. Completed Pass (Same Team)
    d1 = PassEventDetector()
    p1 = _make_p(1, "TEAM_0", 400.0, 500.0, -10.0, 0.0)
    p2 = _make_p(2, "TEAM_0", 600.0, 500.0, 10.0, 0.0)
    for f in range(1, 4):
        d1.process_frame(f, f * 0.04, [p1, p2], _make_b(405.0, 500.0, -9.5, 0.0), _make_poss(f, f*0.04, "TEAM_0", 1, PossessionStatus.SECURE))
    for f in range(4, 8):
        bx = 405.0 + (f - 3) * 35.0
        d1.process_frame(f, f * 0.04, [p1, p2], _make_b(bx, 500.0, -9.5 + (f - 3) * 3.5, 0.0), _make_poss(f, f*0.04, "TEAM_0", None, PossessionStatus.PROVISIONAL_TRANSIT))
    st = d1.process_frame(8, 0.32, [p1, p2], _make_b(598.0, 500.0, 9.8, 0.0), _make_poss(8, 0.32, "TEAM_0", 2, PossessionStatus.SECURE))
    evt = st.recent_finalized_event
    results["completed_pass_same_team"] = (evt is not None and evt.event_type == PassEventType.PASS_COMPLETED and evt.receiver_track_id == 2)

    # 2. Intercepted Pass (Opponent)
    d2 = PassEventDetector()
    p_opp = _make_p(10, "TEAM_1", 550.0, 500.0, 5.0, 0.0)
    for f in range(1, 4):
        d2.process_frame(f, f * 0.04, [p1, p_opp], _make_b(405.0, 500.0, -9.5, 0.0), _make_poss(f, f*0.04, "TEAM_0", 1, PossessionStatus.SECURE))
    for f in range(4, 7):
        d2.process_frame(f, f * 0.04, [p1, p_opp], _make_b(405.0 + (f-3)*40.0, 500.0, -9.5 + (f-3)*4.0, 0.0), _make_poss(f, f*0.04, "TEAM_0", None, PossessionStatus.PROVISIONAL_TRANSIT))
    st = d2.process_frame(7, 0.28, [p1, p_opp], _make_b(548.0, 500.0, 4.8, 0.0), _make_poss(7, 0.28, "TEAM_1", 10, PossessionStatus.SECURE))
    evt = st.recent_finalized_event
    results["intercepted_pass_opponent"] = (evt is not None and evt.event_type == PassEventType.PASS_INTERCEPTED and evt.receiver_team == "TEAM_1")

    # 3. Timeout Unresolved
    d3 = PassEventDetector(config=PassDetectorConfig(max_transit_frames=8))
    for f in range(1, 3):
        d3.process_frame(f, f * 0.04, [p1], _make_b(405.0, 500.0, 0.0, 0.0), _make_poss(f, f*0.04, "TEAM_0", 1, PossessionStatus.SECURE))
    for f in range(3, 12):
        d3.process_frame(f, f * 0.04, [], _make_b(405.0 + (f-2)*8.0, 500.0, (f-2)*0.5, 0.0), _make_poss(f, f*0.04, "TEAM_0", None, PossessionStatus.NEUTRAL))
    results["timeout_unresolved"] = (len(d3.finalized_events) == 1 and d3.finalized_events[0].event_type == PassEventType.BALL_RELEASE_UNRESOLVED)

    # 4. Clearance Candidate
    d4 = PassEventDetector(config=PassDetectorConfig(max_transit_frames=8, clearance_min_speed_ms=15.0, clearance_min_displacement_m=20.0))
    p5 = _make_p(5, "TEAM_0", 200.0, 500.0, -40.0, 0.0)
    for f in range(1, 3):
        d4.process_frame(f, f * 0.04, [p5], _make_b(205.0, 500.0, -39.5, 0.0), _make_poss(f, f*0.04, "TEAM_0", 5, PossessionStatus.SECURE))
    for f in range(3, 12):
        d4.process_frame(f, f * 0.04, [], _make_b(205.0 + (f-2)*50.0, 500.0, -39.5 + (f-2)*4.0, 0.0), _make_poss(f, f*0.04, "TEAM_0", None, PossessionStatus.NEUTRAL))
    results["clearance_candidate"] = (len(d4.finalized_events) == 1 and d4.finalized_events[0].event_type == PassEventType.CLEARANCE_CANDIDATE)

    # 5. Dribble Touch Rejection
    d5 = PassEventDetector()
    p1_dr = _make_p(1, "TEAM_0", 400.0, 500.0, 0.0, 0.0)
    for f in range(1, 3):
        d5.process_frame(f, f * 0.04, [p1_dr], _make_b(405.0, 500.0, 0.0, 0.0), _make_poss(f, f*0.04, "TEAM_0", 1, PossessionStatus.SECURE))
    for f in range(3, 6):
        d5.process_frame(f, f * 0.04, [p1_dr], _make_b(415.0, 500.0, 1.0, 0.0), _make_poss(f, f*0.04, "TEAM_0", None, PossessionStatus.PROVISIONAL_TRANSIT))
    p1_tap = _make_p(1, "TEAM_0", 418.0, 500.0, 1.2, 0.0)
    st = d5.process_frame(6, 0.24, [p1_tap], _make_b(418.0, 500.0, 1.2, 0.0), _make_poss(6, 0.24, "TEAM_0", 1, PossessionStatus.SECURE))
    results["dribble_rejection"] = (st.recent_finalized_event is None and len(d5.finalized_events) == 0)

    # 6. Aerial Speed Jump Invalidation
    d6 = PassEventDetector(config=PassDetectorConfig(aerial_ground_jump_speed_ms=25.0))
    p1_aer = _make_p(1, "TEAM_0", 400.0, 500.0, 0.0, 0.0)
    for f in range(1, 3):
        d6.process_frame(f, f * 0.04, [p1_aer], _make_b(405.0, 500.0, 0.0, 0.0), _make_poss(f, f*0.04, "TEAM_0", 1, PossessionStatus.SECURE))
    d6.process_frame(3, 0.12, [p1_aer], _make_b(420.0, 500.0, 1.0, 0.0), _make_poss(3, 0.12, "TEAM_0", None, PossessionStatus.PROVISIONAL_TRANSIT))
    st = d6.process_frame(4, 0.16, [p1_aer], _make_b(450.0, 480.0, 31.0, 0.0), _make_poss(4, 0.16, "TEAM_0", None, PossessionStatus.PROVISIONAL_TRANSIT))
    results["aerial_jump_invalidation"] = (st.is_aerial_suspected is True and d6.active_candidate.trajectory.trajectory_ground_valid is False)

    # 7. ID Switch Robustness
    d7 = PassEventDetector()
    p2_sw = _make_p(999, "TEAM_0", 600.0, 500.0, 15.0, 0.0)
    for f in range(1, 4):
        d7.process_frame(f, f * 0.04, [p1, p2_sw], _make_b(405.0, 500.0, -4.8, 0.0), _make_poss(f, f*0.04, "TEAM_0", 1, PossessionStatus.SECURE))
    for f in range(4, 8):
        d7.process_frame(f, f * 0.04, [p1, p2_sw], _make_b(405.0 + (f-3)*38.0, 500.0, -4.8 + (f-3)*3.8, 0.0), _make_poss(f, f*0.04, "TEAM_0", None, PossessionStatus.PROVISIONAL_TRANSIT))
    st = d7.process_frame(8, 0.32, [p1, p2_sw], _make_b(600.0, 500.0, 15.0, 0.0), _make_poss(8, 0.32, "TEAM_0", 999, PossessionStatus.SECURE))
    evt = st.recent_finalized_event
    results["id_switch_robustness"] = (evt is not None and evt.event_type == PassEventType.PASS_COMPLETED and evt.receiver_track_id == 999)

    for k, v in results.items():
        logger.info("Synthetic Test %-30s : %s", k, "PASS" if v else "FAIL")
        assert v, f"Synthetic test failed: {k}"

    return results


# ==============================================================================
# PIPELINE SEQUENCE EXECUTION (SINGLE PASS DUAL-MODE ENGINE)
# ==============================================================================

def run_single_sequence_pass_events(
    seq_name: str,
    seq_dir: Path,
    frame_limit: int,
    cached_adapter: CachedPnLCalibAdapter,
    pass_cfg: PassDetectorConfig,
    gt_events: Optional[List[Dict[str, Any]]] = None,
    grid_search_cfgs: Optional[Dict[str, PassDetectorConfig]] = None,
) -> Tuple[List[PassEvent], List[PassFrameState], List[PassEvent], List[PassFrameState], Dict[str, Any], Dict[str, List[PassEvent]]]:
    """Runs upstream tracking + calibration + possession once, evaluating Mode A and Mode B concurrently."""
    logger.info("Processing %s [DUAL-MODE A+B] up to %d frames...", seq_name, frame_limit)

    # 1. Load sequence metadata & GT
    gameinfo_path = seq_dir / "gameinfo.ini"
    gt_txt_path = seq_dir / "gt" / "gt.txt"
    roles, teams = load_gameinfo_metadata(gameinfo_path)
    gt_bboxes_by_frame = load_gt_player_bboxes(gt_txt_path)

    # 2. Load cached raw detections
    raw_dets_path = RAW_DETS_MAP[seq_name]
    with open(raw_dets_path, "rb") as f:
        dets_by_frame = pickle.load(f)

    # 3. Initialize frozen pipeline modules
    calibrator = TemporalPitchCalibrator(adapter=cached_adapter, config=TemporalCalibrationConfig(max_keyframe_interval=10))
    p_tracker = PlayerBoTSORT(BoTSORTConfig(with_reid=False))
    b_tracker = BallTrackManager(create_ball_track_config_v2())
    traj_engine = MetricTrajectoryEngine(MetricTrajectoryConfig(smoothing_method=SmoothingMethod.KALMAN))
    tact_geom_engine = TacticalGeometryEngine(TacticalGeometryConfig())
    lines_engine = OrientedTacticsEngine(TacticalLineConfig())
    possession_engine = PossessionEngine(PossessionConfig())

    # Detectors
    detector_mode_a = PassEventDetector(pass_cfg)
    detector_mode_b = PassEventDetector(pass_cfg)
    grid_detectors = {name: PassEventDetector(cfg) for name, cfg in (grid_search_cfgs or {}).items()}

    # Track ID mapping to GT tracklet ID
    track_to_gt: Dict[int, int] = {}
    gt_to_track: Dict[int, int] = {}

    # Pre-build Oracle Carrier Map for Mode B
    oracle_carrier_by_frame: Dict[int, Tuple[int, str, PossessionStatus]] = {}
    if gt_events:
        for evt in gt_events:
            s_gt = evt.get("sender_track_gt")
            s_team = evt.get("sender_team", "TEAM_0")
            r_gt = evt.get("receiver_track_gt")
            r_team = evt.get("receiver_team", "TEAM_0")
            rel_f = evt["release_frame"]
            rec_f = evt.get("reception_frame")

            # 5 frames prior to release: sender controls ball
            for f in range(max(1, rel_f - 5), rel_f + 1):
                oracle_carrier_by_frame[f] = (s_gt, s_team, PossessionStatus.SECURE)

            # In-flight frames: provisional transit
            if rec_f is not None:
                for f in range(rel_f + 1, rec_f):
                    oracle_carrier_by_frame[f] = (None, s_team, PossessionStatus.PROVISIONAL_TRANSIT)
                # Reception frame: receiver controls ball
                for f in range(rec_f, min(rec_f + 5, frame_limit + 1)):
                    oracle_carrier_by_frame[f] = (r_gt, r_team, PossessionStatus.SECURE)

    # Frame processing
    states_a: List[PassFrameState] = []
    states_b: List[PassFrameState] = []
    latencies_a_ms: List[float] = []

    for fid in range(1, frame_limit + 1):
        timestamp = (fid - 1) / FPS
        fpath = seq_dir / "img1" / f"{fid:06d}.jpg"
        if not fpath.is_file():
            break
        im = cv2.imread(str(fpath))

        dets = dets_by_frame.get(fid, [])
        p_dets = [d for d in dets if d.class_name == "person"]
        b_dets = [d for d in dets if d.class_name in ("sports ball", "ball")]

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

            # Match BoTSORT track ID with GT tracklet ID by IoU
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
                gt_to_track[matched_gt] = tid

            gt_tid = track_to_gt.get(tid)
            if gt_tid is not None:
                p.role = roles.get(gt_tid, "OUTFIELD_PLAYER")
                p.team_label = teams.get(gt_tid, "TEAM_0" if (gt_tid % 2 == 0) else "TEAM_1")
                setattr(p, "gt_tracklet_id", gt_tid)
            else:
                p.role = roles.get(tid, "OUTFIELD_PLAYER")
                p.team_label = teams.get(tid, "TEAM_0" if (tid % 2 == 0) else "TEAM_1")
                setattr(p, "gt_tracklet_id", tid)

        tact_geom_engine.process_frame(fid, timestamp, player_obs, ball_m_obs, calib_res.valid)
        lines_state = lines_engine.process_frame(fid, timestamp, player_obs, ball_m_obs, calib_res.valid)
        att_dirs = {
            "TEAM_0": lines_state.team_0.attack_direction,
            "TEAM_1": lines_state.team_1.attack_direction,
        }

        # Causal Possession Engine (Mode A)
        control_eval = possession_engine.control_estimator.evaluate(player_obs, ball_m_obs, calib_res.valid)
        poss_state_a, _ = possession_engine.state_machine.update(fid, timestamp, control_eval)

        # Oracle Possession State (Mode B)
        poss_state_b = poss_state_a
        if fid in oracle_carrier_by_frame:
            o_gt, o_team, o_status = oracle_carrier_by_frame[fid]
            mapped_tid = gt_to_track.get(o_gt) if o_gt is not None else None
            poss_state_b = TeamPossessionFrameState(
                frame_index=fid,
                timestamp=timestamp,
                possession_team=o_team,
                possession_status=o_status,
                possession_confidence=0.95,
                controlling_player_id=mapped_tid,
                controlling_player_team=o_team,
                control_state=BallControlState.CONTROLLED if mapped_tid else BallControlState.FREE_BALL,
            )

        # Mode A Inference & Timing
        t0 = time.perf_counter()
        st_a = detector_mode_a.process_frame(
            frame_index=fid,
            timestamp=timestamp,
            player_observations=player_obs,
            ball_observation=ball_m_obs,
            possession_state=poss_state_a,
            calibration_valid=calib_res.valid,
            attack_directions=att_dirs,
            sequence_id=seq_name,
        )
        t1 = time.perf_counter()
        latencies_a_ms.append((t1 - t0) * 1000.0)
        states_a.append(st_a)

        # Mode B Inference
        st_b = detector_mode_b.process_frame(
            frame_index=fid,
            timestamp=timestamp,
            player_observations=player_obs,
            ball_observation=ball_m_obs,
            possession_state=poss_state_b,
            calibration_valid=calib_res.valid,
            attack_directions=att_dirs,
            sequence_id=seq_name,
        )
        states_b.append(st_b)

        # Grid Search Detectors (if any)
        for g_det in grid_detectors.values():
            g_det.process_frame(
                frame_index=fid,
                timestamp=timestamp,
                player_observations=player_obs,
                ball_observation=ball_m_obs,
                possession_state=poss_state_a,
                calibration_valid=calib_res.valid,
                attack_directions=att_dirs,
                sequence_id=seq_name,
            )

    timing_stats = {
        "mean_latency_ms": float(np.mean(latencies_a_ms)) if latencies_a_ms else 0.0,
        "median_latency_ms": float(np.median(latencies_a_ms)) if latencies_a_ms else 0.0,
        "p95_latency_ms": float(np.percentile(latencies_a_ms, 95)) if latencies_a_ms else 0.0,
        "total_frames": len(states_a),
    }

    events_a = list(detector_mode_a.finalized_events)
    events_b = list(detector_mode_b.finalized_events)
    grid_events = {name: list(d.finalized_events) for name, d in grid_detectors.items()}

    logger.info("Sequence %s yielded %d Mode A events, %d Mode B events (latency: %.4f ms/frame)",
                seq_name, len(events_a), len(events_b), timing_stats["mean_latency_ms"])
    return events_a, states_a, events_b, states_b, timing_stats, grid_events


# ==============================================================================
# EVALUATION & MATCHING AGAINST GROUND TRUTH
# ==============================================================================

def evaluate_pass_events(
    pred_events: List[PassEvent],
    gt_events: List[Dict[str, Any]],
    rel_tolerance_frames: int = 5,
    rec_tolerance_frames: int = 8,
) -> Dict[str, Any]:
    """Matches predicted pass events to ground-truth events within frame tolerance."""
    matched_gt: set = set()
    matched_pred: set = set()

    # Match pairs: (gt_idx, pred_idx, total_frame_diff)
    candidate_matches = []
    for g_idx, g in enumerate(gt_events):
        g_rel = g["release_frame"]
        g_rec = g.get("reception_frame")
        for p_idx, p in enumerate(pred_events):
            rel_diff = abs(p.release_frame - g_rel)
            if rel_diff <= rel_tolerance_frames:
                rec_diff = 0
                if g_rec is not None and p.reception_frame is not None:
                    rec_diff = abs(p.reception_frame - g_rec)
                    if rec_diff > rec_tolerance_frames:
                        continue
                total_diff = rel_diff + rec_diff
                candidate_matches.append((total_diff, g_idx, p_idx, rel_diff, rec_diff))

    # Greedy best-first matching
    candidate_matches.sort(key=lambda x: x[0])
    matches = []
    for total_diff, g_idx, p_idx, rel_diff, rec_diff in candidate_matches:
        if g_idx not in matched_gt and p_idx not in matched_pred:
            matched_gt.add(g_idx)
            matched_pred.add(p_idx)
            matches.append({
                "gt_idx": g_idx,
                "pred_idx": p_idx,
                "gt_event": gt_events[g_idx],
                "pred_event": pred_events[p_idx],
                "rel_frame_diff": rel_diff,
                "rec_frame_diff": rec_diff,
            })

    # Pass Transfer Detection (Any Pass Completed or Intercepted)
    gt_pass_indices = {i for i, g in enumerate(gt_events) if g["event_type"] in ("PASS_COMPLETED", "PASS_INTERCEPTED")}
    pred_pass_indices = {i for i, p in enumerate(pred_events) if (p.event_type.value if hasattr(p.event_type, "value") else str(p.event_type)) in ("PASS_COMPLETED", "PASS_INTERCEPTED")}

    matched_transfer_gt = {m["gt_idx"] for m in matches if m["gt_idx"] in gt_pass_indices and m["pred_idx"] in pred_pass_indices}
    matched_transfer_pred = {m["pred_idx"] for m in matches if m["gt_idx"] in gt_pass_indices and m["pred_idx"] in pred_pass_indices}

    transfer_tp = len(matched_transfer_gt)
    transfer_fn = len(gt_pass_indices - matched_transfer_gt)
    transfer_fp = len(pred_pass_indices - matched_transfer_pred)
    transfer_prec = transfer_tp / max(1, transfer_tp + transfer_fp)
    transfer_rec = transfer_tp / max(1, transfer_tp + transfer_fn)
    transfer_f1 = 2 * transfer_prec * transfer_rec / max(1e-6, transfer_prec + transfer_rec)

    # Classification accuracy among matched transfers
    classification_correct = sum(
        1 for m in matches
        if m["gt_idx"] in gt_pass_indices and m["pred_idx"] in pred_pass_indices and
        m["gt_event"]["event_type"] == (m["pred_event"].event_type.value if hasattr(m["pred_event"].event_type, "value") else str(m["pred_event"].event_type))
    )
    transfer_class_acc = float(classification_correct / max(1, transfer_tp) * 100.0) if transfer_tp > 0 else 0.0

    # Strict Per-Category Counts
    categories = ["PASS_COMPLETED", "PASS_INTERCEPTED", "CLEARANCE_CANDIDATE", "BALL_RELEASE_UNRESOLVED"]
    per_cat = {c: {"tp": 0, "fp": 0, "fn": 0} for c in categories}

    for m in matches:
        g_type = m["gt_event"]["event_type"]
        p_type = m["pred_event"].event_type.value if hasattr(m["pred_event"].event_type, "value") else str(m["pred_event"].event_type)

        if g_type == p_type:
            if g_type in per_cat:
                per_cat[g_type]["tp"] += 1
        else:
            if g_type in per_cat:
                per_cat[g_type]["fn"] += 1
            if p_type in per_cat:
                per_cat[p_type]["fp"] += 1

    # Unmatched GT -> FN
    for g_idx, g in enumerate(gt_events):
        if g_idx not in matched_gt:
            g_type = g["event_type"]
            if g_type in per_cat:
                per_cat[g_type]["fn"] += 1

    # Unmatched Pred -> FP
    for p_idx, p in enumerate(pred_events):
        if p_idx not in matched_pred:
            p_type = p.event_type.value if hasattr(p.event_type, "value") else str(p.event_type)
            if p_type in per_cat:
                per_cat[p_type]["fp"] += 1

    category_metrics = {}
    for c, counts in per_cat.items():
        tp = counts["tp"]
        fp = counts["fp"]
        fn = counts["fn"]
        prec = tp / max(1, tp + fp)
        rec = tp / max(1, tp + fn)
        f1 = 2 * prec * rec / max(1e-6, prec + rec)
        category_metrics[c] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": float(prec),
            "recall": float(rec),
            "f1": float(f1),
            "support": tp + fn,
        }

    # Timing errors on matched events
    rel_errors_frames = [m["rel_frame_diff"] for m in matches]
    rel_errors_ms = [e * (1000.0 / FPS) for e in rel_errors_frames]
    rec_errors_frames = [m["rec_frame_diff"] for m in matches if m["gt_event"].get("reception_frame") is not None]
    rec_errors_ms = [e * (1000.0 / FPS) for e in rec_errors_frames]

    # Attribution accuracy on matched events
    sender_team_correct = 0
    receiver_team_correct = 0
    rec_total = 0

    for m in matches:
        g = m["gt_event"]
        p = m["pred_event"]
        if p.sender_team == g["sender_team"]:
            sender_team_correct += 1
        if g.get("receiver_team") is not None:
            rec_total += 1
            if p.receiver_team == g["receiver_team"]:
                receiver_team_correct += 1

    sender_team_acc = float(sender_team_correct / max(1, len(matches)) * 100.0) if matches else 0.0
    receiver_team_acc = float(receiver_team_correct / max(1, rec_total) * 100.0) if rec_total > 0 else 0.0

    # Physical trajectory statistics
    displacements = [p.pass_displacement_m for p in pred_events if p.pass_displacement_m is not None]
    forward_disps = [p.forward_displacement_m for p in pred_events if p.forward_displacement_m is not None]
    aerial_count = sum(1 for p in pred_events if p.trajectory and p.trajectory.aerial_suspected)

    return {
        "gt_events_count": len(gt_events),
        "pred_events_count": len(pred_events),
        "matched_events_count": len(matches),
        "pass_transfer_detection": {
            "precision": float(transfer_prec),
            "recall": float(transfer_rec),
            "f1": float(transfer_f1),
            "tp": transfer_tp,
            "fp": transfer_fp,
            "fn": transfer_fn,
            "classification_accuracy_pct": transfer_class_acc,
        },
        "per_category_metrics": category_metrics,
        "timing_errors": {
            "release_frame_mean": float(np.mean(rel_errors_frames)) if rel_errors_frames else None,
            "release_frame_median": float(np.median(rel_errors_frames)) if rel_errors_frames else None,
            "release_frame_p90": float(np.percentile(rel_errors_frames, 90)) if rel_errors_frames else None,
            "release_ms_mean": float(np.mean(rel_errors_ms)) if rel_errors_ms else None,
            "reception_frame_mean": float(np.mean(rec_errors_frames)) if rec_errors_frames else None,
            "reception_frame_median": float(np.median(rec_errors_frames)) if rec_errors_frames else None,
            "reception_frame_p90": float(np.percentile(rec_errors_frames, 90)) if rec_errors_frames else None,
            "reception_ms_mean": float(np.mean(rec_errors_ms)) if rec_errors_ms else None,
        },
        "attribution_accuracy": {
            "sender_team_accuracy_pct": sender_team_acc,
            "receiver_team_accuracy_pct": receiver_team_acc,
        },
        "physical_trajectory_stats": {
            "mean_displacement_m": float(np.mean(displacements)) if displacements else None,
            "median_displacement_m": float(np.median(displacements)) if displacements else None,
            "mean_forward_displacement_m": float(np.mean(forward_disps)) if forward_disps else None,
            "progressive_passes_pct": float(sum(1 for d in forward_disps if d > 0) / max(1, len(forward_disps)) * 100.0) if forward_disps else 0.0,
            "aerial_suspected_count": aerial_count,
        },
    }


# ==============================================================================
# VISUALIZATION RENDERING
# ==============================================================================

def render_pass_pitch_diagram(
    event: PassEvent,
    pitch_dimensions: PitchDimensions,
    sequence_id: str,
    output_png: Path,
) -> None:
    """Renders 2D top-down pitch diagram illustrating a finalized pass trajectory."""
    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(14, 9), dpi=150)
    fig.patch.set_facecolor("#1e2227")
    ax.set_facecolor("#1e2227")

    hl = pitch_dimensions.length_m / 2.0
    hw = pitch_dimensions.width_m / 2.0

    pitch_rect = patches.Rectangle((-hl, -hw), pitch_dimensions.length_m, pitch_dimensions.width_m,
                                   fill=True, facecolor="#2d6e2e", edgecolor="white", linewidth=2.0)
    ax.add_patch(pitch_rect)

    for _, pts in pitch_dimensions.get_canonical_pitch_lines().items():
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        ax.plot(xs, ys, color="white", linewidth=1.5, alpha=0.85)

    center_circle = patches.Circle((0, 0), pitch_dimensions.center_circle_radius_m, fill=False, edgecolor="white", linewidth=1.5)
    ax.add_patch(center_circle)
    ax.scatter([0], [0], color="white", s=25, zorder=5)

    # Plot Pass Release and Reception
    if event.release_position_pitch is not None:
        rx, ry = event.release_position_pitch
        ax.scatter([rx], [ry], color="#e63946", s=140, edgecolor="white", linewidth=2, zorder=10, label=f"Release (P#{event.sender_track_id})")
        ax.text(rx + 1.0, ry + 1.0, f"Passer #{event.sender_track_id}\n({event.sender_team})", color="white", fontsize=9, weight="bold")

    if event.reception_position_pitch is not None:
        cx, cy = event.reception_position_pitch
        rec_color = "#2a9d8f" if event.event_type == PassEventType.PASS_COMPLETED else "#e76f51"
        lbl = f"Receiver #{event.receiver_track_id}" if event.receiver_track_id else "Endpoint"
        ax.scatter([cx], [cy], color=rec_color, s=140, edgecolor="white", linewidth=2, zorder=10, label=lbl)
        ax.text(cx + 1.0, cy + 1.0, f"{lbl}\n({event.receiver_team or 'None'})", color="white", fontsize=9, weight="bold")

    # Draw Pass Flight Vector
    if event.release_position_pitch is not None and event.reception_position_pitch is not None:
        rx, ry = event.release_position_pitch
        cx, cy = event.reception_position_pitch
        ax.annotate(
            "",
            xy=(cx, cy),
            xytext=(rx, ry),
            arrowprops=dict(arrowstyle="->", color="#f4a261", lw=3.0, ls="--", mutation_scale=20),
            zorder=8,
        )

    # Banner Header
    banner_color = "#2a9d8f" if event.event_type == PassEventType.PASS_COMPLETED else "#e76f51"
    disp_str = f"{event.pass_displacement_m:.1f}m" if event.pass_displacement_m is not None else "N/A"
    fwd_str = f"{event.forward_displacement_m:+.1f}m" if event.forward_displacement_m is not None else "N/A"
    flight_str = f"{event.trajectory.flight_duration_s:.2f}s" if event.trajectory else "N/A"

    banner_text = (
        f"{sequence_id} — {event.event_id} [{event.event_type.value}]\n"
        f"Sender: #{event.sender_track_id} ({event.sender_team}) -> Receiver: #{event.receiver_track_id} ({event.receiver_team})\n"
        f"Release Frame: {event.release_frame} | Reception Frame: {event.reception_frame} | Flight Duration: {flight_str}\n"
        f"Displacement: {disp_str} | Forward ΔX_attack: {fwd_str} | Confidence: {event.event_confidence:.2f}"
    )

    ax.text(0.0, 38.0, banner_text, color=banner_color, fontsize=10, weight="bold", ha="center",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#1e2227", edgecolor=banner_color, alpha=0.9))

    ax.set_xlim(-hl - 8, hl + 8)
    ax.set_ylim(-hw - 8, hw + 8)
    ax.set_xlabel("Pitch X (meters)", color="white")
    ax.set_ylabel("Pitch Y (meters)", color="white")
    ax.tick_params(colors="white")
    ax.legend(loc="lower right", facecolor="#1e2227", edgecolor="white", labelcolor="white")

    plt.tight_layout()
    plt.savefig(str(output_png), facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    logger.info("Saved pass pitch diagram to %s", output_png)


def render_pass_timeline_plot(
    events: List[PassEvent],
    frame_states: List[PassFrameState],
    sequence_id: str,
    output_png: Path,
) -> None:
    """Renders multi-panel pass event timeline."""
    output_png.parent.mkdir(parents=True, exist_ok=True)
    times = [f.timestamp for f in frame_states]
    flight_ages = [f.flight_age_frames for f in frame_states]

    fig, axs = plt.subplots(3, 1, figsize=(13, 9), sharex=True, dpi=150)
    fig.patch.set_facecolor("#1e2227")

    def _setup_ax(ax, title, ylabel):
        ax.set_facecolor("#2a2e36")
        ax.set_title(title, color="white", fontsize=10, weight="bold")
        ax.set_ylabel(ylabel, color="white", fontsize=9)
        ax.tick_params(colors="white")
        ax.grid(True, linestyle="--", alpha=0.3)

    # 1. Active Transit State & Events
    _setup_ax(axs[0], f"{sequence_id} — Pass Event Timeline & Active Flight State", "State")
    state_numeric = [1 if f.active_state == PassEventType.PENDING_TRANSFER else 0 for f in frame_states]
    axs[0].fill_between(times, state_numeric, color="#f4a261", alpha=0.4, label="In-Transit Flight Window")
    axs[0].set_yticks([0, 1])
    axs[0].set_yticklabels(["Idle/Controlled", "Ball In Flight"])

    for evt in events:
        t_rel = evt.release_timestamp
        t_rec = evt.reception_timestamp or (t_rel + 0.5)
        color = "#2a9d8f" if evt.event_type == PassEventType.PASS_COMPLETED else (
            "#e76f51" if evt.event_type == PassEventType.PASS_INTERCEPTED else "#e9c46a"
        )
        axs[0].axvspan(t_rel, t_rec, color=color, alpha=0.6)
        axs[0].text(t_rel, 0.5, f" {evt.event_type.value[:6]} #{evt.sender_track_id}->#{evt.receiver_track_id}",
                    color="white", fontsize=8, rotation=90, weight="bold")

    # 2. Flight Transit Age
    _setup_ax(axs[1], "Ball Flight Age (Frames)", "Frames")
    axs[1].plot(times, flight_ages, color="#e76f51", linewidth=1.6)
    axs[1].axhline(35, color="red", linestyle="--", alpha=0.7, label="Max Transit Timeout (35f)")
    axs[1].legend(loc="upper right", facecolor="#1e2227", labelcolor="white")

    # 3. Finalized Event Forward Displacement
    _setup_ax(axs[2], "Forward Attacking Displacement ΔX_attack (Meters)", "Meters")
    evt_times = [e.reception_timestamp or e.release_timestamp for e in events]
    evt_fwds = [e.forward_displacement_m or 0.0 for e in events]
    colors = ["#2a9d8f" if fwd > 0 else "#e76f51" for fwd in evt_fwds]
    if evt_times:
        axs[2].bar(evt_times, evt_fwds, width=0.8, color=colors, edgecolor="white", alpha=0.9)
    axs[2].axhline(0, color="white", linestyle="-", linewidth=1.0)
    axs[2].set_xlabel("Time (seconds)", color="white", fontsize=10)

    plt.tight_layout()
    plt.savefig(str(output_png), facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    logger.info("Saved pass timeline plot to %s", output_png)


# ==============================================================================
# MAIN BENCHMARK DRIVER
# ==============================================================================

def main() -> None:
    print("================================================================================")
    print("EXP-19 — PASS DETECTION & BALL EVENT TRAJECTORIES BENCHMARK")
    print("================================================================================")

    tracking_base = Path("/media/adriano/Windows/datasets/SoccerNetTracking2023/train")
    tactics_runs_dir = Path("/media/adriano/Windows/runs/tactics")
    visuals_dir = tactics_runs_dir / "visuals"
    gt_path = PROJECT_ROOT / "docs" / "experiments" / "pass_events_gt_v1.json"
    report_path = PROJECT_ROOT / "docs" / "experiments" / "exp19_pass_events.json"

    visuals_dir.mkdir(parents=True, exist_ok=True)

    # 1. Phase 22 Synthetic Scenarios
    synthetic_results = run_synthetic_state_tests()

    # 2. Load Ground Truth
    with open(gt_path, "r") as f:
        gt_data = json.load(f)

    gt_dev_events = gt_data["DEV"]
    gt_holdout_events = gt_data["HOLDOUT"]
    gt_by_seq = {}
    for ev in gt_dev_events + gt_holdout_events:
        gt_by_seq.setdefault(ev["sequence_id"], []).append(ev)

    # 3. Setup Calibration Adapter & Disk Cache
    raw_adapter = PnLCalibAdapter()
    cached_adapter = CachedPnLCalibAdapter(raw_adapter, disk_cache_path=tactics_runs_dir / "calib_cache.pkl")

    # Sequence limits
    dev_limits = {"SNMOT-060": 750, "SNMOT-061": 150, "SNMOT-062": 150, "SNMOT-063": 150, "SNMOT-064": 150, "SNMOT-065": 150}
    holdout_limits = {"SNMOT-066": 150, "SNMOT-067": 150, "SNMOT-068": 150, "SNMOT-069": 750, "SNMOT-070": 150, "SNMOT-071": 150}

    locked_cfg = PassDetectorConfig(max_transit_frames=35)
    grid_cfgs = {
        "25": PassDetectorConfig(max_transit_frames=25),
        "35": PassDetectorConfig(max_transit_frames=35),
        "45": PassDetectorConfig(max_transit_frames=45),
    }

    mode_a_dev_events: Dict[str, List[PassEvent]] = {}
    mode_a_dev_states: Dict[str, List[PassFrameState]] = {}
    mode_b_dev_events: Dict[str, List[PassEvent]] = {}
    mode_b_dev_states: Dict[str, List[PassFrameState]] = {}
    dev_timings: Dict[str, Any] = {}

    mode_a_holdout_events: Dict[str, List[PassEvent]] = {}
    mode_a_holdout_states: Dict[str, List[PassFrameState]] = {}
    mode_b_holdout_events: Dict[str, List[PassEvent]] = {}
    mode_b_holdout_states: Dict[str, List[PassFrameState]] = {}
    holdout_timings: Dict[str, Any] = {}

    grid_search_dev_events: Dict[str, Dict[str, List[PassEvent]]] = {}

    # Run DEV Sequences
    for s_name, n_f in dev_limits.items():
        s_dir = tracking_base / s_name
        gt_seq = [e for e in gt_by_seq.get(s_name, []) if e["release_frame"] <= n_f]
        s_grid_cfgs = grid_cfgs if s_name == "SNMOT-060" else None

        ev_a, st_a, ev_b, st_b, t_stat, g_evs = run_single_sequence_pass_events(
            seq_name=s_name,
            seq_dir=s_dir,
            frame_limit=n_f,
            cached_adapter=cached_adapter,
            pass_cfg=locked_cfg,
            gt_events=gt_seq,
            grid_search_cfgs=s_grid_cfgs,
        )

        mode_a_dev_events[s_name] = ev_a
        mode_a_dev_states[s_name] = st_a
        mode_b_dev_events[s_name] = ev_b
        mode_b_dev_states[s_name] = st_b
        dev_timings[s_name] = t_stat
        if g_evs:
            grid_search_dev_events[s_name] = g_evs

    # Run HOLDOUT Sequences
    for s_name, n_f in holdout_limits.items():
        s_dir = tracking_base / s_name
        gt_seq = [e for e in gt_by_seq.get(s_name, []) if e["release_frame"] <= n_f]

        ev_a, st_a, ev_b, st_b, t_stat, _ = run_single_sequence_pass_events(
            seq_name=s_name,
            seq_dir=s_dir,
            frame_limit=n_f,
            cached_adapter=cached_adapter,
            pass_cfg=locked_cfg,
            gt_events=gt_seq,
        )

        mode_a_holdout_events[s_name] = ev_a
        mode_a_holdout_states[s_name] = st_a
        mode_b_holdout_events[s_name] = ev_b
        mode_b_holdout_states[s_name] = st_b
        holdout_timings[s_name] = t_stat

    # 4. Evaluate Grid Search on DEV
    logger.info("Compiling Phase 9: DEV Parameter Grid Search Results...")
    grid_search_summary = {}
    gt_dev_060 = [e for e in gt_by_seq.get("SNMOT-060", []) if e["release_frame"] <= dev_limits["SNMOT-060"]]
    if "SNMOT-060" in grid_search_dev_events:
        for k_val, g_list in grid_search_dev_events["SNMOT-060"].items():
            ev_res = evaluate_pass_events(g_list, gt_dev_060)
            grid_search_summary[k_val] = {
                "max_transit_frames": int(k_val),
                "events_detected": len(g_list),
                "transfer_detection": ev_res["pass_transfer_detection"],
            }
            logger.info("Grid Search max_transit_frames=%s -> F1=%.4f (Prec=%.4f, Rec=%.4f)",
                        k_val,
                        ev_res["pass_transfer_detection"]["f1"],
                        ev_res["pass_transfer_detection"]["precision"],
                        ev_res["pass_transfer_detection"]["recall"])

    # 5. Aggregate Evaluation Across Sets
    all_gt_dev = [e for s, n_f in dev_limits.items() for e in gt_by_seq.get(s, []) if e["release_frame"] <= n_f]
    all_pred_dev_a = [e for evs in mode_a_dev_events.values() for e in evs]
    all_pred_dev_b = [e for evs in mode_b_dev_events.values() for e in evs]

    all_gt_holdout = [e for s, n_f in holdout_limits.items() for e in gt_by_seq.get(s, []) if e["release_frame"] <= n_f]
    all_pred_holdout_a = [e for evs in mode_a_holdout_events.values() for e in evs]
    all_pred_holdout_b = [e for evs in mode_b_holdout_events.values() for e in evs]

    eval_dev_mode_a = evaluate_pass_events(all_pred_dev_a, all_gt_dev)
    eval_dev_mode_b = evaluate_pass_events(all_pred_dev_b, all_gt_dev)

    eval_holdout_mode_a = evaluate_pass_events(all_pred_holdout_a, all_gt_holdout)
    eval_holdout_mode_b = evaluate_pass_events(all_pred_holdout_b, all_gt_holdout)

    # 6. Render Visualizations
    p_dims = PitchDimensions()
    vis_060_events = mode_a_dev_events.get("SNMOT-060", [])
    if vis_060_events:
        render_pass_pitch_diagram(vis_060_events[0], p_dims, "SNMOT-060", visuals_dir / "SNMOT-060_pass_pitch.png")
    render_pass_timeline_plot(vis_060_events, mode_a_dev_states["SNMOT-060"], "SNMOT-060", visuals_dir / "SNMOT-060_pass_timeseries.png")

    vis_069_events = mode_a_holdout_events.get("SNMOT-069", [])
    if vis_069_events:
        render_pass_pitch_diagram(vis_069_events[0], p_dims, "SNMOT-069", visuals_dir / "SNMOT-069_pass_pitch.png")
    render_pass_timeline_plot(vis_069_events, mode_a_holdout_states["SNMOT-069"], "SNMOT-069", visuals_dir / "SNMOT-069_pass_timeseries.png")

    # 7. Runtime Profiling Aggregation
    all_latencies = [t["mean_latency_ms"] for t in {**dev_timings, **holdout_timings}.values()]
    mean_pass_latency = float(np.mean(all_latencies))
    p95_pass_latency = float(np.percentile([t["p95_latency_ms"] for t in {**dev_timings, **holdout_timings}.values()], 95))

    logger.info("Pass Event Engine Latency: Mean = %.4f ms/frame (Target < 0.30 ms), P95 = %.4f ms/frame",
                mean_pass_latency, p95_pass_latency)

    # 8. Build Official JSON Report
    report_data = {
        "experiment_id": "EXP-19",
        "description": "Pass Detection & Ball Event Trajectories Benchmark",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "hardware_environment": {
            "os": platform.platform(),
            "cpu": platform.processor(),
            "python_version": platform.python_version(),
        },
        "locked_configuration": asdict(locked_cfg),
        "synthetic_validation_results": synthetic_results,
        "dev_grid_search_max_transit_frames": grid_search_summary,
        "evaluation_summary": {
            "mode_a_end_to_end": {
                "dev": eval_dev_mode_a,
                "holdout": eval_holdout_mode_a,
            },
            "mode_b_oracle_control_diagnostic": {
                "dev": eval_dev_mode_b,
                "holdout": eval_holdout_mode_b,
            },
        },
        "per_sequence_breakdown": {
            "dev": {
                s: {
                    "frames": dev_limits[s],
                    "gt_count": len([e for e in gt_by_seq.get(s, []) if e["release_frame"] <= dev_limits[s]]),
                    "detected_count_mode_a": len(mode_a_dev_events[s]),
                    "detected_count_mode_b": len(mode_b_dev_events[s]),
                    "timing_ms": dev_timings[s],
                }
                for s in dev_limits
            },
            "holdout": {
                s: {
                    "frames": holdout_limits[s],
                    "gt_count": len([e for e in gt_by_seq.get(s, []) if e["release_frame"] <= holdout_limits[s]]),
                    "detected_count_mode_a": len(mode_a_holdout_events[s]),
                    "detected_count_mode_b": len(mode_b_holdout_events[s]),
                    "timing_ms": holdout_timings[s],
                }
                for s in holdout_limits
            },
        },
        "latency_compliance": {
            "mean_pass_detector_latency_ms": mean_pass_latency,
            "p95_pass_detector_latency_ms": p95_pass_latency,
            "latency_target_ms": 0.30,
            "compliant": bool(mean_pass_latency < 0.30),
        },
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(report_data, f, indent=2)
    logger.info("Saved official EXP-19 benchmark report to %s", report_path)

    print("\n================================================================================")
    print("EXP-19 BENCHMARK EXECUTION COMPLETE")
    print(f"DEV Mode A Transfer F1:     {eval_dev_mode_a['pass_transfer_detection']['f1']:.4f} (Prec: {eval_dev_mode_a['pass_transfer_detection']['precision']:.4f}, Rec: {eval_dev_mode_a['pass_transfer_detection']['recall']:.4f})")
    print(f"DEV Mode B Oracle F1:       {eval_dev_mode_b['pass_transfer_detection']['f1']:.4f} (Prec: {eval_dev_mode_b['pass_transfer_detection']['precision']:.4f}, Rec: {eval_dev_mode_b['pass_transfer_detection']['recall']:.4f})")
    print(f"HOLDOUT Mode A Transfer F1: {eval_holdout_mode_a['pass_transfer_detection']['f1']:.4f} (Prec: {eval_holdout_mode_a['pass_transfer_detection']['precision']:.4f}, Rec: {eval_holdout_mode_a['pass_transfer_detection']['recall']:.4f})")
    print(f"HOLDOUT Mode B Oracle F1:   {eval_holdout_mode_b['pass_transfer_detection']['f1']:.4f} (Prec: {eval_holdout_mode_b['pass_transfer_detection']['precision']:.4f}, Rec: {eval_holdout_mode_b['pass_transfer_detection']['recall']:.4f})")
    print(f"Mean Detector Latency:      {mean_pass_latency:.4f} ms/frame (Budget: <0.30 ms)")
    print(f"Report: {report_path}")
    print("================================================================================\n")


if __name__ == "__main__":
    main()
