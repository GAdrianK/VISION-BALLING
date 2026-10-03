"""EXP-21: Dynamic Formation Structure Inference Benchmark.

Executes complete benchmark across all 12 SoccerNet DEV and HOLDOUT tracking sequences:
- Phase 15: Exact synthetic verification for all 8 prototypes & edge cases
- Phase 16: Perturbation robustness analysis (noise, dropouts, wrong-team)
- Phase 7: Causal temporal window grid search (W=25, 50, 75 frames) on DEV
- Phase 20-22: Evaluation against formation_gt_v1 (accuracy, macro F1, coverage, structure edit distance)
- Phase 25: Latency profiling against <0.30 ms/frame budget
- Phase 26: Top-down pitch and timeseries visualizations
- Output: docs/experiments/exp21_dynamic_formation.json
"""

from __future__ import annotations

import configparser
import json
import logging
import pickle
import sys
import time
from collections import Counter
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
    PlayerMetricObservation,
    BallMetricObservation,
)
from app.video_analysis.tactical_geometry import (
    TacticalGeometryConfig,
    TacticalGeometryEngine,
    TacticalFrameState,
    TeamTacticalGeometry,
    BallTacticalGeometry,
    InterTeamTacticalGeometry,
    TacticalQualityState,
)
from app.video_analysis.tactical_lines import (
    AttackDirection,
    OrientedTacticalFrameState,
    OrientedTacticsEngine,
    TacticalLine,
    TacticalLineConfig,
    TeamOrientedTactics,
)
from app.video_analysis.possession import (
    PossessionConfig,
    PossessionEngine,
)
from app.video_analysis.formation_inferer import (
    CANONICAL_PROTOTYPES,
    DynamicFormationEngine,
    FormationConfig,
    FormationContext,
    FormationFrameState,
    FormationSignature,
    FormationState,
    TeamFormationState,
    VisibilityClass,
    compute_formation_distance,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("EXP-21")

DEV_SEQUENCES = ["SNMOT-060", "SNMOT-061", "SNMOT-062", "SNMOT-063", "SNMOT-064", "SNMOT-065"]
HOLDOUT_SEQUENCES = ["SNMOT-066", "SNMOT-067", "SNMOT-068", "SNMOT-069", "SNMOT-070", "SNMOT-071"]
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
# CALIBRATION ADAPTER WRAPPER (CACHE + NEAREST FALLBACK)
# ==============================================================================

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

        # Nearest keyframe fallback in same sequence
        seq_id = None
        for part in Path(image_path).parts:
            if part.startswith("SNMOT-"):
                seq_id = part
                break

        if seq_id:
            seq_keys = [k for k in self.cache.keys() if seq_id in k]
            if seq_keys:
                try:
                    curr_num = int(Path(image_path).stem)
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


# ==============================================================================
# GROUND TRUTH PARSING HELPERS
# ==============================================================================

def load_gameinfo_metadata(gameinfo_path: Path) -> Tuple[Dict[int, str], Dict[int, str]]:
    """Loads tracklet ground roles and team labels from gameinfo.ini if present."""
    roles: Dict[int, str] = {}
    teams: Dict[int, str] = {}
    if not gameinfo_path.is_file():
        return roles, teams

    cp = configparser.ConfigParser(strict=False)
    try:
        cp.read(str(gameinfo_path))
    except Exception as e:
        logger.warning("Failed parsing gameinfo.ini: %s", e)
        return roles, teams

    if "Sequence" in cp:
        sec = cp["Sequence"]
        for k, v in sec.items():
            if k.startswith("trackletid_"):
                try:
                    tid = int(k.split("_")[1])
                    val = str(v).strip()
                    parts = [p.strip() for p in val.split(";")]
                    role_str = parts[0].lower()
                    if "goalkeeper" in role_str:
                        roles[tid] = "GOALKEEPER"
                    else:
                        roles[tid] = "OUTFIELD_PLAYER"

                    if len(parts) >= 2:
                        team_token = parts[1].upper()
                        if team_token in ("A", "0", "TEAM_0", "TEAM_A", "LEFT", "TEAM_LEFT") or ("0" in team_token) or ("LEFT" in team_token):
                            teams[tid] = "TEAM_0"
                        elif team_token in ("B", "1", "TEAM_1", "TEAM_B", "RIGHT", "TEAM_RIGHT") or ("1" in team_token) or ("RIGHT" in team_token):
                            teams[tid] = "TEAM_1"
                        else:
                            teams[tid] = "TEAM_0"
                    else:
                        teams[tid] = "TEAM_0"
                except (ValueError, IndexError):
                    pass
    return roles, teams


def load_gt_player_bboxes(gt_txt_path: Path) -> Dict[int, Dict[int, List[float]]]:
    """Loads ground-truth bounding boxes by frame and tracklet ID."""
    boxes: Dict[int, Dict[int, List[float]]] = {}
    if not gt_txt_path.is_file():
        return boxes

    with open(gt_txt_path, "r") as f:
        for line in f:
            parts = line.strip().split(",")
            if len(parts) >= 6:
                fid = int(parts[0])
                tid = int(parts[1])
                x, y, w, h = float(parts[2]), float(parts[3]), float(parts[4]), float(parts[5])
                boxes.setdefault(fid, {})[tid] = [x, y, w, h]
    return boxes


def compute_iou(box1: List[float], box2: List[float]) -> float:
    """Computes Intersection over Union between two [x, y, w, h] bounding boxes."""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[0] + box1[2], box2[0] + box2[2])
    y2 = min(box1[1] + box1[3], box2[1] + box2[3])

    inter = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    union = box1[2] * box1[3] + box2[2] * box2[3] - inter
    return inter / union if union > 0 else 0.0


# ==============================================================================
# PHASE 15: SYNTHETIC SCENARIO VERIFICATION
# ==============================================================================

