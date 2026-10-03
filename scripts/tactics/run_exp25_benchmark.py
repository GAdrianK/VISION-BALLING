#!/usr/bin/env python3
"""EXP-25: Tactical Event Fusion, Confidence Propagation & Evidence Cards Benchmark Runner.

Executes:
1. Multi-sequence end-to-end integration across DEV and HOLDOUT splits (350 frames/seq)
2. Ingestion of all Chapter 7 upstream modules (EXP-15 to EXP-24)
3. Causal continuous episode segmentation (PressureIndex and Defensive Block)
4. Confidence propagation with strict upstream dependency ceilings
5. Quality-tier attribution (HIGH, MEDIUM, LOW, INVALID)
6. Deduplication and causal/evidential relation graph construction
7. Contradiction auditing and confidence discounting
8. Deterministic human-readable evidence summaries
9. Team tactical summaries with explicit reliability bands
10. Steady-state runtime profiling (< 1.0 ms/frame budget)
11. Serialization of match_timeline.jsonl, tactical_events.json, team_summary.json, event_graph.json
12. Generation of match intelligence dashboard visual artifact
13. Compiles docs/experiments/exp25_tactical_event_fusion.json
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
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import matplotlib.patches as patches
import matplotlib.pyplot as plt
import numpy as np

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
)
from app.video_analysis.tactical_transitions import (
    TacticalTransitionsConfig,
    TacticalTransitionsEngine,
)
from app.video_analysis.pass_detector import (
    PassDetectorConfig,
    PassEventDetector,
)
from app.video_analysis.formation_inferer import (
    FormationConfig,
    DynamicFormationEngine,
)
from app.video_analysis.tactical_fusion import (
    TacticalFusionEngine,
    TacticalEvidenceEvent,
    EventFamily,
    SemanticLevel,
    QualityLevel,
    RelationType,
    ContinuousEpisodeConfig,
    MatchTacticalTimeline,
    EventRelationGraph,
    TeamTacticalAggregate,
    TeamReliabilityBand,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("EXP-25-BENCHMARK")

FPS = 25.0
NUM_FRAMES_PER_SEQ = 350

# Split definitions
FUSION_TRAIN = ["SNMOT-060", "SNMOT-061", "SNMOT-063"]
FUSION_DEV = ["SNMOT-062", "SNMOT-064", "SNMOT-067", "SNMOT-068"]
FUSION_HOLDOUT = ["SNMOT-065", "SNMOT-066", "SNMOT-069", "SNMOT-070", "SNMOT-071"]
ALL_SEQUENCES = FUSION_DEV + FUSION_HOLDOUT

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
# CALIBRATION ADAPTER & HELPERS
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


def load_sequence_roles_and_gameinfo(seq_dir: Path) -> Tuple[Dict[int, str], Dict[int, str]]:
    gi_path = seq_dir / "gameinfo.ini"
    roles: Dict[int, str] = {}
    teams: Dict[int, str] = {}
    if not gi_path.exists():
        return roles, teams

    cfg = configparser.ConfigParser()
    cfg.read(gi_path)
    if not cfg.has_section("Sequence"):
        return roles, teams

    for k, v in cfg.items("Sequence"):
        if k.startswith("trackletid_"):
            try:
                tid = int(k.split("_")[1])
                parts = [p.strip() for p in v.split(";")]
                desc = parts[0]
                if desc.startswith("player"):
                    roles[tid] = "OUTFIELD_PLAYER"
                    teams[tid] = "TEAM_0" if "left" in desc else "TEAM_1"
                elif desc.startswith("goalkeeper"):
                    roles[tid] = "GOALKEEPER"
                    teams[tid] = "TEAM_0" if "left" in desc else "TEAM_1"
                elif desc.startswith("referee"):
                    roles[tid] = "REFEREE"
                    teams[tid] = "REFEREE"
            except (ValueError, IndexError):
                pass
    return roles, teams


def load_gt_bboxes_by_frame(seq_dir: Path) -> Dict[int, Dict[int, List[float]]]:
    gt_path = seq_dir / "gt" / "gt.txt"
    gt_by_frame: Dict[int, Dict[int, List[float]]] = {}
    if not gt_path.exists():
        return gt_by_frame

    with open(gt_path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split(",")
            if len(parts) >= 6:
                fid = int(parts[0])
                tid = int(parts[1])
                x = float(parts[2])
                y = float(parts[3])
                w = float(parts[4])
                h = float(parts[5])
                if fid not in gt_by_frame:
                    gt_by_frame[fid] = {}
                gt_by_frame[fid][tid] = [x, y, x + w, y + h]
    return gt_by_frame


def compute_iou(box_a: List[float], box_b: List[float]) -> float:
    x_left = max(box_a[0], box_b[0])
    y_top = max(box_a[1], box_b[1])
    x_right = min(box_a[2], box_b[2])
    y_bottom = min(box_a[3], box_b[3])
    if x_right < x_left or y_bottom < y_top:
        return 0.0
    inter_area = (x_right - x_left) * (y_bottom - y_top)
    box_a_area = max(0.0, box_a[2] - box_a[0]) * max(0.0, box_a[3] - box_a[1])
    box_b_area = max(0.0, box_b[2] - box_b[0]) * max(0.0, box_b[3] - box_b[1])
    union_area = box_a_area + box_b_area - inter_area
    if union_area <= 0.0:
        return 0.0
    return float(inter_area / union_area)


# ==============================================================================
# PIPELINE EXECUTION FOR ONE SEQUENCE
# ==============================================================================

def run_sequence_fusion(
    seq_name: str,
    seq_dir: Path,
    raw_dets_path: Path,
    cached_adapter: RobustCachedCalibAdapter,
    num_frames: int = NUM_FRAMES_PER_SEQ,
) -> Tuple[TacticalFusionEngine, Dict[str, Any], Dict[str, Any]]:
    """Runs the full Chapter 7 upstream stack and TacticalFusionEngine on a sequence."""
    logger.info("Executing Tactical Event Fusion on sequence %s (%d frames)...", seq_name, num_frames)

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
    traj_engine = MetricTrajectoryEngine(config=MetricTrajectoryConfig(smoothing_method=SmoothingMethod.KALMAN, pitch_dimensions=pitch_dim))

    tact_geom_engine = TacticalGeometryEngine(config=TacticalGeometryConfig(include_goalkeeper_in_shape=False, pitch_dimensions=pitch_dim))
    lines_engine = OrientedTacticsEngine(config=TacticalLineConfig(pitch_dimensions=pitch_dim, min_line_gap_m=6.0, min_players_for_tactics=4))
    def_block_engine = DefensiveBlockEngine(config=DefensiveBlockConfig(pitch_dimensions=pitch_dim))
    possession_engine_v2 = PossessionEngineV2(config=PossessionConfigV2())
    pressure_engine = DefensivePressureEngine(config=DefensivePressureConfig())
    transition_engine = TacticalTransitionsEngine(config=TacticalTransitionsConfig())
    pass_detector = PassEventDetector(config=PassDetectorConfig())
    formation_engine = DynamicFormationEngine(config=FormationConfig())

    # EXP-25 Integration Engine
    fusion_engine = TacticalFusionEngine(sequence_id=seq_name, fps=FPS)

    fusion_latencies_ms: List[float] = []

    # Diagnostics to keep for visualization
    saved_frames_data: Dict[str, Any] = {
        "pressure_team0": [],
        "pressure_team1": [],
        "block_height_team0": [],
        "block_height_team1": [],
        "snapshots": {},
    }

    for fid in range(1, num_frames + 1):
        timestamp = (fid - 1) / FPS
        fpath = img1_dir / f"{fid:06d}.jpg"
        im = cv2.imread(str(fpath))
        if im is None:
            continue

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
            else:
                p.role = roles.get(tid, "OUTFIELD_PLAYER")
                p.team_label = teams.get(tid, "TEAM_0" if (tid % 2 == 0) else "TEAM_1")

        # Tactical stack
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
        poss_state = possession_engine_v2.process_frame(
            frame_index=fid,
            timestamp=timestamp,
            player_observations=player_obs,
            ball_observation=ball_m_obs,
            calibration_valid=calib_res.valid,
        )
        press_state = pressure_engine.process_frame(
            frame_index=fid,
            timestamp=timestamp,
            player_observations=player_obs,
            ball_observation=ball_m_obs,
            possession_state_v2=poss_state,
            block_frame_state=block_state,
            calibration_valid=calib_res.valid,
        )
        trans_state = transition_engine.process_frame(
            frame_index=fid,
            timestamp=timestamp,
            player_observations=player_obs,
            ball_observation=ball_m_obs,
            possession_state_v2=poss_state,
            pressure_state=press_state,
            block_frame_state=block_state,
            oriented_tactics_state=lines_state,
            calibration_valid=calib_res.valid,
        )
        pass_state = pass_detector.process_frame(
            frame_index=fid,
            timestamp=timestamp,
            player_observations=player_obs,
            ball_observation=ball_m_obs,
            possession_state=poss_state,
            calibration_valid=calib_res.valid,
            sequence_id=seq_name,
        )
        formation_state = formation_engine.process_frame(
            frame_index=fid,
            timestamp=timestamp,
            players=player_obs,
            tactical_geom=tact_geom_state,
            oriented_tactics=lines_state,
            ball=ball_m_obs,
            ball_control=poss_state,
        )

        # Count visible outfield players
        n_t0 = sum(1 for p in player_obs if p.team_label == "TEAM_0" and p.role == "OUTFIELD_PLAYER")
        n_t1 = sum(1 for p in player_obs if p.team_label == "TEAM_1" and p.role == "OUTFIELD_PLAYER")

        # Record timeseries for visual dashboard
        b0_h = block_state.team_0.defensive_line_height_m if block_state and block_state.team_0 else None
        b1_h = block_state.team_1.defensive_line_height_m if block_state and block_state.team_1 else None
        saved_frames_data["block_height_team0"].append((fid, timestamp, b0_h))
        saved_frames_data["block_height_team1"].append((fid, timestamp, b1_h))

        p_idx = press_state.pressure_index if press_state else 0.0
        def_t = press_state.defending_team if press_state else "UNKNOWN"
        saved_frames_data["pressure_team0"].append((fid, timestamp, p_idx if def_t == "TEAM_0" else 0.0))
        saved_frames_data["pressure_team1"].append((fid, timestamp, p_idx if def_t == "TEAM_1" else 0.0))

        # Save snapshot around frame 80 for 2D pitch diagram
        if fid == 80:
            saved_frames_data["snapshots"][80] = {
                "player_obs": [(p.track_id, p.team_label, p.role, p.pitch_x_m, p.pitch_y_m) for p in player_obs if p.pitch_x_m is not None and p.pitch_y_m is not None],
                "ball_obs": (ball_m_obs.pitch_x_m, ball_m_obs.pitch_y_m) if ball_m_obs and ball_m_obs.pitch_x_m is not None else None,
                "block_0_height": b0_h,
                "block_1_height": b1_h,
                "pressure_state": press_state,
            }

        # === EXP-25 FUSION INGESTION & LATENCY PROFILING ===
        t_fus_0 = time.perf_counter()

        # Ingest frame
        fusion_engine.ingest_frame(
            frame_idx=fid,
            timestamp=timestamp,
            block_metrics_team0=block_state.team_0 if block_state else None,
            block_metrics_team1=block_state.team_1 if block_state else None,
            possession_status=poss_state.possession_status.value if poss_state else "UNKNOWN",
            possessing_team=poss_state.possession_team if poss_state else "UNKNOWN",
            possession_confidence=poss_state.possession_confidence if poss_state else 0.5,
            pressure_state=press_state,
            formation_state_team0=formation_state.team_0 if formation_state else None,
            formation_state_team1=formation_state.team_1 if formation_state else None,
            calibration_valid=calib_res.valid,
            visible_players_t0=n_t0,
            visible_players_t1=n_t1,
        )

        # Ingest turnover if triggered
        if poss_state and poss_state.recent_possession_change is not None:
            fusion_engine.ingest_possession_change_event(
                poss_state.recent_possession_change,
                calibration_valid=calib_res.valid,
                visible_players=n_t0 if getattr(poss_state.recent_possession_change, "from_team", getattr(poss_state.recent_possession_change, "losing_team", "")) == "TEAM_0" else n_t1,
            )

        # Ingest transition candidate if confirmed on this frame
        if trans_state and trans_state.active_event is not None and trans_state.active_event.is_confirmed:
            if trans_state.active_event.confirmation_frame_index == fid:
                fusion_engine.ingest_transition_event(
                    trans_state.active_event,
                    calibration_valid=calib_res.valid,
                    visible_players=trans_state.active_event.visible_outfield_count,
                )

        # Ingest pass event if finalized on this frame
        if pass_state and pass_state.recent_finalized_event is not None:
            fusion_engine.ingest_pass_event(
                pass_state.recent_finalized_event,
                calibration_valid=calib_res.valid,
            )

        t_fus_1 = time.perf_counter()
        fusion_latencies_ms.append((t_fus_1 - t_fus_0) * 1000.0)

    # Finalize sequence fusion
    timeline, graph, team_summaries = fusion_engine.finalize(
        last_frame=num_frames,
        last_timestamp=(num_frames - 1) / FPS,
    )

    stats = {
        "sequence_id": seq_name,
        "frames_evaluated": num_frames,
        "total_events": len(timeline.events),
        "graph_node_count": len(graph.nodes),
        "graph_edge_count": len(graph.edges),
        "latency_ms": {
            "mean": float(np.mean(fusion_latencies_ms)) if fusion_latencies_ms else 0.0,
            "median": float(np.median(fusion_latencies_ms)) if fusion_latencies_ms else 0.0,
            "p95": float(np.percentile(fusion_latencies_ms, 95)) if fusion_latencies_ms else 0.0,
            "max": float(np.max(fusion_latencies_ms)) if fusion_latencies_ms else 0.0,
        },
    }

    logger.info(
        "Sequence %s completed: %d events, %d edges. Fusion latency: mean=%.4f ms, P95=%.4f ms",
        seq_name, len(timeline.events), len(graph.edges), stats["latency_ms"]["mean"], stats["latency_ms"]["p95"]
    )

    return fusion_engine, stats, saved_frames_data, team_summaries


# ==============================================================================
# VISUALIZATION DASHBOARD ARTIFACT (PHASE 25)
# ==============================================================================

def generate_match_intelligence_dashboard(
    seq_name: str,
    timeline: MatchTacticalTimeline,
    graph: EventRelationGraph,
    team_summaries: Dict[str, TeamTacticalAggregate],
    saved_frames: Dict[str, Any],
    output_png_path: Path,
) -> None:
    """Generates a 4-panel tactical match intelligence dashboard artifact."""
    output_png_path.parent.mkdir(parents=True, exist_ok=True)

    fig = plt.figure(figsize=(18, 12), facecolor="#0e1117")
    gs = fig.add_gridspec(3, 2, height_ratios=[1.2, 1.0, 1.2], hspace=0.32, wspace=0.22)

    # Palette
    c_t0 = "#3498db"  # blue
    c_t1 = "#e74c3c"  # red
    c_neut = "#95a5a6" # gray
    c_bg = "#161b22"
    c_text = "#ecf0f1"

    # Panel 1: Multi-scale Tactical Event Timeline (Top Full Width)
    ax_timeline = fig.add_subplot(gs[0, :])
    ax_timeline.set_facecolor(c_bg)
    ax_timeline.set_title(f"MATCH TACTICAL TIMELINE & EVIDENCE CARDS — {seq_name}", color=c_text, fontsize=13, fontweight="bold", pad=12)

    # Plot events as horizontal spans and markers
    events = timeline.events
    y_map = {
        EventFamily.POSSESSION_CHANGE: 5,
        EventFamily.POST_LOSS_ENGAGEMENT: 4,
        EventFamily.DEFENSIVE_RECOVERY: 3,
        EventFamily.PRESSURE_EPISODE: 2,
        EventFamily.BLOCK_STATE: 1,
        EventFamily.BALL_TRANSFER: 0,
    }
    y_labels = [
        "Ball Transfer",
        "Block State",
        "Pressure Episode",
        "Def. Recovery",
        "Post-Loss Press",
        "Possession Change",
    ]

    for e in events:
        y = y_map.get(e.event_family, 2)
        color = c_t0 if e.subject_team == "TEAM_0" else (c_t1 if e.subject_team == "TEAM_1" else c_neut)
        alpha = 0.35 + 0.65 * e.confidence
        t0 = e.start_timestamp
        t1 = max(t0 + 0.15, e.end_timestamp)

        # Bar
        ax_timeline.barh(y, t1 - t0, left=t0, height=0.45, color=color, alpha=alpha, edgecolor="#ffffff", linewidth=0.6)

        # Confidence tag for significant events
        if e.event_family in (EventFamily.POSSESSION_CHANGE, EventFamily.POST_LOSS_ENGAGEMENT, EventFamily.DEFENSIVE_RECOVERY):
            lbl = f"c={e.confidence:.2f} [{e.quality_level.value[0]}]"
            ax_timeline.text((t0 + t1) / 2, y + 0.28, lbl, color=c_text, fontsize=8, ha="center", va="bottom", fontweight="bold")

    ax_timeline.set_yticks(range(6))
    ax_timeline.set_yticklabels(y_labels, color=c_text, fontsize=10)
    ax_timeline.set_xlabel("Match Time (seconds)", color=c_text, fontsize=10)
    ax_timeline.set_xlim(0, 14.0)
    ax_timeline.tick_params(colors=c_text)
    ax_timeline.grid(True, color="#2c3e50", linestyle="--", alpha=0.5)

    # Panel 2: Continuous Defensive PressureIndex (Middle Left)
    ax_press = fig.add_subplot(gs[1, 0])
    ax_press.set_facecolor(c_bg)
    ax_press.set_title("CONTINUOUS DEFENSIVE PRESSURE INDEX (EXP-23)", color=c_text, fontsize=11, fontweight="bold")

    p0_times = [p[1] for p in saved_frames["pressure_team0"]]
    p0_vals = [p[2] for p in saved_frames["pressure_team0"]]
    p1_times = [p[1] for p in saved_frames["pressure_team1"]]
    p1_vals = [p[2] for p in saved_frames["pressure_team1"]]

    ax_press.plot(p0_times, p0_vals, color=c_t0, label="TEAM_0 Pressure", linewidth=1.8)
    ax_press.plot(p1_times, p1_vals, color=c_t1, label="TEAM_1 Pressure", linewidth=1.8)
    ax_press.axhline(0.45, color="#f1c40f", linestyle="--", alpha=0.7, label="Enter Threshold (0.45)")
    ax_press.axhline(0.25, color="#27ae60", linestyle=":", alpha=0.7, label="Exit Threshold (0.25)")
    ax_press.set_ylabel("PressureIndex [0, 1]", color=c_text, fontsize=10)
    ax_press.set_ylim(-0.05, 1.05)
    ax_press.tick_params(colors=c_text)
    ax_press.legend(loc="upper right", facecolor="#1e272e", edgecolor="none", fontsize=8, labelcolor=c_text)
    ax_press.grid(True, color="#2c3e50", linestyle="--", alpha=0.5)

    # Panel 3: Continuous Defensive Block Height (Middle Right)
    ax_block = fig.add_subplot(gs[1, 1])
    ax_block.set_facecolor(c_bg)
    ax_block.set_title("DEFENSIVE BLOCK HEIGHT & COMPACTNESS (EXP-20)", color=c_text, fontsize=11, fontweight="bold")

    b0_times = [b[1] for b in saved_frames["block_height_team0"] if b[2] is not None]
    b0_vals = [b[2] for b in saved_frames["block_height_team0"] if b[2] is not None]
    b1_times = [b[1] for b in saved_frames["block_height_team1"] if b[2] is not None]
    b1_vals = [b[2] for b in saved_frames["block_height_team1"] if b[2] is not None]

    if b0_times:
        ax_block.plot(b0_times, b0_vals, color=c_t0, label="TEAM_0 Line Height", linewidth=1.8)
    if b1_times:
        ax_block.plot(b1_times, b1_vals, color=c_t1, label="TEAM_1 Line Height", linewidth=1.8)

    ax_block.axhline(35.0, color="#e67e22", linestyle="--", alpha=0.7, label="Low Block Ceiling (35m)")
    ax_block.axhline(52.5, color="#9b59b6", linestyle="--", alpha=0.7, label="Midfield Line (52.5m)")
    ax_block.set_ylabel("Height from Own Goal (m)", color=c_text, fontsize=10)
    ax_block.set_ylim(15.0, 75.0)
    ax_block.tick_params(colors=c_text)
    ax_block.legend(loc="upper right", facecolor="#1e272e", edgecolor="none", fontsize=8, labelcolor=c_text)
    ax_block.grid(True, color="#2c3e50", linestyle="--", alpha=0.5)

    # Panel 4: 2D Pitch Spatial Snapshot (Bottom Left)
    ax_pitch = fig.add_subplot(gs[2, 0])
    ax_pitch.set_facecolor("#1b381e")  # pitch green
    ax_pitch.set_title("2D METRIC PITCH SNAPSHOT AT TRANSITION ONSET (Frame 80)", color=c_text, fontsize=11, fontweight="bold")

    # Draw pitch outline
    pitch_len, pitch_wid = 105.0, 68.0
    ax_pitch.plot([-pitch_len/2, pitch_len/2, pitch_len/2, -pitch_len/2, -pitch_len/2],
                  [-pitch_wid/2, -pitch_wid/2, pitch_wid/2, pitch_wid/2, -pitch_wid/2], color="white", alpha=0.6)
    ax_pitch.axvline(0, color="white", alpha=0.6)
    circle = plt.Circle((0, 0), 9.15, color="white", fill=False, alpha=0.6)
    ax_pitch.add_patch(circle)

    snap = saved_frames.get("snapshots", {}).get(80)
    if snap:
        for tid, team, role, xm, ym in snap["player_obs"]:
            col = c_t0 if team == "TEAM_0" else c_t1
            marker = "s" if role == "GOALKEEPER" else "o"
            ax_pitch.scatter(xm, ym, color=col, s=80, marker=marker, edgecolors="white", linewidths=1.0, zorder=4)
        if snap["ball_obs"]:
            bx, by = snap["ball_obs"]
            ax_pitch.scatter(bx, by, color="#f1c40f", s=90, marker="*", edgecolors="black", zorder=5, label="Ball")

    ax_pitch.set_xlim(-pitch_len/2 - 2, pitch_len/2 + 2)
    ax_pitch.set_ylim(-pitch_wid/2 - 2, pitch_wid/2 + 2)
    ax_pitch.set_xlabel("Pitch X (m)", color=c_text, fontsize=9)
    ax_pitch.set_ylabel("Pitch Y (m)", color=c_text, fontsize=9)
    ax_pitch.tick_params(colors=c_text)

    # Panel 5: Team Tactical Aggregates & Reliability Summary Table (Bottom Right)
    ax_table = fig.add_subplot(gs[2, 1])
    ax_table.set_facecolor(c_bg)
    ax_table.axis("off")
    ax_table.set_title("TEAM TACTICAL AGGREGATES & RELIABILITY BANDS", color=c_text, fontsize=11, fontweight="bold")

    t0_sum = team_summaries["TEAM_0"]
    t1_sum = team_summaries["TEAM_1"]

    table_data = [
        ["Metric Primitive", "TEAM_0", "TEAM_1", "Reliability Band"],
        ["Secure Possession (%)", f"{t0_sum.secure_possession_pct:.1f}%", f"{t1_sum.secure_possession_pct:.1f}%", f"Coverage: {t0_sum.reliability.coverage_pct:.0f}%"],
        ["Def. Line Height (m)", f"{t0_sum.mean_defensive_line_height_m or 0.0:.1f} m", f"{t1_sum.mean_defensive_line_height_m or 0.0:.1f} m", f"Confidence: {t0_sum.reliability.confidence_mean:.2f}"],
        ["Team Depth / Width", f"{t0_sum.mean_team_depth_m or 0.0:.1f}m / {t0_sum.mean_team_width_m or 0.0:.1f}m", f"{t1_sum.mean_team_depth_m or 0.0:.1f}m / {t1_sum.mean_team_width_m or 0.0:.1f}m", "Metric Trajectories (EXP-15)"],
        ["Mean PressureIndex", f"{t0_sum.mean_pressure_index:.2f} (peak {t0_sum.peak_pressure_index:.2f})", f"{t1_sum.mean_pressure_index:.2f} (peak {t1_sum.peak_pressure_index:.2f})", f"P10 Conf: {t0_sum.reliability.confidence_p10:.2f}"],
        ["Counterpress Score", f"{t0_sum.post_loss_counterpress_mean:.2f}", f"{t1_sum.post_loss_counterpress_mean:.2f}", "EXP-24 Causal Transition"],
        ["Completed Transfers", f"{t0_sum.completed_pass_count}", f"{t1_sum.completed_pass_count}", "Quality-Gated (EXP-19)"],
        ["Formation Consensus", f"{t0_sum.formation_hypothesis or 'Fluid Line Shape'}", f"{t1_sum.formation_hypothesis or 'Fluid Line Shape'}", "Lines Primary (EXP-21)"],
    ]

    tbl = ax_table.table(
        cellText=table_data,
        cellLoc="center",
        loc="center",
        colWidths=[0.32, 0.22, 0.22, 0.24],
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    for (r, c), cell in tbl.get_celld().items():
        cell.set_edgecolor("#2c3e50")
        if r == 0:
            cell.set_facecolor("#2c3e50")
            cell.set_text_props(color="#f39c12", fontweight="bold")
        else:
            cell.set_facecolor("#1e272e" if r % 2 == 0 else "#252e38")
            cell.set_text_props(color=c_text)
        cell.set_height(0.10)

    plt.tight_layout()
    plt.savefig(output_png_path, dpi=200, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved match intelligence dashboard artifact to %s", output_png_path)


# ==============================================================================
# MAIN BENCHMARK RUNNER
# ==============================================================================

def run_exp25_benchmark() -> None:
    """Executes the full EXP-25 benchmark across DEV and HOLDOUT sequences."""
    start_total_time = time.perf_counter()
    logger.info("=" * 80)
    logger.info("STARTING CHAPTER 7 EXP-25: TACTICAL EVENT FUSION BENCHMARK")
    logger.info("=" * 80)

    calib_cache_path = Path("/media/adriano/Windows/runs/tactics/calib_cache.pkl")
    cached_adapter = RobustCachedCalibAdapter(calib_cache_path)

    base_seq_dir = Path("/media/adriano/Windows/datasets/SoccerNetTracking2023/train")
    output_dir = PROJECT_ROOT / "docs" / "experiments" / "exp25_outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    seq_results: Dict[str, Any] = {}
    all_events: List[TacticalEvidenceEvent] = []
    all_edges: List[Dict[str, Any]] = []
    all_team_summaries: Dict[str, Any] = {}

    saved_frames_for_vis: Dict[str, Any] = {}

    for seq_name in ALL_SEQUENCES:
        seq_path = base_seq_dir / seq_name
        raw_dets_path = RAW_DETS_MAP.get(seq_name)
        if not seq_path.exists() or not raw_dets_path or not raw_dets_path.exists():
            logger.warning("Skipping %s: missing sequence dir or raw detections", seq_name)
            continue

        fusion_engine, stats, saved_frames, team_summaries = run_sequence_fusion(
            seq_name=seq_name,
            seq_dir=seq_path,
            raw_dets_path=raw_dets_path,
            cached_adapter=cached_adapter,
            num_frames=NUM_FRAMES_PER_SEQ,
        )

        timeline = fusion_engine.timeline
        graph = fusion_engine.graph

        # Store sequence events
        all_events.extend(timeline.events)
        for e in graph.edges:
            all_edges.append(e.to_dict())

        all_team_summaries[seq_name] = {k: v.to_dict() for k, v in team_summaries.items()}
        seq_results[seq_name] = stats

        if seq_name == "SNMOT-068":
            saved_frames_for_vis = saved_frames

    # Serialize modular outputs (Phase 24)
    # 1. match_timeline.jsonl
    timeline_path = output_dir / "match_timeline.jsonl"
    with open(timeline_path, "w", encoding="utf-8") as f:
        for e in all_events:
            f.write(json.dumps(e.to_dict()) + "\n")

    # 2. tactical_events.json
    events_path = output_dir / "tactical_events.json"
    with open(events_path, "w", encoding="utf-8") as f:
        json.dump([e.to_dict() for e in all_events], f, indent=2)

    # 3. team_summary.json
    summary_path = output_dir / "team_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(all_team_summaries, f, indent=2)

    # 4. event_graph.json
    graph_path = output_dir / "event_graph.json"
    with open(graph_path, "w", encoding="utf-8") as f:
        json.dump({
            "node_count": len(all_events),
            "edge_count": len(all_edges),
            "edges": all_edges,
        }, f, indent=2)

    # Generate visual artifact for SNMOT-068
    dashboard_png_path = PROJECT_ROOT / "docs" / "experiments" / "SNMOT-068_match_intelligence_dashboard.png"
    artifact_png_path = Path("/home/adriano/.gemini/antigravity/brain/ae1f4037-bdfb-4ac1-8758-a8f41039e8fd/SNMOT-068_match_intelligence_dashboard.png")

    if "SNMOT-068" in seq_results:
        # Reconstruct SNMOT-068 specific timeline and summaries
        sn068_events = [e for e in all_events if e.sequence_id == "SNMOT-068"]
        sn068_timeline = MatchTacticalTimeline("SNMOT-068")
        sn068_timeline.add_events(sn068_events)
        sn068_graph = EventRelationGraph()
        for e in sn068_events:
            sn068_graph.add_event(e)

        # Build dummy TeamTacticalAggregate if needed
        t0_d = all_team_summaries["SNMOT-068"]["TEAM_0"]
        t1_d = all_team_summaries["SNMOT-068"]["TEAM_1"]
        rel0 = TeamReliabilityBand(**t0_d["reliability"])
        rel1 = TeamReliabilityBand(**t1_d["reliability"])
        agg0 = TeamTacticalAggregate(**{**t0_d, "reliability": rel0})
        agg1 = TeamTacticalAggregate(**{**t1_d, "reliability": rel1})

        generate_match_intelligence_dashboard(
            seq_name="SNMOT-068",
            timeline=sn068_timeline,
            graph=sn068_graph,
            team_summaries={"TEAM_0": agg0, "TEAM_1": agg1},
            saved_frames=saved_frames_for_vis,
            output_png_path=dashboard_png_path,
        )
        # Copy to artifact dir
        if dashboard_png_path.exists():
            import shutil
            shutil.copy2(dashboard_png_path, artifact_png_path)

    # Compute Global & Split Benchmark Aggregates (Phase 27)
    family_counter = Counter(e.event_family.value for e in all_events)
    level_counter = Counter(e.semantic_level.value for e in all_events)
    quality_counter = Counter(e.quality_level.value for e in all_events)
    conflict_count = sum(1 for e in all_events if e.conflict_flag)

    edge_rel_counter = Counter(e["relation"] for e in all_edges)

    # Confidence by semantic level
    conf_by_level: Dict[str, List[float]] = defaultdict(list)
    for e in all_events:
        conf_by_level[e.semantic_level.value].append(e.confidence)

    # Confidence ceilings audit: check if any LEVEL 3 event exceeded 0.85
    level3_confs = conf_by_level.get(SemanticLevel.LEVEL_3_TACTICAL_CANDIDATE.value, [])
    max_level3_conf = float(np.max(level3_confs)) if level3_confs else 0.0
    level3_ceiling_respected = bool(max_level3_conf <= 0.85 + 1e-5)

    # Runtime statistics
    all_latencies = [s["latency_ms"]["mean"] for s in seq_results.values()]
    mean_latency = float(np.mean(all_latencies)) if all_latencies else 0.0
    p95_latency = float(np.percentile([s["latency_ms"]["p95"] for s in seq_results.values()], 95)) if seq_results else 0.0

    benchmark_summary = {
        "experiment": "EXP-25",
        "description": "Tactical Event Fusion, Confidence Propagation & Evidence Cards Benchmark",
        "status": "COMPLETED",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "hardware": {
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "dataset": {
            "split_dev": FUSION_DEV,
            "split_holdout": FUSION_HOLDOUT,
            "total_sequences": len(seq_results),
            "frames_per_sequence": NUM_FRAMES_PER_SEQ,
            "total_frames_evaluated": len(seq_results) * NUM_FRAMES_PER_SEQ,
        },
        "event_fusion_totals": {
            "total_events_emitted": len(all_events),
            "event_family_distribution": dict(family_counter),
            "semantic_level_distribution": dict(level_counter),
            "quality_level_distribution": dict(quality_counter),
            "contradiction_rate": {
                "conflicts_detected": conflict_count,
                "conflict_pct": round(100.0 * conflict_count / max(1, len(all_events)), 2),
            },
        },
        "event_relation_graph": {
            "total_nodes": len(all_events),
            "total_edges": len(all_edges),
            "edges_per_node": round(len(all_edges) / max(1, len(all_events)), 3),
            "relation_distribution": dict(edge_rel_counter),
        },
        "confidence_propagation_audit": {
            "mean_confidence_by_level": {k: round(float(np.mean(v)), 3) for k, v in conf_by_level.items()},
            "max_confidence_by_level": {k: round(float(np.max(v)), 3) for k, v in conf_by_level.items()},
            "level3_ceiling_threshold": 0.85,
            "level3_max_observed_confidence": round(max_level3_conf, 3),
            "level3_ceiling_respected": level3_ceiling_respected,
        },
        "runtime_performance": {
            "target_budget_ms_frame": 1.0,
            "mean_fusion_latency_ms": round(mean_latency, 4),
            "p95_fusion_latency_ms": round(p95_latency, 4),
            "target_budget_met": bool(mean_latency < 1.0),
        },
        "per_sequence_summary": seq_results,
    }

    master_json_path = PROJECT_ROOT / "docs" / "experiments" / "exp25_tactical_event_fusion.json"
    with open(master_json_path, "w", encoding="utf-8") as f:
        json.dump(benchmark_summary, f, indent=2)
    logger.info("Saved master benchmark JSON to %s", master_json_path)

    total_duration = time.perf_counter() - start_total_time
    logger.info("=" * 80)
    logger.info("EXP-25 BENCHMARK COMPLETE IN %.2f seconds", total_duration)
    logger.info("Total Events: %d | Graph Edges: %d", len(all_events), len(all_edges))
    logger.info("Mean Latency: %.4f ms/frame (Budget: <1.0 ms/frame: %s)", mean_latency, mean_latency < 1.0)
    logger.info("Level 3 Ceiling Respected: %s (Max Level 3 Conf: %.3f)", level3_ceiling_respected, max_level3_conf)
    logger.info("=" * 80)


if __name__ == "__main__":
    run_exp25_benchmark()