def run_synthetic_tests() -> Dict[str, bool]:
    """Validates exact behavior on canonical fixtures, missing players, staggers, and noise."""
    logger.info("Executing Phase 15 Synthetic Scenario Verification...")
    engine = DynamicFormationEngine()
    results: Dict[str, bool] = {}

    def _p(tid: int, x: float, y: float) -> PlayerMetricObservation:
        return PlayerMetricObservation(
            track_id=tid, frame_index=1, timestamp=0.04, team_label="TEAM_0",
            pitch_x_m=x, pitch_y_m=y, speed_mps=1.0, role="OUTFIELD_PLAYER", position_valid=True,
        )

    def _lines(counts: Sequence[int], x_pos: Sequence[float]) -> List[TacticalLine]:
        lines = []
        tid = 0
        for idx, (cnt, x) in enumerate(zip(counts, x_pos)):
            tids = list(range(tid, tid + cnt))
            tid += cnt
            lines.append(TacticalLine(idx, tids, cnt, x, x, 28.0 if cnt >= 4 else 20.0, x, 0.0, 0.95, f"L_{idx}"))
        return lines

    def _ctx(players: List[PlayerMetricObservation], lines: List[TacticalLine]):
        tg = TacticalFrameState(
            1, 0.04, True,
            TeamTacticalGeometry(team_label="TEAM_0", visible_players=len(players), outfield_player_count=len(players), is_valid=True, width_m=40.0, longitudinal_span_m=35.0),
            TeamTacticalGeometry(team_label="TEAM_1", is_valid=True),
            BallTacticalGeometry(), InterTeamTacticalGeometry(),
            TacticalQualityState(True, True),
        )
        t_orient = TeamOrientedTactics(
            team_label="TEAM_0", attack_direction=AttackDirection.POSITIVE_X, is_oriented=True,
            lines=lines, line_count=len(lines), visibility_level="HIGH" if len(players) >= 8 else "MEDIUM",
            outfield_player_count=len(players),
        )
        og = OrientedTacticalFrameState(1, 0.04, t_orient, TeamOrientedTactics("TEAM_1"), 0.95)
        return tg, og

    # 1-8: Canonical Prototypes
    proto_configs = {
        "4-4-2": ([4, 4, 2], [-20.0, -5.0, 12.0]),
        "4-3-3": ([4, 3, 3], [-20.0, -5.0, 15.0]),
        "4-2-3-1": ([4, 2, 3, 1], [-22.0, -10.0, 2.0, 15.0]),
        "4-1-4-1": ([4, 1, 4, 1], [-22.0, -12.0, 3.0, 16.0]),
        "3-5-2": ([3, 5, 2], [-20.0, -3.0, 14.0]),
        "3-4-3": ([3, 4, 3], [-20.0, -4.0, 15.0]),
        "5-3-2": ([5, 3, 2], [-22.0, -4.0, 14.0]),
        "5-4-1": ([5, 4, 1], [-22.0, -4.0, 16.0]),
    }

    for name, (counts, x_pos) in proto_configs.items():
        engine.reset()
        lns = _lines(counts, x_pos)
        plys = []
        tid = 0
        for cnt, x in zip(counts, x_pos):
            for j in range(cnt):
                plys.append(_p(tid, x, float(j * 6 - 12)))
                tid += 1
        tf, of = _ctx(plys, lns)
        st = engine.process_frame(1, 0.04, plys, tf, of)
        sig = st.team_0.instantaneous_signature
        results[f"canonical_{name}"] = (sig.best_prototype == name and sig.formation_label == name and sig.formation_confidence >= 0.85)

    # 9: 1 missing player (9 outfield) -> PARTIAL
    c_m1 = [4, 3, 2]
    lns_m1 = _lines(c_m1, [-20.0, -5.0, 12.0])
    plys_m1 = [_p(i, -20.0 if i < 4 else (-5.0 if i < 7 else 12.0), float((i % 4) * 6 - 9)) for i in range(9)]
    engine.reset()
    eng_part = DynamicFormationEngine(FormationConfig(full_evidence_threshold=10))
    tf, of = _ctx(plys_m1, lns_m1)
    st_m1 = eng_part.process_frame(1, 0.04, plys_m1, tf, of)
    results["one_missing_player_partial"] = (st_m1.team_0.instantaneous_signature.visibility_class == VisibilityClass.PARTIAL_EVIDENCE and st_m1.team_0.instantaneous_signature.formation_state == FormationState.PARTIAL)

    # 10: Low visibility (5 outfield) -> UNKNOWN
    plys_low = [_p(i, -20.0, float(i * 6 - 12)) for i in range(5)]
    lns_low = _lines([5], [-20.0])
    engine.reset()
    tf, of = _ctx(plys_low, lns_low)
    st_low = engine.process_frame(1, 0.04, plys_low, tf, of)
    results["low_visibility_unknown"] = (st_low.team_0.instantaneous_signature.visibility_class == VisibilityClass.LOW_EVIDENCE and st_low.team_0.instantaneous_signature.formation_state == FormationState.UNKNOWN)

    # 11: Set piece deformation -> TRANSITIONING / SET_PIECE_DEFORMATION
    plys_sp = [_p(i, -45.0 + (i % 3) * 3.0, (i // 3) * 3.0 - 5.0) for i in range(10)]
    lns_sp = [TacticalLine(0, list(range(10)), 10, -42.0, -42.0, 12.0, -42.0, 0.0, 0.95, "SCRUM")]
    tf_sp, of_sp = _ctx(plys_sp, lns_sp)
    tf_sp.team_0.longitudinal_span_m = 10.0
    tf_sp.team_0.width_m = 14.0
    engine.reset()
    st_sp = engine.process_frame(1, 0.04, plys_sp, tf_sp, of_sp)
    results["set_piece_deformation"] = (st_sp.team_0.instantaneous_signature.invalidation_reason == "SET_PIECE_DEFORMATION")

    for k, v in results.items():
        logger.info("Synthetic Scenario %-30s : %s", k, "PASS" if v else "FAIL")
        assert v, f"Scenario {k} failed!"
    return results


# ==============================================================================
# PHASE 16: PERTURBATION ROBUSTNESS RUNNER
# ==============================================================================

def run_perturbation_tests() -> Dict[str, Any]:
    """Evaluates position noise, defender dropout, and wrong-team perturbations."""
    logger.info("Executing Phase 16 Perturbation Robustness Analysis...")
    engine = DynamicFormationEngine()
    rng = np.random.RandomState(42)

    def _p(tid: int, x: float, y: float, team: str = "TEAM_0") -> PlayerMetricObservation:
        return PlayerMetricObservation(
            track_id=tid, frame_index=1, timestamp=0.04, team_label=team,
            pitch_x_m=x, pitch_y_m=y, speed_mps=1.0, role="OUTFIELD_PLAYER", position_valid=True,
        )

    base_counts = [4, 4, 2]
    base_x = [-20.0, -5.0, 12.0]
    base_players = []
    tid = 0
    for cnt, x in zip(base_counts, base_x):
        for j in range(cnt):
            base_players.append(_p(tid, x, float(j * 6 - 9)))
            tid += 1

    base_lines = [
        TacticalLine(0, [0, 1, 2, 3], 4, -20.0, -20.0, 28.0, -20.0, 0.0, 0.95, "DEF"),
        TacticalLine(1, [4, 5, 6, 7], 4, -5.0, -5.0, 26.0, -5.0, 0.0, 0.95, "MID"),
        TacticalLine(2, [8, 9], 2, 12.0, 12.0, 16.0, 12.0, 0.0, 0.95, "ATT"),
    ]

    tf_base = TacticalFrameState(
        1, 0.04, True,
        TeamTacticalGeometry(team_label="TEAM_0", visible_players=10, outfield_player_count=10, is_valid=True, width_m=40.0, longitudinal_span_m=35.0),
        TeamTacticalGeometry(team_label="TEAM_1", is_valid=True),
        BallTacticalGeometry(), InterTeamTacticalGeometry(), TacticalQualityState(True, True),
    )
    of_base = OrientedTacticalFrameState(
        1, 0.04,
        TeamOrientedTactics(team_label="TEAM_0", attack_direction=AttackDirection.POSITIVE_X, is_oriented=True, lines=base_lines, line_count=3, outfield_player_count=10),
        TeamOrientedTactics("TEAM_1"), 0.95,
    )

    st_base = engine.process_frame(1, 0.04, base_players, tf_base, of_base)
    base_proto = st_base.team_0.instantaneous_signature.best_prototype
    assert base_proto == "4-4-2"

    # Noise injection tests
    noise_results = {}
    for scale in [0.10, 0.25, 0.50, 1.00]:
        flips = 0
        dist_changes = []
        for _ in range(50):
            noisy_lines = []
            for l in base_lines:
                nx = l.mean_x_attack + float(rng.uniform(-scale, scale))
                noisy_lines.append(TacticalLine(l.line_id, l.player_track_ids, l.player_count, nx, nx, l.width_y_m, nx, 0.0, 0.95, l.candidate_semantic_name))
            ot_noisy = OrientedTacticalFrameState(
                1, 0.04,
                TeamOrientedTactics(team_label="TEAM_0", attack_direction=AttackDirection.POSITIVE_X, is_oriented=True, lines=noisy_lines, line_count=3, outfield_player_count=10),
                of_base.team_1, 0.95,
            )
            st_n = engine.process_frame(1, 0.04, base_players, tf_base, ot_noisy)
            sig_n = st_n.team_0.instantaneous_signature
            if sig_n.best_prototype != "4-4-2":
                flips += 1
            dist_changes.append(abs(sig_n.prototype_distances["4-4-2"] - st_base.team_0.instantaneous_signature.prototype_distances["4-4-2"]))
        noise_results[f"noise_{scale:.2f}m"] = {
            "mean_dist_change": float(np.mean(dist_changes)),
            "prototype_flips": flips,
            "stability_ratio": float((50 - flips) / 50.0),
        }

    # Missing defender dropout
    missing_players = [p for p in base_players if p.track_id != 3]
    missing_lines = [
        TacticalLine(0, [0, 1, 2], 3, -20.0, -20.0, 22.0, -20.0, 0.0, 0.95, "DEF"),
        base_lines[1], base_lines[2],
    ]
    ot_mis = OrientedTacticalFrameState(
        1, 0.04,
        TeamOrientedTactics(team_label="TEAM_0", attack_direction=AttackDirection.POSITIVE_X, is_oriented=True, lines=missing_lines, line_count=3, outfield_player_count=9),
        of_base.team_1, 0.95,
    )
    st_mis = engine.process_frame(1, 0.04, missing_players, tf_base, ot_mis)
    mis_sig = st_mis.team_0.instantaneous_signature

    pert_summary = {
        "coordinate_noise": noise_results,
        "missing_player_dropout": {
            "visible_outfield": mis_sig.visible_outfield_count,
            "visibility_class": mis_sig.visibility_class.value,
            "top_prototype": mis_sig.best_prototype,
            "distance_442": mis_sig.prototype_distances.get("4-4-2", 0.0),
            "distance_352": mis_sig.prototype_distances.get("3-5-2", 0.0),
        },
    }
    logger.info("Phase 16 summary: noise 0.10m stability=%.1f%%, noise 1.00m stability=%.1f%%",
                noise_results["noise_0.10m"]["stability_ratio"] * 100.0,
                noise_results["noise_1.00m"]["stability_ratio"] * 100.0)
    return pert_summary


# ==============================================================================
# PIPELINE EXECUTION FOR SINGLE SEQUENCE
# ==============================================================================

def run_single_sequence_formations(
    seq_name: str,
    seq_dir: Path,
    raw_dets_path: Path,
    cached_adapter: RobustCachedCalibAdapter,
    form_cfg: FormationConfig,
    frame_limit: int = 150,
    grid_search_cfgs: Optional[Dict[str, FormationConfig]] = None,
) -> Tuple[List[FormationFrameState], Dict[str, Any], Dict[str, List[FormationFrameState]]]:
    """Runs perception, tracking, calibration, geometry, lines, and formation inference on video frames."""
    logger.info("Processing %s up to %d frames...", seq_name, frame_limit)

    gameinfo_path = seq_dir / "gameinfo.ini"
    gt_txt_path = seq_dir / "gt" / "gt.txt"
    roles, teams = load_gameinfo_metadata(gameinfo_path)
    gt_bboxes_by_frame = load_gt_player_bboxes(gt_txt_path)

    with open(raw_dets_path, "rb") as f:
        dets_by_frame = pickle.load(f)

    # Initialize frozen pipeline modules
    calibrator = TemporalPitchCalibrator(adapter=cached_adapter, config=TemporalCalibrationConfig(max_keyframe_interval=10))
    p_tracker = PlayerBoTSORT(BoTSORTConfig(with_reid=False))
    b_tracker = BallTrackManager(create_ball_track_config_v2())
    traj_engine = MetricTrajectoryEngine(MetricTrajectoryConfig(smoothing_method=SmoothingMethod.KALMAN))
    tact_geom_engine = TacticalGeometryEngine(TacticalGeometryConfig())
    lines_engine = OrientedTacticsEngine(TacticalLineConfig())
    possession_engine = PossessionEngine(PossessionConfig())

    main_engine = DynamicFormationEngine(form_cfg)
    grid_engines = {k: DynamicFormationEngine(cfg) for k, cfg in (grid_search_cfgs or {}).items()}

    track_to_gt: Dict[int, int] = {}
    states: List[FormationFrameState] = []
    grid_states: Dict[str, List[FormationFrameState]] = {k: [] for k in (grid_search_cfgs or {})}
    latencies_ms: List[float] = []

    for fid in range(1, frame_limit + 1):
        timestamp = (fid - 1) / FPS
        fpath = seq_dir / "img1" / f"{fid:06d}.jpg"
        if not fpath.is_file():
            break
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

        bbox_map = {p["track_id"]: p["bbox"] for p in p_list}
        gt_curr = gt_bboxes_by_frame.get(fid, {})
        for p in player_obs:
            tid = p.track_id
            p_box = bbox_map.get(tid)
            if p_box is not None and gt_curr:
                best_iou = 0.30
                matched_gt = None
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
            else:
                p.role = roles.get(tid, "OUTFIELD_PLAYER")
                p.team_label = teams.get(tid, "TEAM_0" if (tid % 2 == 0) else "TEAM_1")

        tact_state = tact_geom_engine.process_frame(fid, timestamp, player_obs, ball_m_obs, calib_res.valid)
        lines_state = lines_engine.process_frame(fid, timestamp, player_obs, ball_m_obs, calib_res.valid)

        # Causal possession diagnostic
        poss_eval = possession_engine.control_estimator.evaluate(player_obs, ball_m_obs, calib_res.valid)
        poss_state, _ = possession_engine.state_machine.update(fid, timestamp, poss_eval)

        # Profile main formation inferer engine
        t0 = time.perf_counter()
        f_state = main_engine.process_frame(
            frame_index=fid,
            timestamp=timestamp,
            players=player_obs,
            tactical_geom=tact_state,
            oriented_tactics=lines_state,
            ball=ball_m_obs,
            ball_control=poss_state,
        )
        t1 = time.perf_counter()
        latencies_ms.append((t1 - t0) * 1000.0)
        states.append(f_state)

        # Grid search runs (if any)
        for g_k, g_eng in grid_engines.items():
            g_st = g_eng.process_frame(
                frame_index=fid,
                timestamp=timestamp,
                players=player_obs,
                tactical_geom=tact_state,
                oriented_tactics=lines_state,
                ball=ball_m_obs,
                ball_control=poss_state,
            )
            grid_states[g_k].append(g_st)

    timing_stats = {
        "mean_latency_ms": float(np.mean(latencies_ms)) if latencies_ms else 0.0,
        "median_latency_ms": float(np.median(latencies_ms)) if latencies_ms else 0.0,
        "p95_latency_ms": float(np.percentile(latencies_ms, 95)) if latencies_ms else 0.0,
        "max_latency_ms": float(np.max(latencies_ms)) if latencies_ms else 0.0,
        "total_frames": len(states),
    }

    return states, timing_stats, grid_states


# ==============================================================================
# GT EVALUATION & STRUCTURE METRICS
# ==============================================================================

def evaluate_sequence_against_gt(
    states: List[FormationFrameState],
    gt_intervals: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Compares predicted stable formations against ground truth intervals and computes structure metrics."""
    total_eval_frames = 0
    correct_frames = 0
    cat_pred: List[str] = []
    cat_gt: List[str] = []

    # Map intervals to frame-level GT
    frame_gt_map: Dict[int, Tuple[str, str]] = {}
    for interv in gt_intervals:
        s_f = interv["start_frame"]
        e_f = interv["end_frame"]
        t0_gt = interv["team_0"]
        t1_gt = interv["team_1"]
        for f in range(s_f, e_f + 1):
            frame_gt_map[f] = (t0_gt, t1_gt)

    # Structure-only counters
    line_count_matches = 0
    exact_line_matches = 0
    edit_distances: List[float] = []
    total_structure_frames = 0

    for st in states:
        fid = st.frame_index
        if fid not in frame_gt_map:
            continue

        gt_0, gt_1 = frame_gt_map[fid]

        # Team 0
        if gt_0 != "NOT_VISIBLE":
            total_eval_frames += 1
            pred_0 = st.team_0.stable_formation_label
            cat_pred.append(pred_0)
            cat_gt.append(gt_0)
            if pred_0 == gt_0:
                correct_frames += 1

            # Structure metric against gt_0 prototype if canonical
            if gt_0 in CANONICAL_PROTOTYPES:
                proto_obj = CANONICAL_PROTOTYPES[gt_0]
                obs_lines = st.team_0.instantaneous_signature.players_per_line
                total_structure_frames += 1
                if len(obs_lines) == proto_obj.line_count:
                    line_count_matches += 1
                if tuple(obs_lines) == proto_obj.expected_players_per_line:
                    exact_line_matches += 1
                dist, _ = compute_formation_distance(obs_lines, proto_obj.expected_players_per_line)
                edit_distances.append(dist)

        # Team 1
        if gt_1 != "NOT_VISIBLE":
            total_eval_frames += 1
            pred_1 = st.team_1.stable_formation_label
            cat_pred.append(pred_1)
            cat_gt.append(gt_1)
            if pred_1 == gt_1:
                correct_frames += 1

            if gt_1 in CANONICAL_PROTOTYPES:
                proto_obj = CANONICAL_PROTOTYPES[gt_1]
                obs_lines = st.team_1.instantaneous_signature.players_per_line
                total_structure_frames += 1
                if len(obs_lines) == proto_obj.line_count:
                    line_count_matches += 1
                if tuple(obs_lines) == proto_obj.expected_players_per_line:
                    exact_line_matches += 1
                dist, _ = compute_formation_distance(obs_lines, proto_obj.expected_players_per_line)
                edit_distances.append(dist)

    accuracy = (correct_frames / total_eval_frames) if total_eval_frames > 0 else 0.0

    # Macro metrics per class
    classes = sorted(list(set(cat_gt)))
    f1_list = []
    rec_list = []
    per_class_stats = {}

    for c in classes:
        tp = sum(1 for p, g in zip(cat_pred, cat_gt) if p == c and g == c)
        fp = sum(1 for p, g in zip(cat_pred, cat_gt) if p == c and g != c)
        fn = sum(1 for p, g in zip(cat_pred, cat_gt) if p != c and g == c)
        supp = sum(1 for g in cat_gt if g == c)

        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

        per_class_stats[c] = {
            "precision": float(prec),
            "recall": float(rec),
            "f1_score": float(f1),
            "support": supp,
        }
        f1_list.append(f1)
        rec_list.append(rec)

    macro_f1 = float(np.mean(f1_list)) if f1_list else 0.0
    balanced_acc = float(np.mean(rec_list)) if rec_list else 0.0

    structure_metrics = {
        "line_count_accuracy": float(line_count_matches / total_structure_frames) if total_structure_frames > 0 else 0.0,
        "players_per_line_exact_match": float(exact_line_matches / total_structure_frames) if total_structure_frames > 0 else 0.0,
        "mean_line_edit_distance": float(np.mean(edit_distances)) if edit_distances else 0.0,
    }

    return {
        "evaluable_frames": total_eval_frames,
        "accuracy": float(accuracy),
        "balanced_accuracy": float(balanced_acc),
        "macro_f1": float(macro_f1),
        "per_class": per_class_stats,
        "structure_metrics": structure_metrics,
    }


def compute_temporal_formation_stability(states: List[FormationFrameState]) -> Dict[str, Any]:
    """Measures formation switches per minute, mean duration, and state distributions."""
    if not states:
        return {}

    total_seconds = len(states) / FPS
    switches_0 = sum(1 for i in range(1, len(states)) if states[i].team_0.stable_formation_label != states[i - 1].team_0.stable_formation_label)
    switches_1 = sum(1 for i in range(1, len(states)) if states[i].team_1.stable_formation_label != states[i - 1].team_1.stable_formation_label)
    total_switches = switches_0 + switches_1
    switches_per_min = (total_switches / total_seconds) * 60.0 if total_seconds > 0 else 0.0

    state_counts_0 = Counter(s.team_0.stable_state.value for s in states)
    state_counts_1 = Counter(s.team_1.stable_state.value for s in states)
    total_team_frames = len(states) * 2

    return {
        "switches_per_minute": float(switches_per_min),
        "total_transitions": total_switches,
        "mean_state_duration_seconds": float(total_seconds / (total_switches / 2.0 + 1.0)),
        "state_distribution": {
            "STABLE_pct": float((state_counts_0["STABLE"] + state_counts_1["STABLE"]) / total_team_frames * 100.0),
            "TRANSITIONING_pct": float((state_counts_0["TRANSITIONING"] + state_counts_1["TRANSITIONING"]) / total_team_frames * 100.0),
            "AMBIGUOUS_pct": float((state_counts_0["AMBIGUOUS"] + state_counts_1["AMBIGUOUS"]) / total_team_frames * 100.0),
            "PARTIAL_pct": float((state_counts_0["PARTIAL"] + state_counts_1["PARTIAL"]) / total_team_frames * 100.0),
            "UNKNOWN_pct": float((state_counts_0["UNKNOWN"] + state_counts_1["UNKNOWN"]) / total_team_frames * 100.0),
        },
    }


# ==============================================================================
# VISUALIZATION RENDERING HELPERS (PHASE 26)
# ==============================================================================

def render_formation_pitch_diagram(
    state: FormationFrameState,
    sequence_id: str,
    output_png: Path,
) -> None:
    """Renders top-down 2D tactical pitch diagram with tactical lines and formation hypotheses."""
    output_png.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(12, 8), dpi=150)
    fig.patch.set_facecolor("#12161a")
    ax.set_facecolor("#1b2838")

    l = 105.0
    w = 68.0
    hl = l / 2.0
    hw = w / 2.0

    # Pitch Outline & Markings
    pitch_rect = patches.Rectangle((-hl, -hw), l, w, linewidth=1.5, edgecolor="white", facecolor="none")
    ax.add_patch(pitch_rect)
    ax.plot([0, 0], [-hw, hw], color="white", linewidth=1.2)
    center_circle = patches.Circle((0, 0), 9.15, linewidth=1.2, edgecolor="white", facecolor="none")
    ax.add_patch(center_circle)

    # Penalty areas
    pa_w, pa_h = 16.5, 40.32
    ax.add_patch(patches.Rectangle((-hl, -pa_h / 2), pa_w, pa_h, linewidth=1.2, edgecolor="white", facecolor="none"))
    ax.add_patch(patches.Rectangle((hl - pa_w, -pa_h / 2), pa_w, pa_h, linewidth=1.2, edgecolor="white", facecolor="none"))

    # Thirds guide lines (dashed gray)
    ax.plot([-hl + 35.0, -hl + 35.0], [-hw, hw], color="#6c757d", linestyle="--", linewidth=1.0, alpha=0.6)
    ax.plot([hl - 35.0, hl - 35.0], [-hw, hw], color="#6c757d", linestyle="--", linewidth=1.0, alpha=0.6)

    # Team 0 Elements
    t0 = state.team_0
    sig0 = t0.instantaneous_signature
    c0 = "#00d2d3"
    t0_title = f"Team 0: {t0.stable_formation_label} [{t0.stable_state.value}] ({t0.state_confidence:.2f})"

    for l_meta in sig0.observed_lines:
        px = l_meta["center_x_attack"]
        wy = l_meta["width_m"] / 2.0
        ax.plot([px, px], [-wy, wy], color=c0, linewidth=2.8, alpha=0.85)
        ax.scatter([px], [0.0], color=c0, s=100, edgecolors="white", zorder=5)
        ax.text(px, wy + 2.0, f"n={l_meta['player_count']}", color=c0, fontsize=8, ha="center")

    # Team 1 Elements
    t1 = state.team_1
    sig1 = t1.instantaneous_signature
    c1 = "#ff9f43"
    t1_title = f"Team 1: {t1.stable_formation_label} [{t1.stable_state.value}] ({t1.state_confidence:.2f})"

    for l_meta in sig1.observed_lines:
        px = -l_meta["center_x_attack"]  # Attack toward -X
        wy = l_meta["width_m"] / 2.0
        ax.plot([px, px], [-wy, wy], color=c1, linewidth=2.8, alpha=0.85)
        ax.scatter([px], [0.0], color=c1, s=100, edgecolors="white", zorder=5)
        ax.text(px, wy + 2.0, f"n={l_meta['player_count']}", color=c1, fontsize=8, ha="center")

    banner_text = (
        f"{sequence_id} — Frame {state.frame_index} (t={state.timestamp:.2f}s)\n"
        f"{t0_title} | Observed Lines: {sig0.players_per_line}\n"
        f"{t1_title} | Observed Lines: {sig1.players_per_line}"
    )
    ax.text(0.0, 38.0, banner_text, color="white", fontsize=10, weight="bold", ha="center",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#1e2227", edgecolor="#48dbfb", alpha=0.9))

    ax.set_xlim(-hl - 6, hl + 6)
    ax.set_ylim(-hw - 6, hw + 6)
    ax.set_xlabel("Pitch X (meters)", color="white")
    ax.set_ylabel("Pitch Y (meters)", color="white")
    ax.tick_params(colors="white")

    plt.tight_layout()
    plt.savefig(str(output_png), facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    logger.info("Saved formation pitch diagram to %s", output_png)


def render_formation_timeseries_plot(
    states: List[FormationFrameState],
    sequence_id: str,
    output_png: Path,
) -> None:
    """Renders 4-panel tactical formation timeseries."""
    output_png.parent.mkdir(parents=True, exist_ok=True)
    times = [s.timestamp for s in states]

    cnt0 = [s.team_0.instantaneous_signature.line_count for s in states]
    cnt1 = [s.team_1.instantaneous_signature.line_count for s in states]
    conf0 = [s.team_0.state_confidence for s in states]
    conf1 = [s.team_1.state_confidence for s in states]
    vis0 = [s.team_0.instantaneous_signature.visible_outfield_count for s in states]
    vis1 = [s.team_1.instantaneous_signature.visible_outfield_count for s in states]

    state_map = {"STABLE": 2, "PARTIAL": 1, "AMBIGUOUS": 0, "TRANSITIONING": -1, "UNKNOWN": -2}
    st0_num = [state_map.get(s.team_0.stable_state.value, -2) for s in states]
    st1_num = [state_map.get(s.team_1.stable_state.value, -2) for s in states]

    fig, axes = plt.subplots(4, 1, figsize=(14, 10), sharex=True, dpi=150)
    fig.patch.set_facecolor("#12161a")
    for ax in axes:
        ax.set_facecolor("#1b2838")
        ax.tick_params(colors="white")

    axes[0].set_title(f"Dynamic Formation Structure Tracking — {sequence_id}", color="white", fontsize=12, weight="bold")

    # Panel 1: Line Count
    axes[0].step(times, cnt0, where="post", color="#00d2d3", label="Team 0 Line Count", linewidth=1.8)
    axes[0].step(times, cnt1, where="post", color="#ff9f43", label="Team 1 Line Count", linewidth=1.8)
    axes[0].set_ylabel("Line Count", color="white")
    axes[0].set_ylim(0, 6)
    axes[0].legend(loc="upper right", facecolor="#1e2227", labelcolor="white", fontsize=8)

    # Panel 2: Outfield Visibility
    axes[1].plot(times, vis0, color="#00d2d3", label="Team 0 Visible Outfield (N/10)", linewidth=1.5)
    axes[1].plot(times, vis1, color="#ff9f43", label="Team 1 Visible Outfield (N/10)", linewidth=1.5)
    axes[1].axhline(9, color="green", linestyle=":", label="Full Evidence (N>=9)")
    axes[1].axhline(6, color="red", linestyle=":", label="Abstention Threshold (N<=6)")
    axes[1].set_ylabel("Visible Players", color="white")
    axes[1].set_ylim(0, 11)
    axes[1].legend(loc="lower right", facecolor="#1e2227", labelcolor="white", fontsize=8)

    # Panel 3: Confidence
    axes[2].plot(times, conf0, color="#00d2d3", label="Team 0 Confidence", linewidth=1.8)
    axes[2].plot(times, conf1, color="#ff9f43", label="Team 1 Confidence", linewidth=1.8)
    axes[2].set_ylabel("Confidence", color="white")
    axes[2].set_ylim(0.0, 1.05)
    axes[2].legend(loc="upper right", facecolor="#1e2227", labelcolor="white", fontsize=8)

    # Panel 4: Formation State
    axes[3].step(times, st0_num, where="post", color="#00d2d3", label="Team 0 State", linewidth=2.0)
    axes[3].step(times, [s + 0.1 for s in st1_num], where="post", color="#ff9f43", label="Team 1 State", linewidth=2.0)
    axes[3].set_yticks([-2, -1, 0, 1, 2])
    axes[3].set_yticklabels(["UNKNOWN", "TRANSITION", "AMBIGUOUS", "PARTIAL", "STABLE"], color="white")
    axes[3].set_ylabel("Formation State", color="white")
    axes[3].set_xlabel("Time (seconds)", color="white")
    axes[3].legend(loc="upper right", facecolor="#1e2227", labelcolor="white", fontsize=8)

    plt.tight_layout()
    plt.savefig(str(output_png), facecolor=fig.get_facecolor(), edgecolor="none")
    plt.close(fig)
    logger.info("Saved formation timeseries plot to %s", output_png)


# ==============================================================================
# MAIN BENCHMARK EXECUTION
# ==============================================================================

def main() -> None:
    logger.info("=" * 60)
    logger.info("STARTING EXP-21: DYNAMIC FORMATION STRUCTURE INFERENCE BENCHMARK")
    logger.info("=" * 60)

    tracking_base = Path("/media/adriano/Windows/datasets/SoccerNetTracking2023/train")
    tactics_runs_dir = Path("/media/adriano/Windows/runs/tactics")
    visuals_dir = tactics_runs_dir / "visuals"
    gt_path = PROJECT_ROOT / "docs" / "experiments" / "formation_gt_v1.json"
    report_path = PROJECT_ROOT / "docs" / "experiments" / "exp21_dynamic_formation.json"

    visuals_dir.mkdir(parents=True, exist_ok=True)

    # 1. Phase 15 Synthetic Scenarios
    synthetic_results = run_synthetic_tests()

    # 2. Phase 16 Perturbation Robustness
    perturbation_results = run_perturbation_tests()

    # 3. Load Ground Truth
    with open(gt_path, "r") as f:
        gt_data = json.load(f)

    # 4. Setup Cached Adapter
    cached_adapter = RobustCachedCalibAdapter(disk_cache_path=tactics_runs_dir / "calib_cache.pkl")

    dev_limits = {"SNMOT-060": 750, "SNMOT-061": 150, "SNMOT-062": 150, "SNMOT-063": 150, "SNMOT-064": 150, "SNMOT-065": 150}
    holdout_limits = {"SNMOT-066": 150, "SNMOT-067": 150, "SNMOT-068": 150, "SNMOT-069": 750, "SNMOT-070": 150, "SNMOT-071": 150}

    locked_cfg = FormationConfig(temporal_window_frames=50)
    grid_cfgs = {
        "W=25": FormationConfig(temporal_window_frames=25),
        "W=50": FormationConfig(temporal_window_frames=50),
        "W=75": FormationConfig(temporal_window_frames=75),
    }

    dev_results: Dict[str, Any] = {}
    holdout_results: Dict[str, Any] = {}
    dev_states_map: Dict[str, List[FormationFrameState]] = {}
    holdout_states_map: Dict[str, List[FormationFrameState]] = {}
    dev_timings: Dict[str, Any] = {}
    holdout_timings: Dict[str, Any] = {}
    grid_dev_states: Dict[str, Dict[str, List[FormationFrameState]]] = {}

    # Run DEV Sequences
    for s_name, n_f in dev_limits.items():
        s_dir = tracking_base / s_name
        gt_intervals = gt_data["DEV"].get(s_name, [])
        s_grid_cfgs = grid_cfgs if s_name == "SNMOT-060" else None

        states, t_stat, g_states = run_single_sequence_formations(
            seq_name=s_name,
            seq_dir=s_dir,
            raw_dets_path=RAW_DETS_MAP[s_name],
            cached_adapter=cached_adapter,
            form_cfg=locked_cfg,
            frame_limit=n_f,
            grid_search_cfgs=s_grid_cfgs,
        )

        dev_states_map[s_name] = states
        dev_timings[s_name] = t_stat
        if g_states:
            grid_dev_states[s_name] = g_states

        gt_eval = evaluate_sequence_against_gt(states, gt_intervals)
        stab_eval = compute_temporal_formation_stability(states)

        dev_results[s_name] = {
            "gt_evaluation": gt_eval,
            "temporal_stability": stab_eval,
            "timing": t_stat,
        }

    # Run HOLDOUT Sequences
    for s_name, n_f in holdout_limits.items():
        s_dir = tracking_base / s_name
        gt_intervals = gt_data["HOLDOUT"].get(s_name, [])

        states, t_stat, _ = run_single_sequence_formations(
            seq_name=s_name,
            seq_dir=s_dir,
            raw_dets_path=RAW_DETS_MAP[s_name],
            cached_adapter=cached_adapter,
            form_cfg=locked_cfg,
            frame_limit=n_f,
        )

        holdout_states_map[s_name] = states
        holdout_timings[s_name] = t_stat

        gt_eval = evaluate_sequence_against_gt(states, gt_intervals)
        stab_eval = compute_temporal_formation_stability(states)

        holdout_results[s_name] = {
            "gt_evaluation": gt_eval,
            "temporal_stability": stab_eval,
            "timing": t_stat,
        }

    # Grid Search Analysis on SNMOT-060
    grid_search_summary = {}
    if "SNMOT-060" in grid_dev_states:
        for w_val, g_sts in grid_dev_states["SNMOT-060"].items():
            stab = compute_temporal_formation_stability(g_sts)
            ev = evaluate_sequence_against_gt(g_sts, gt_data["DEV"]["SNMOT-060"])
            grid_search_summary[w_val] = {
                "switches_per_minute": stab["switches_per_minute"],
                "mean_duration_s": stab["mean_state_duration_seconds"],
                "accuracy": ev["accuracy"],
                "macro_f1": ev["macro_f1"],
                "stable_pct": stab["state_distribution"]["STABLE_pct"],
            }
        logger.info("DEV Grid Search (SNMOT-060): %s", grid_search_summary)

    # Aggregated DEV Metrics
    dev_accs = [r["gt_evaluation"]["accuracy"] for r in dev_results.values() if r["gt_evaluation"]["evaluable_frames"] > 0]
    dev_f1s = [r["gt_evaluation"]["macro_f1"] for r in dev_results.values() if r["gt_evaluation"]["evaluable_frames"] > 0]
    dev_mean_acc = float(np.mean(dev_accs)) if dev_accs else 0.0
    dev_mean_f1 = float(np.mean(dev_f1s)) if dev_f1s else 0.0

    # Aggregated HOLDOUT Metrics
    holdout_accs = [r["gt_evaluation"]["accuracy"] for r in holdout_results.values() if r["gt_evaluation"]["evaluable_frames"] > 0]
    holdout_f1s = [r["gt_evaluation"]["macro_f1"] for r in holdout_results.values() if r["gt_evaluation"]["evaluable_frames"] > 0]
    holdout_mean_acc = float(np.mean(holdout_accs)) if holdout_accs else 0.0
    holdout_mean_f1 = float(np.mean(holdout_f1s)) if holdout_f1s else 0.0

    # Overall Timing
    all_latencies = [t["mean_latency_ms"] for t in list(dev_timings.values()) + list(holdout_timings.values())]
    all_p95s = [t["p95_latency_ms"] for t in list(dev_timings.values()) + list(holdout_timings.values())]
    overall_mean_latency = float(np.mean(all_latencies)) if all_latencies else 0.0
    overall_p95_latency = float(np.mean(all_p95s)) if all_p95s else 0.0

    logger.info("=" * 60)
    logger.info("EXP-21 BENCHMARK SUMMARY")
    logger.info("DEV Mean Accuracy     : %.2f%% | Mean Macro F1: %.4f", dev_mean_acc * 100.0, dev_mean_f1)
    logger.info("HOLDOUT Mean Accuracy : %.2f%% | Mean Macro F1: %.4f", holdout_mean_acc * 100.0, holdout_mean_f1)
    logger.info("Incremental Latency   : %.4f ms/frame (P95: %.4f ms/frame)", overall_mean_latency, overall_p95_latency)
    logger.info("Budget Compliance     : %s (target < 0.30 ms/frame)", "COMPLIANT" if overall_mean_latency < 0.30 else "EXCEEDED")
    logger.info("=" * 60)

    # 5. Render Visualizations
    render_formation_pitch_diagram(
        dev_states_map["SNMOT-060"][100], "SNMOT-060", visuals_dir / "SNMOT-060_formation_pitch.png"
    )
    render_formation_timeseries_plot(
        dev_states_map["SNMOT-060"], "SNMOT-060", visuals_dir / "SNMOT-060_formation_timeseries.png"
    )
    render_formation_pitch_diagram(
        holdout_states_map["SNMOT-069"][100], "SNMOT-069", visuals_dir / "SNMOT-069_formation_pitch.png"
    )
    render_formation_timeseries_plot(
        holdout_states_map["SNMOT-069"], "SNMOT-069", visuals_dir / "SNMOT-069_formation_timeseries.png"
    )

    # 6. Save Official Benchmark JSON
    official_data = {
        "experiment": "EXP-21",
        "description": "Dynamic Formation Structure Inference Benchmark",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "platform": f"{sys.platform}",
        "python_version": sys.version,
        "config": {
            "full_evidence_threshold": locked_cfg.full_evidence_threshold,
            "partial_evidence_threshold": locked_cfg.partial_evidence_threshold,
            "low_evidence_threshold": locked_cfg.low_evidence_threshold,
            "temporal_window_frames": locked_cfg.temporal_window_frames,
            "min_consensus_ratio": locked_cfg.min_consensus_ratio,
            "ambiguity_margin": locked_cfg.ambiguity_margin,
            "wingback_ambiguity_threshold": locked_cfg.wingback_ambiguity_threshold,
        },
        "synthetic_verification": synthetic_results,
        "perturbation_analysis": perturbation_results,
        "grid_search_window_dev": grid_search_summary,
        "overall_summary": {
            "dev_mean_accuracy": dev_mean_acc,
            "dev_mean_macro_f1": dev_mean_f1,
            "holdout_mean_accuracy": holdout_mean_acc,
            "holdout_mean_macro_f1": holdout_mean_f1,
            "incremental_latency_ms": overall_mean_latency,
            "p95_latency_ms": overall_p95_latency,
            "budget_target_ms": 0.30,
            "is_budget_compliant": bool(overall_mean_latency < 0.30),
            "total_frames_evaluated": sum(d["timing"]["total_frames"] for d in list(dev_results.values()) + list(holdout_results.values())),
        },
        "dev_sequences": dev_results,
        "holdout_sequences": holdout_results,
    }

    with open(report_path, "w") as f:
        json.dump(official_data, f, indent=2)
    logger.info("Saved official EXP-21 benchmark JSON to %s", report_path)


if __name__ == "__main__":
    main()
