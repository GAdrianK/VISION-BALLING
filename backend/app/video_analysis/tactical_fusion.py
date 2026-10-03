"""Tactical Event Fusion, Confidence Propagation & Evidence Cards Engine (EXP-25 / Chapter 7).

Integrates all validated Chapter 7 tactical intelligence signals:
- EXP-15 Metric Player & Ball Trajectories
- EXP-16 Tactical Geometry & Convex Hulls
- EXP-17 Attacking Direction & Oriented Lines
- EXP-19 Ball Transfer Events (quality-gated)
- EXP-20 Defensive Block Height & Compactness
- EXP-21 Dynamic Formation Line Structures (structural primary; nominal hypothesis restricted)
- EXP-22 Possession V2 & Carrier Attribution
- EXP-23 Continuous Defensive Pressure Primitives
- EXP-24 Continuous Tactical Transitions & Post-Loss Candidates

Guiding Principles:
1. Unified Tactical Event Schema: All tactical phenomena share one standardized evidence structure.
2. Three Semantic Levels:
   - LEVEL 1: PHYSICAL_FACT (metric distances, speeds, direct counts)
   - LEVEL 2: STRUCTURAL_INFERENCE (block heights, compact episodes, progression)
   - LEVEL 3: TACTICAL_CANDIDATE (counterpress candidate, defensive recovery) — never claimed as absolute fact.
3. Strict Confidence Ceilings: Downstream events cannot exceed the confidence of upstream dependencies.
4. Separate Quality Tiers: HIGH, MEDIUM, LOW, INVALID reflecting tracking, visibility, and calibration integrity.
5. Continuous Episode Segmentation: Causal hysteresis prevents frame-by-frame event flicker.
6. Causal & Evidential Graph: Explicit relationships (CAUSES, FOLLOWS, OVERLAPS, SUPPORTS).
7. Traceable Deterministic Summaries: Templated evidence strings with ZERO free-form LLM hallucination.
8. Reliability Bands: Every team aggregate exposes coverage %, valid frame count, mean/P10 confidence.
9. Immutability: Zero modifications to upstream algorithms (EXP-15 to EXP-24 are LOCKED).
"""

from __future__ import annotations

import json
import logging
import math
from collections import Counter, defaultdict, deque
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

import numpy as np

logger = logging.getLogger("TACTICAL_FUSION")


# ==============================================================================
# ENUMS & TAXONOMY
# ==============================================================================

class SemanticLevel(str, Enum):
    """Semantic tier of tactical assertions."""
    LEVEL_1_PHYSICAL_FACT = "LEVEL_1_PHYSICAL_FACT"          # Directly measured kinematic / geometric facts
    LEVEL_2_STRUCTURAL_INFERENCE = "LEVEL_2_STRUCTURAL_INFERENCE"  # Spatial shape, line structure, continuous episodes
    LEVEL_3_TACTICAL_CANDIDATE = "LEVEL_3_TACTICAL_CANDIDATE"      # Tactical interpretations / candidate behaviors


class EventFamily(str, Enum):
    """Functional family of tactical evidence events."""
    POSSESSION_CHANGE = "POSSESSION_CHANGE"
    BALL_TRANSFER = "BALL_TRANSFER"
    BLOCK_STATE = "BLOCK_STATE"
    BLOCK_HEIGHT_CHANGE = "BLOCK_HEIGHT_CHANGE"
    PRESSURE_EPISODE = "PRESSURE_EPISODE"
    POST_LOSS_ENGAGEMENT = "POST_LOSS_ENGAGEMENT"
    DEFENSIVE_RECOVERY = "DEFENSIVE_RECOVERY"
    ATTACKING_PROGRESSION = "ATTACKING_PROGRESSION"
    TEAM_COMPRESSION = "TEAM_COMPRESSION"


class QualityLevel(str, Enum):
    """Data integrity tier independent of event confidence."""
    HIGH = "HIGH"          # Calibration valid, >=8 outfield players, no tracking discontinuities
    MEDIUM = "MEDIUM"      # Calibration valid, 6-7 outfield players, minor tracking noise
    LOW = "LOW"            # Calibration marginal, <6 outfield players, or significant tracking flicker
    INVALID = "INVALID"    # Uncalibrated, <4 outfield players, or corrupted observation


class RelationType(str, Enum):
    """Directed edge relationship between tactical events in the evidence graph."""
    CAUSES = "CAUSES"        # Causal trigger (e.g. Possession loss -> Post-loss engagement)
    FOLLOWS = "FOLLOWS"      # Chronological sequence without direct mechanical causality
    OVERLAPS = "OVERLAPS"    # Concurrently active episodes for the same tactical moment
    SUPPORTS = "SUPPORTS"    # Evidentiary backing (e.g. Pressure episode supports Counterpress candidate)


# ==============================================================================
# UNIFIED TACTICAL EVENT SCHEMA (PHASE 1)
# ==============================================================================

@dataclass
class TacticalEvidenceEvent:
    """Standardized machine-readable tactical evidence card with strict provenance."""

    event_id: str
    sequence_id: str

    start_frame: int
    end_frame: int
    start_timestamp: float
    end_timestamp: float

    event_family: EventFamily
    semantic_level: SemanticLevel

    subject_team: Optional[str] = None          # Primary team associated with the event
    opponent_team: Optional[str] = None         # Defending / receiving opponent team

    confidence: float = 0.0                     # Evidential confidence bounded by upstream ceilings in [0.0, 1.0]
    quality_level: QualityLevel = QualityLevel.MEDIUM

    source_modules: List[str] = field(default_factory=list)
    supporting_metrics: Dict[str, Any] = field(default_factory=dict)

    limitations: List[str] = field(default_factory=list)
    visibility_quality: str = "UNKNOWN"
    calibration_quality: str = "UNKNOWN"

    causal: bool = True
    summary_text: Optional[str] = None
    related_event_ids: List[str] = field(default_factory=list)
    conflict_flag: bool = False
    conflict_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serializes event to clean JSON-compatible dictionary."""
        d = asdict(self)
        d["event_family"] = self.event_family.value
        d["semantic_level"] = self.semantic_level.value
        d["quality_level"] = self.quality_level.value
        return d


# ==============================================================================
# EVENT GRAPH (PHASE 9)
# ==============================================================================

@dataclass
class EventEdge:
    """Directed relation edge between two tactical evidence cards."""
    source_id: str
    target_id: str
    relation: RelationType
    weight: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "relation": self.relation.value,
            "weight": self.weight,
        }


@dataclass
class EventRelationGraph:
    """Causal and evidential graph linking tactical evidence cards."""

    nodes: Dict[str, TacticalEvidenceEvent] = field(default_factory=dict)
    edges: List[EventEdge] = field(default_factory=list)

    def add_event(self, event: TacticalEvidenceEvent) -> None:
        """Registers a node in the graph."""
        self.nodes[event.event_id] = event

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        relation: RelationType,
        weight: float = 1.0,
    ) -> None:
        """Creates a directed relationship between two events."""
        if source_id in self.nodes and target_id in self.nodes:
            if any(e.source_id == source_id and e.target_id == target_id and e.relation == relation for e in self.edges):
                return
            edge = EventEdge(source_id, target_id, relation, weight)
            self.edges.append(edge)
            if target_id not in self.nodes[source_id].related_event_ids:
                self.nodes[source_id].related_event_ids.append(target_id)
            if source_id not in self.nodes[target_id].related_event_ids:
                self.nodes[target_id].related_event_ids.append(source_id)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "edges": [e.to_dict() for e in self.edges],
        }


# ==============================================================================
# CONFIDENCE PROPAGATION & CEILINGS (PHASE 4, 5, 6)
# ==============================================================================

class ConfidencePropagator:
    """Calculates evidential confidence with strict dependency ceilings and quality grading."""

    # Maximum confidence allowed for LEVEL 3 candidate interpretations
    LEVEL_3_CEILING: float = 0.85

    @classmethod
    def compute_confidence(
        cls,
        base_score: float,
        upstream_confidences: Sequence[float],
        semantic_level: SemanticLevel,
        calibration_valid: bool = True,
        visible_outfield: int = 10,
        has_conflict: bool = False,
        tracking_stable: bool = True,
    ) -> float:
        """Computes propagated confidence respecting dependency ceilings and quality discounts.

        Formula:
          c_inter = base_score * penalty_calib * penalty_vis * penalty_conflict * penalty_track
          c_ceiling = min(upstream_confidences) if upstream_confidences else 1.0
          if semantic_level == LEVEL_3:
              c_ceiling = min(c_ceiling, 0.85)
          c_final = min(c_ceiling, c_inter)
        """
        # Multiplicative quality penalties
        p_calib = 1.0 if calibration_valid else 0.40
        if visible_outfield >= 8:
            p_vis = 1.0
        elif visible_outfield >= 6:
            p_vis = 0.85
        elif visible_outfield >= 4:
            p_vis = 0.65
        else:
            p_vis = 0.30

        p_conflict = 0.60 if has_conflict else 1.0
        p_track = 1.0 if tracking_stable else 0.80

        c_inter = float(np.clip(base_score * p_calib * p_vis * p_conflict * p_track, 0.0, 1.0))

        # Enforce upstream dependency ceiling
        if upstream_confidences:
            upstream_min = float(min(upstream_confidences))
            c_ceiling = upstream_min
        else:
            c_ceiling = 1.0

        # Enforce Level 3 tactical candidate ceiling
        if semantic_level == SemanticLevel.LEVEL_3_TACTICAL_CANDIDATE:
            c_ceiling = min(c_ceiling, cls.LEVEL_3_CEILING)

        return float(np.clip(min(c_ceiling, c_inter), 0.0, 1.0))

    @staticmethod
    def determine_quality(
        calibration_quality: str,
        visible_outfield: int,
        has_conflict: bool = False,
        tracking_stable: bool = True,
        carrier_confidence: float = 1.0,
    ) -> QualityLevel:
        """Determines the data quality tier based on sensory constraints."""
        if calibration_quality.upper() in ("INVALID", "UNAVAILABLE") or visible_outfield < 4:
            return QualityLevel.INVALID
        if calibration_quality.upper() != "VALID" or visible_outfield < 6 or has_conflict or carrier_confidence < 0.35:
            return QualityLevel.LOW
        if visible_outfield in (6, 7) or not tracking_stable or carrier_confidence < 0.60:
            return QualityLevel.MEDIUM
        return QualityLevel.HIGH


# ==============================================================================
# DETERMINISTIC HUMAN-READABLE EVIDENCE SUMMARY (PHASE 23)
# ==============================================================================

class DeterministicSummaryFormatter:
    """Generates fully deterministic, template-based factual evidence summaries.

    Strictly prohibits LLM free-form generation to maintain auditability and avoid hallucinations.
    """

    @staticmethod
    def format_summary(event: TacticalEvidenceEvent) -> str:
        f = event.event_family
        m = event.supporting_metrics
        t_start = event.start_timestamp
        t_end = event.end_timestamp
        subj = event.subject_team or "UNKNOWN"
        opp = event.opponent_team or "UNKNOWN"
        conf = event.confidence
        qual = event.quality_level.value

        if f == EventFamily.POSSESSION_CHANGE:
            return (
                f"{subj} lost possession to {opp} at {t_start:.2f}s (frame {event.start_frame}). "
                f"Possession confidence: {conf:.2f} [{qual}]."
            )
        elif f == EventFamily.POST_LOSS_ENGAGEMENT:
            d_pre = m.get("nearest_defender_pre", 0.0)
            d_post = m.get("nearest_defender_post", 0.0)
            p_pre = m.get("pressure_pre_mean", 0.0)
            p_post = m.get("pressure_post_mean", 0.0)
            cp_score = m.get("counterpress_score", 0.0)
            dt = t_end - t_start
            return (
                f"{subj} engaged in post-loss pressing against {opp} ({t_start:.2f}–{t_end:.2f}s, Δt={dt:.2f}s). "
                f"Nearest defender closed from {d_pre:.1f}m to {d_post:.1f}m; "
                f"PressureIndex changed from {p_pre:.2f} to {p_post:.2f}. "
                f"CounterpressScore: {cp_score:.2f} [Confidence: {conf:.2f}]."
            )
        elif f == EventFamily.DEFENSIVE_RECOVERY:
            line_vel = m.get("defensive_line_velocity", 0.0)
            cent_delta = m.get("centroid_ball_distance_delta", 0.0)
            rec_score = m.get("recovery_score", 0.0)
            return (
                f"{subj} initiated defensive recovery after possession loss ({t_start:.2f}–{t_end:.2f}s). "
                f"Backline retreated at {line_vel:.1f}m/s; centroid-ball distance shifted by {cent_delta:+.1f}m. "
                f"RecoveryScore: {rec_score:.2f} [Confidence: {conf:.2f}]."
            )
        elif f == EventFamily.PRESSURE_EPISODE:
            peak = m.get("peak_pressure_index", 0.0)
            mean = m.get("mean_pressure_index", 0.0)
            d_min = m.get("nearest_defender_min_m", 0.0)
            dur = t_end - t_start
            return (
                f"{subj} applied continuous defensive pressure on {opp} ({t_start:.2f}–{t_end:.2f}s, dur: {dur:.2f}s). "
                f"Mean PressureIndex: {mean:.2f} (peak: {peak:.2f}), min defender proximity: {d_min:.1f}m."
            )
        elif f == EventFamily.BLOCK_STATE:
            cat = m.get("block_category", "UNKNOWN")
            h = m.get("mean_defensive_line_height_m", 0.0)
            depth = m.get("mean_depth_m", 0.0)
            width = m.get("mean_width_m", 0.0)
            dur = t_end - t_start
            return (
                f"{subj} structured in a {cat} block ({t_start:.2f}–{t_end:.2f}s, dur: {dur:.2f}s). "
                f"Mean defensive line height: {h:.1f}m from own goal, depth: {depth:.1f}m, width: {width:.1f}m."
            )
        elif f == EventFamily.BLOCK_HEIGHT_CHANGE:
            from_cat = m.get("from_category", "UNKNOWN")
            to_cat = m.get("to_category", "UNKNOWN")
            dh = m.get("height_delta_m", 0.0)
            return (
                f"{subj} shifted defensive block height from {from_cat} to {to_cat} at {t_start:.2f}s "
                f"(line displacement: {dh:+.1f}m, confidence: {conf:.2f})."
            )
        elif f == EventFamily.BALL_TRANSFER:
            dist = m.get("pass_distance_m", 0.0)
            fwd = m.get("forward_displacement_m", 0.0)
            return (
                f"{subj} ball transfer completed ({t_start:.2f}–{t_end:.2f}s). "
                f"Distance: {dist:.1f}m, forward displacement: {fwd:+.1f}m [Confidence: {conf:.2f}]."
            )
        elif f == EventFamily.ATTACKING_PROGRESSION:
            prog = m.get("forward_progression_m", 0.0)
            dur = t_end - t_start
            return (
                f"{subj} achieved forward ball progression of {prog:.1f}m over {dur:.2f}s "
                f"({t_start:.2f}–{t_end:.2f}s, confidence: {conf:.2f})."
            )
        elif f == EventFamily.TEAM_COMPRESSION:
            d_depth = m.get("delta_depth_mps", 0.0)
            d_line = m.get("delta_line_height_mps", 0.0)
            return (
                f"{subj} executed spatial block compression ({t_start:.2f}–{t_end:.2f}s). "
                f"Depth rate: {d_depth:.1f}m/s, line push rate: {d_line:.1f}m/s."
            )
        else:
            return f"Event {f.value} for {subj} at {t_start:.2f}s [Confidence: {conf:.2f}]."


# ==============================================================================
# CONTINUOUS EPISODE SEGMENTATION WITH HYSTERESIS (PHASE 11, 12)
# ==============================================================================

@dataclass
class ContinuousEpisodeConfig:
    """Hysteresis and duration thresholds for continuous signal segmentation."""

    # Pressure episode thresholds (EXP-23)
    pressure_enter_threshold: float = 0.45
    pressure_exit_threshold: float = 0.25
    pressure_min_duration_frames: int = 8      # 0.32s at 25 fps

    # Defensive block height thresholds (EXP-20)
    block_min_duration_frames: int = 12        # 0.48s at 25 fps
    block_height_buffer_m: float = 2.0         # Hysteresis buffer around 35.0m and 52.5m boundaries

    # Possession episode thresholds (EXP-22)
    possession_min_duration_frames: int = 5    # 0.20s at 25 fps

    # Progression episode thresholds
    progression_min_distance_m: float = 6.0
    progression_max_window_frames: int = 50    # 2.0s at 25 fps

    fps: float = 25.0


class ContinuousEpisodeSegmenter:
    """Causal hysteresis segmenter converting frame-level signals into discrete episodes."""

    def __init__(self, config: Optional[ContinuousEpisodeConfig] = None):
        self.config = config or ContinuousEpisodeConfig()

        # Active state tracking for pressure episodes: team -> state
        self._active_pressure: Dict[str, Optional[Dict[str, Any]]] = {"TEAM_0": None, "TEAM_1": None}

        # Active state tracking for block episodes: team -> state
        self._active_block: Dict[str, Optional[Dict[str, Any]]] = {"TEAM_0": None, "TEAM_1": None}

        # Active state tracking for possession: current_team, start_frame, frames
        self._active_possession: Optional[Dict[str, Any]] = None

        # Active tracking for spatial compression: team -> list of frames
        self._compression_frames: Dict[str, List[int]] = {"TEAM_0": [], "TEAM_1": []}

    def process_pressure_frame(
        self,
        frame_idx: int,
        timestamp: float,
        defending_team: str,
        target_team: str,
        pressure_index: float,
        nearest_dist_m: Optional[float],
        closing_speed_mps: Optional[float],
        visible_outfield: int,
        calib_valid: bool,
    ) -> List[TacticalEvidenceEvent]:
        """Segments pressure time-series into continuous PressureEpisode events via hysteresis."""
        emitted: List[TacticalEvidenceEvent] = []
        if defending_team not in ("TEAM_0", "TEAM_1"):
            return emitted

        state = self._active_pressure[defending_team]

        if state is None:
            # Check enter condition
            if pressure_index >= self.config.pressure_enter_threshold:
                self._active_pressure[defending_team] = {
                    "start_frame": frame_idx,
                    "start_timestamp": timestamp,
                    "target_team": target_team,
                    "pressure_indices": [pressure_index],
                    "nearest_dists": [nearest_dist_m] if nearest_dist_m is not None else [],
                    "closing_speeds": [closing_speed_mps] if closing_speed_mps is not None else [],
                    "visible_counts": [visible_outfield],
                    "calib_valids": [calib_valid],
                }
        else:
            # Active episode: accumulate
            state["pressure_indices"].append(pressure_index)
            if nearest_dist_m is not None:
                state["nearest_dists"].append(nearest_dist_m)
            if closing_speed_mps is not None:
                state["closing_speeds"].append(closing_speed_mps)
            state["visible_counts"].append(visible_outfield)
            state["calib_valids"].append(calib_valid)

            # Check exit condition
            if pressure_index < self.config.pressure_exit_threshold:
                duration_frames = frame_idx - state["start_frame"] + 1
                if duration_frames >= self.config.pressure_min_duration_frames:
                    mean_p = float(np.mean(state["pressure_indices"]))
                    peak_p = float(np.max(state["pressure_indices"]))
                    min_d = float(np.min(state["nearest_dists"])) if state["nearest_dists"] else 0.0
                    max_close = float(np.max(state["closing_speeds"])) if state["closing_speeds"] else 0.0
                    mean_vis = int(np.mean(state["visible_counts"]))
                    all_calib = bool(all(state["calib_valids"]))

                    qual = ConfidencePropagator.determine_quality(
                        "VALID" if all_calib else "INVALID",
                        mean_vis,
                    )
                    conf = ConfidencePropagator.compute_confidence(
                        base_score=mean_p,
                        upstream_confidences=[0.90 if all_calib else 0.40],
                        semantic_level=SemanticLevel.LEVEL_1_PHYSICAL_FACT,
                        calibration_valid=all_calib,
                        visible_outfield=mean_vis,
                    )

                    evt = TacticalEvidenceEvent(
                        event_id=f"press_{state['start_frame']}_{frame_idx}_{defending_team}",
                        sequence_id="CURRENT",
                        start_frame=state["start_frame"],
                        end_frame=frame_idx,
                        start_timestamp=state["start_timestamp"],
                        end_timestamp=timestamp,
                        event_family=EventFamily.PRESSURE_EPISODE,
                        semantic_level=SemanticLevel.LEVEL_1_PHYSICAL_FACT,
                        subject_team=defending_team,
                        opponent_team=state["target_team"],
                        confidence=conf,
                        quality_level=qual,
                        source_modules=["EXP-23 defensive_pressure"],
                        supporting_metrics={
                            "mean_pressure_index": round(mean_p, 3),
                            "peak_pressure_index": round(peak_p, 3),
                            "duration_frames": duration_frames,
                            "nearest_defender_min_m": round(min_d, 2),
                            "max_closing_speed_mps": round(max_close, 2),
                        },
                        visibility_quality="HIGH" if mean_vis >= 8 else ("MEDIUM" if mean_vis >= 6 else "LOW"),
                        calibration_quality="VALID" if all_calib else "INVALID",
                    )
                    evt.summary_text = DeterministicSummaryFormatter.format_summary(evt)
                    emitted.append(evt)

                self._active_pressure[defending_team] = None

        return emitted

    def process_block_frame(
        self,
        frame_idx: int,
        timestamp: float,
        team_id: str,
        category: str,
        line_height_m: Optional[float],
        centroid_height_m: Optional[float],
        depth_m: Optional[float],
        width_m: Optional[float],
        visible_outfield: int,
        calib_valid: bool,
    ) -> List[TacticalEvidenceEvent]:
        """Segments defensive block geometry into continuous BlockEpisode intervals."""
        emitted: List[TacticalEvidenceEvent] = []
        if team_id not in ("TEAM_0", "TEAM_1"):
            return emitted

        state = self._active_block[team_id]

        if line_height_m is None or category in ("UNKNOWN", "AMBIGUOUS"):
            # Close active block if visibility lost
            if state is not None:
                duration_frames = frame_idx - state["start_frame"]
                if duration_frames >= self.config.block_min_duration_frames:
                    evt = self._create_block_event(state, frame_idx - 1, timestamp)
                    if evt:
                        emitted.append(evt)
                self._active_block[team_id] = None
            return emitted

        if state is None:
            self._active_block[team_id] = {
                "start_frame": frame_idx,
                "start_timestamp": timestamp,
                "category": category,
                "heights": [line_height_m],
                "centroid_heights": [centroid_height_m] if centroid_height_m is not None else [],
                "depths": [depth_m] if depth_m is not None else [],
                "widths": [width_m] if width_m is not None else [],
                "visibles": [visible_outfield],
                "calibs": [calib_valid],
            }
        else:
            # Check if category changed with hysteresis buffer
            prev_cat = state["category"]
            cat_changed = False
            if prev_cat != category:
                # Require crossing the boundary + buffer
                if prev_cat == "LOW_BLOCK" and line_height_m > (35.0 + self.config.block_height_buffer_m):
                    cat_changed = True
                elif prev_cat == "MID_BLOCK":
                    if line_height_m < (35.0 - self.config.block_height_buffer_m):
                        cat_changed = True
                    elif line_height_m > (52.5 + self.config.block_height_buffer_m):
                        cat_changed = True
                elif prev_cat == "HIGH_BLOCK" and line_height_m < (52.5 - self.config.block_height_buffer_m):
                    cat_changed = True

            if cat_changed:
                duration_frames = frame_idx - state["start_frame"]
                if duration_frames >= self.config.block_min_duration_frames:
                    evt = self._create_block_event(state, frame_idx - 1, timestamp)
                    if evt:
                        emitted.append(evt)
                # Re-initialize new category
                self._active_block[team_id] = {
                    "start_frame": frame_idx,
                    "start_timestamp": timestamp,
                    "category": category,
                    "heights": [line_height_m],
                    "centroid_heights": [centroid_height_m] if centroid_height_m is not None else [],
                    "depths": [depth_m] if depth_m is not None else [],
                    "widths": [width_m] if width_m is not None else [],
                    "visibles": [visible_outfield],
                    "calibs": [calib_valid],
                }
            else:
                state["heights"].append(line_height_m)
                if centroid_height_m is not None:
                    state["centroid_heights"].append(centroid_height_m)
                if depth_m is not None:
                    state["depths"].append(depth_m)
                if width_m is not None:
                    state["widths"].append(width_m)
                state["visibles"].append(visible_outfield)
                state["calibs"].append(calib_valid)

        return emitted

    def _create_block_event(
        self,
        state: Dict[str, Any],
        end_frame: int,
        end_timestamp: float,
    ) -> Optional[TacticalEvidenceEvent]:
        dur = end_frame - state["start_frame"] + 1
        mean_h = float(np.mean(state["heights"]))
        mean_ch = float(np.mean(state["centroid_heights"])) if state["centroid_heights"] else mean_h
        mean_depth = float(np.mean(state["depths"])) if state["depths"] else 0.0
        mean_width = float(np.mean(state["widths"])) if state["widths"] else 0.0
        mean_vis = int(np.mean(state["visibles"]))
        all_calib = bool(all(state["calibs"]))

        qual = ConfidencePropagator.determine_quality("VALID" if all_calib else "INVALID", mean_vis)
        conf = ConfidencePropagator.compute_confidence(
            base_score=0.88,
            upstream_confidences=[0.90 if all_calib else 0.40],
            semantic_level=SemanticLevel.LEVEL_2_STRUCTURAL_INFERENCE,
            calibration_valid=all_calib,
            visible_outfield=mean_vis,
        )

        evt = TacticalEvidenceEvent(
            event_id=f"block_{state['start_frame']}_{end_frame}_{state['category']}",
            sequence_id="CURRENT",
            start_frame=state["start_frame"],
            end_frame=end_frame,
            start_timestamp=state["start_timestamp"],
            end_timestamp=end_timestamp,
            event_family=EventFamily.BLOCK_STATE,
            semantic_level=SemanticLevel.LEVEL_2_STRUCTURAL_INFERENCE,
            subject_team="TEAM_0" if "TEAM_0" in str(state) else "TEAM_1", # Context assigned by caller
            confidence=conf,
            quality_level=qual,
            source_modules=["EXP-20 defensive_block"],
            supporting_metrics={
                "block_category": state["category"],
                "mean_defensive_line_height_m": round(mean_h, 2),
                "mean_centroid_height_m": round(mean_ch, 2),
                "mean_depth_m": round(mean_depth, 2),
                "mean_width_m": round(mean_width, 2),
                "duration_frames": dur,
            },
            visibility_quality="HIGH" if mean_vis >= 8 else ("MEDIUM" if mean_vis >= 6 else "LOW"),
            calibration_quality="VALID" if all_calib else "INVALID",
        )
        evt.summary_text = DeterministicSummaryFormatter.format_summary(evt)
        return evt

    def finalize(self, last_frame: int, last_timestamp: float) -> List[TacticalEvidenceEvent]:
        """Flushes any open episodes at sequence boundary."""
        remaining: List[TacticalEvidenceEvent] = []
        for team_id in ("TEAM_0", "TEAM_1"):
            p_state = self._active_pressure[team_id]
            if p_state is not None:
                dur = last_frame - p_state["start_frame"] + 1
                if dur >= self.config.pressure_min_duration_frames:
                    mean_p = float(np.mean(p_state["pressure_indices"]))
                    peak_p = float(np.max(p_state["pressure_indices"]))
                    min_d = float(np.min(p_state["nearest_dists"])) if p_state["nearest_dists"] else 0.0
                    max_close = float(np.max(p_state["closing_speeds"])) if p_state["closing_speeds"] else 0.0
                    mean_vis = int(np.mean(p_state["visible_counts"]))
                    all_calib = bool(all(p_state["calib_valids"]))
                    qual = ConfidencePropagator.determine_quality("VALID" if all_calib else "INVALID", mean_vis)
                    conf = ConfidencePropagator.compute_confidence(
                        base_score=mean_p,
                        upstream_confidences=[0.90 if all_calib else 0.40],
                        semantic_level=SemanticLevel.LEVEL_1_PHYSICAL_FACT,
                        calibration_valid=all_calib,
                        visible_outfield=mean_vis,
                    )
                    evt = TacticalEvidenceEvent(
                        event_id=f"press_{p_state['start_frame']}_{last_frame}_{team_id}",
                        sequence_id="CURRENT",
                        start_frame=p_state["start_frame"],
                        end_frame=last_frame,
                        start_timestamp=p_state["start_timestamp"],
                        end_timestamp=last_timestamp,
                        event_family=EventFamily.PRESSURE_EPISODE,
                        semantic_level=SemanticLevel.LEVEL_1_PHYSICAL_FACT,
                        subject_team=team_id,
                        opponent_team=p_state["target_team"],
                        confidence=conf,
                        quality_level=qual,
                        source_modules=["EXP-23 defensive_pressure"],
                        supporting_metrics={
                            "mean_pressure_index": round(mean_p, 3),
                            "peak_pressure_index": round(peak_p, 3),
                            "duration_frames": dur,
                            "nearest_defender_min_m": round(min_d, 2),
                            "max_closing_speed_mps": round(max_close, 2),
                        },
                        visibility_quality="HIGH" if mean_vis >= 8 else ("MEDIUM" if mean_vis >= 6 else "LOW"),
                        calibration_quality="VALID" if all_calib else "INVALID",
                    )
                    evt.summary_text = DeterministicSummaryFormatter.format_summary(evt)
                    remaining.append(evt)
                self._active_pressure[team_id] = None

            b_state = self._active_block[team_id]
            if b_state is not None:
                dur = last_frame - b_state["start_frame"] + 1
                if dur >= self.config.block_min_duration_frames:
                    evt = self._create_block_event(b_state, last_frame, last_timestamp)
                    if evt:
                        evt.subject_team = team_id
                        evt.summary_text = DeterministicSummaryFormatter.format_summary(evt)
                        remaining.append(evt)
                self._active_block[team_id] = None

        return remaining


# ==============================================================================
# EVENT DEDUPLICATION & CONTRADICTION HANDLING (PHASE 8, 21)
# ==============================================================================

class EventDeduplicator:
    """Consolidates overlapping representations and links evidential edges."""

    @staticmethod
    def link_and_deduplicate(
        events: List[TacticalEvidenceEvent],
        graph: EventRelationGraph,
        temporal_window_frames: int = 25,
    ) -> List[TacticalEvidenceEvent]:
        """Groups temporally proximate and causally related events, attaching graph edges."""
        # Index events by family and frame
        events_by_id = {e.event_id: e for e in events}
        for e in events:
            graph.add_event(e)

        # Detect causal chains: POSSESSION_CHANGE -> POST_LOSS_ENGAGEMENT / DEFENSIVE_RECOVERY
        turnovers = [e for e in events if e.event_family == EventFamily.POSSESSION_CHANGE]
        engagements = [
            e for e in events
            if e.event_family in (EventFamily.POST_LOSS_ENGAGEMENT, EventFamily.DEFENSIVE_RECOVERY)
        ]
        pressures = [e for e in events if e.event_family == EventFamily.PRESSURE_EPISODE]

        for turn in turnovers:
            for eng in engagements:
                if abs(eng.start_frame - turn.start_frame) <= temporal_window_frames:
                    if eng.subject_team == turn.subject_team or eng.opponent_team == turn.opponent_team:
                        graph.add_edge(turn.event_id, eng.event_id, RelationType.CAUSES)

        # Link supporting pressure episodes to post-loss engagements
        for eng in engagements:
            for press in pressures:
                # If pressure episode overlaps engagement window for the same team
                if (press.start_frame <= eng.end_frame and press.end_frame >= eng.start_frame):
                    if press.subject_team == eng.subject_team:
                        graph.add_edge(press.event_id, eng.event_id, RelationType.SUPPORTS)

        return events


class ContradictionDetector:
    """Detects multi-module state inconsistencies and flags tactical events."""

    @staticmethod
    def audit_event_consistency(
        event: TacticalEvidenceEvent,
        possession_team: Optional[str],
        pressure_target_team: Optional[str],
    ) -> TacticalEvidenceEvent:
        """Audits event for inter-module contradictions and discounts confidence if conflicted."""
        # Check 1: Possession vs Pressure Target Team
        if (
            event.event_family in (EventFamily.POST_LOSS_ENGAGEMENT, EventFamily.PRESSURE_EPISODE)
            and possession_team is not None
            and pressure_target_team is not None
        ):
            if possession_team != "UNKNOWN" and pressure_target_team != "UNKNOWN":
                if possession_team != pressure_target_team:
                    event.conflict_flag = True
                    event.conflict_reason = (
                        f"Possession V2 assigns ball to {possession_team}, but defensive "
                        f"pressure target resolves to {pressure_target_team}."
                    )
                    # Apply conflict discount
                    event.confidence = float(np.clip(event.confidence * 0.60, 0.0, 1.0))
                    event.limitations.append(f"CONFLICT: {event.conflict_reason}")
                    if event.quality_level == QualityLevel.HIGH:
                        event.quality_level = QualityLevel.MEDIUM

        return event


# ==============================================================================
# MATCH TIMELINE & TEAM TACTICAL AGGREGATES (PHASE 10, 19, 20)
# ==============================================================================

class MatchTacticalTimeline:
    """Chronological ordered container of tactical evidence events."""

    def __init__(self, sequence_id: str = "UNKNOWN"):
        self.sequence_id = sequence_id
        self._events: List[TacticalEvidenceEvent] = []

    def add_event(self, event: TacticalEvidenceEvent) -> None:
        self._events.append(event)

    def add_events(self, events: Sequence[TacticalEvidenceEvent]) -> None:
        self._events.extend(events)

    def sort(self) -> None:
        """Sorts timeline chronologically by start frame and semantic level."""
        self._events.sort(key=lambda e: (e.start_frame, e.end_frame, e.semantic_level.value))

    @property
    def events(self) -> List[TacticalEvidenceEvent]:
        return self._events

    def to_jsonl(self, filepath: Union[str, Path]) -> None:
        """Exports timeline to versioned JSONL format."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for e in self._events:
                f.write(json.dumps(e.to_dict()) + "\n")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sequence_id": self.sequence_id,
            "total_events": len(self._events),
            "events": [e.to_dict() for e in self._events],
        }


@dataclass
class TeamReliabilityBand:
    """Coverage and uncertainty statistics accompanying aggregate metrics."""
    coverage_pct: float = 0.0
    valid_frames: int = 0
    total_frames: int = 0
    confidence_mean: float = 0.0
    confidence_p10: float = 0.0
    quality_distribution: Dict[str, int] = field(default_factory=lambda: {"HIGH": 0, "MEDIUM": 0, "LOW": 0, "INVALID": 0})


@dataclass
class TeamTacticalAggregate:
    """Team-level summary primitives with mandatory reliability bands (Phase 19, 20)."""

    team_id: str
    reliability: TeamReliabilityBand

    # Possession (EXP-22)
    secure_possession_duration_s: float = 0.0
    secure_possession_pct: float = 0.0
    possession_change_count: int = 0

    # Defensive Block Geometry (EXP-20)
    mean_defensive_line_height_m: Optional[float] = None
    mean_team_depth_m: Optional[float] = None
    mean_team_width_m: Optional[float] = None
    mean_hull_area_m2: Optional[float] = None

    # Defensive Pressure (EXP-23)
    mean_pressure_index: float = 0.0
    peak_pressure_index: float = 0.0
    high_quality_pressure_episode_count: int = 0

    # Transitions & Counter-press (EXP-24)
    post_loss_counterpress_mean: float = 0.0
    defensive_recovery_mean: float = 0.0

    # Progression (EXP-17, EXP-19)
    net_forward_progression_m: float = 0.0
    completed_pass_count: int = 0

    # Formation Structural Lines (EXP-21: lines primary, nominal hypothesis restricted)
    observed_line_structures: List[Dict[str, Any]] = field(default_factory=list)
    formation_hypothesis: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ==============================================================================
# TACTICAL FUSION ENGINE (PHASE 1 - 24 ORCHESTRATOR)
# ==============================================================================

class TacticalFusionEngine:
    """Unified integration engine producing evidence cards, timelines, graphs, and summaries.

    Strictly causal, zero-perception-retraining, and enforces upstream confidence ceilings.
    """

    def __init__(
        self,
        sequence_id: str = "UNKNOWN",
        fps: float = 25.0,
        config: Optional[ContinuousEpisodeConfig] = None,
    ):
        self.sequence_id = sequence_id
        self.fps = fps
        self.config = config or ContinuousEpisodeConfig(fps=fps)

        self.segmenter = ContinuousEpisodeSegmenter(self.config)
        self.graph = EventRelationGraph()
        self.timeline = MatchTacticalTimeline(sequence_id=sequence_id)

        # Frame-level accumulation for team aggregates
        self._frames_processed: int = 0
        self._possession_frames: Dict[str, int] = {"TEAM_0": 0, "TEAM_1": 0, "UNKNOWN": 0, "CONTESTED": 0}
        self._block_heights: Dict[str, List[float]] = {"TEAM_0": [], "TEAM_1": []}
        self._block_depths: Dict[str, List[float]] = {"TEAM_0": [], "TEAM_1": []}
        self._block_widths: Dict[str, List[float]] = {"TEAM_0": [], "TEAM_1": []}
        self._block_hulls: Dict[str, List[float]] = {"TEAM_0": [], "TEAM_1": []}
        self._pressure_indices: Dict[str, List[float]] = {"TEAM_0": [], "TEAM_1": []}
        self._confidences: Dict[str, List[float]] = {"TEAM_0": [], "TEAM_1": []}
        self._qualities: Dict[str, Counter] = {"TEAM_0": Counter(), "TEAM_1": Counter()}
        self._progression_totals: Dict[str, float] = {"TEAM_0": 0.0, "TEAM_1": 0.0}
        self._formation_consensuses: Dict[str, Counter] = {"TEAM_0": Counter(), "TEAM_1": Counter()}
        self._formation_lines_samples: Dict[str, List[List[int]]] = {"TEAM_0": [], "TEAM_1": []}

        # Discrete event counts
        self._possession_change_count: Dict[str, int] = {"TEAM_0": 0, "TEAM_1": 0}
        self._pass_completed_count: Dict[str, int] = {"TEAM_0": 0, "TEAM_1": 0}
        self._counterpress_scores: Dict[str, List[float]] = {"TEAM_0": [], "TEAM_1": []}
        self._recovery_scores: Dict[str, List[float]] = {"TEAM_0": [], "TEAM_1": []}

    def ingest_frame(
        self,
        frame_idx: int,
        timestamp: float,
        # EXP-20 Block states
        block_metrics_team0: Optional[Any],
        block_metrics_team1: Optional[Any],
        # EXP-22 Possession state
        possession_status: str,
        possessing_team: Optional[str],
        possession_confidence: float,
        # EXP-23 Pressure state
        pressure_state: Optional[Any],
        # EXP-21 Formation state (optional diagnostic)
        formation_state_team0: Optional[Any] = None,
        formation_state_team1: Optional[Any] = None,
        # Calibration & visibility
        calibration_valid: bool = True,
        visible_players_t0: int = 10,
        visible_players_t1: int = 10,
    ) -> List[TacticalEvidenceEvent]:
        """Ingests frame-level multi-module outputs and accumulates continuous episodes."""
        self._frames_processed += 1
        new_events: List[TacticalEvidenceEvent] = []

        # 1. Accumulate possession frame stats
        poss_key = possessing_team if possessing_team in ("TEAM_0", "TEAM_1") else possession_status
        self._possession_frames[poss_key] = self._possession_frames.get(poss_key, 0) + 1

        # 2. Block geometry accumulation & episode segmentation
        for team_id, b_metrics, vis in (
            ("TEAM_0", block_metrics_team0, visible_players_t0),
            ("TEAM_1", block_metrics_team1, visible_players_t1),
        ):
            if b_metrics is not None:
                cat = getattr(b_metrics, "category", None) or getattr(b_metrics, "block_category", "UNKNOWN")
                if isinstance(cat, Enum):
                    cat = cat.value
                h = getattr(b_metrics, "defensive_line_height_m", None)
                ch = getattr(b_metrics, "team_centroid_height_m", None)
                d = getattr(b_metrics, "oriented_depth_m", None)
                w = getattr(b_metrics, "lateral_width_m", None)
                hull = getattr(b_metrics, "hull_area_m2", None)

                if h is not None and not math.isnan(h):
                    self._block_heights[team_id].append(float(h))
                if d is not None and not math.isnan(d):
                    self._block_depths[team_id].append(float(d))
                if w is not None and not math.isnan(w):
                    self._block_widths[team_id].append(float(w))
                if hull is not None and not math.isnan(hull):
                    self._block_hulls[team_id].append(float(hull))

                q = ConfidencePropagator.determine_quality("VALID" if calibration_valid else "INVALID", vis)
                self._qualities[team_id][q.value] += 1
                c = ConfidencePropagator.compute_confidence(
                    base_score=0.85,
                    upstream_confidences=[possession_confidence],
                    semantic_level=SemanticLevel.LEVEL_2_STRUCTURAL_INFERENCE,
                    calibration_valid=calibration_valid,
                    visible_outfield=vis,
                )
                self._confidences[team_id].append(c)

                # Segment continuous block episodes
                b_evts = self.segmenter.process_block_frame(
                    frame_idx=frame_idx,
                    timestamp=timestamp,
                    team_id=team_id,
                    category=str(cat),
                    line_height_m=h,
                    centroid_height_m=ch,
                    depth_m=d,
                    width_m=w,
                    visible_outfield=vis,
                    calib_valid=calibration_valid,
                )
                for be in b_evts:
                    be.sequence_id = self.sequence_id
                    be.subject_team = team_id
                    new_events.append(be)

        # 3. Defensive Pressure accumulation & episode segmentation
        if pressure_state is not None:
            def_team = getattr(pressure_state, "defending_team", "UNKNOWN")
            p_index = getattr(pressure_state, "pressure_index", 0.0)
            target = getattr(pressure_state, "target", None)
            target_team = getattr(target, "target_team", "UNKNOWN") if target else "UNKNOWN"
            d_min = getattr(pressure_state, "nearest_defender_distance_m", None)
            v_close = getattr(pressure_state, "max_closing_speed_mps", None)

            if def_team in ("TEAM_0", "TEAM_1"):
                self._pressure_indices[def_team].append(float(p_index))
                vis_def = visible_players_t0 if def_team == "TEAM_0" else visible_players_t1

                p_evts = self.segmenter.process_pressure_frame(
                    frame_idx=frame_idx,
                    timestamp=timestamp,
                    defending_team=def_team,
                    target_team=target_team,
                    pressure_index=float(p_index),
                    nearest_dist_m=d_min,
                    closing_speed_mps=v_close,
                    visible_outfield=vis_def,
                    calib_valid=calibration_valid,
                )
                for pe in p_evts:
                    pe.sequence_id = self.sequence_id
                    # Audit contradictions
                    pe = ContradictionDetector.audit_event_consistency(pe, possessing_team, target_team)
                    new_events.append(pe)

        # 4. Formation lines inspection (EXP-21 formation policy: line structure primary)
        for team_id, f_state in (("TEAM_0", formation_state_team0), ("TEAM_1", formation_state_team1)):
            if f_state is not None:
                lines = getattr(f_state, "players_per_line", None)
                if lines and isinstance(lines, list):
                    self._formation_lines_samples[team_id].append(lines)
                label = getattr(f_state, "stable_formation_label", None) or getattr(f_state, "formation_label", None)
                vis_class = getattr(f_state, "visibility_class", None)
                vis_val = getattr(vis_class, "value", str(vis_class)) if vis_class else ""
                # Only log nominal hypothesis if evidence was FULL
                if label and label not in ("UNKNOWN", "PARTIAL") and "FULL" in vis_val:
                    self._formation_consensuses[team_id][label] += 1

        for e in new_events:
            self.timeline.add_event(e)
            self.graph.add_event(e)

        return new_events

    def ingest_possession_change_event(
        self,
        event: Any,
        calibration_valid: bool = True,
        visible_players: int = 10,
    ) -> TacticalEvidenceEvent:
        """Converts an EXP-22 confirmed possession change into a LEVEL 1 TacticalEvidenceEvent."""
        losing_team = getattr(event, "losing_team", None) or getattr(event, "from_team", "UNKNOWN")
        gaining_team = getattr(event, "gaining_team", None) or getattr(event, "to_team", "UNKNOWN")
        frame_idx = getattr(event, "frame_index", 0)
        timestamp = getattr(event, "timestamp", frame_idx / self.fps)
        conf_raw = getattr(event, "confidence", 0.70)
        if isinstance(conf_raw, str):
            conf_map = {"HIGH": 0.85, "MEDIUM": 0.65, "LOW": 0.40}
            conf_raw = conf_map.get(conf_raw.upper(), 0.50)

        if losing_team in self._possession_change_count:
            self._possession_change_count[losing_team] += 1

        qual = ConfidencePropagator.determine_quality("VALID" if calibration_valid else "INVALID", visible_players)
        final_conf = ConfidencePropagator.compute_confidence(
            base_score=float(conf_raw),
            upstream_confidences=[float(conf_raw)],
            semantic_level=SemanticLevel.LEVEL_1_PHYSICAL_FACT,
            calibration_valid=calibration_valid,
            visible_outfield=visible_players,
        )

        evt = TacticalEvidenceEvent(
            event_id=f"poss_change_{frame_idx}_{losing_team}_to_{gaining_team}",
            sequence_id=self.sequence_id,
            start_frame=frame_idx,
            end_frame=frame_idx,
            start_timestamp=timestamp,
            end_timestamp=timestamp,
            event_family=EventFamily.POSSESSION_CHANGE,
            semantic_level=SemanticLevel.LEVEL_1_PHYSICAL_FACT,
            subject_team=losing_team,
            opponent_team=gaining_team,
            confidence=final_conf,
            quality_level=qual,
            source_modules=["EXP-22 possession_v2"],
            supporting_metrics={
                "turnover_frame": frame_idx,
                "losing_team": losing_team,
                "gaining_team": gaining_team,
                "upstream_confidence": conf_raw,
            },
            visibility_quality="HIGH" if visible_players >= 8 else ("MEDIUM" if visible_players >= 6 else "LOW"),
            calibration_quality="VALID" if calibration_valid else "INVALID",
        )
        evt.summary_text = DeterministicSummaryFormatter.format_summary(evt)
        self.timeline.add_event(evt)
        self.graph.add_event(evt)
        return evt

    def ingest_transition_event(
        self,
        event: Any,
        calibration_valid: bool = True,
        visible_players: int = 10,
    ) -> TacticalEvidenceEvent:
        """Converts an EXP-24 tactical transition into a structured Evidence Card (Phase 16)."""
        loss_frame = getattr(event, "loss_frame_index", 0)
        confirm_frame = getattr(event, "confirmation_frame_index", loss_frame + int(self.fps)) or (loss_frame + 25)
        loss_ts = getattr(event, "loss_timestamp", loss_frame / self.fps)
        confirm_ts = confirm_frame / self.fps
        losing_team = getattr(event, "losing_team", "UNKNOWN")
        gaining_team = getattr(event, "gaining_team", "UNKNOWN")
        candidate_label = getattr(event, "candidate_label", None)
        if isinstance(candidate_label, Enum):
            candidate_label = candidate_label.value
        candidate_label = str(candidate_label)

        cp_score = getattr(event, "counterpress_score", 0.0)
        rec_score = getattr(event, "recovery_score", 0.0)
        feats = getattr(event, "features", None)

        metrics: Dict[str, Any] = {
            "counterpress_score": round(float(cp_score), 3),
            "recovery_score": round(float(rec_score), 3),
            "candidate_label": candidate_label,
        }

        if feats is not None:
            metrics.update({
                "pressure_pre_mean": round(getattr(feats, "pressure_pre_mean", 0.0), 3),
                "pressure_post_mean": round(getattr(feats, "pressure_post_mean", 0.0), 3),
                "pressure_delta": round(getattr(feats, "pressure_delta", 0.0), 3),
                "nearest_defender_pre": round(getattr(feats, "nearest_defender_pre", 15.0), 2),
                "nearest_defender_post": round(getattr(feats, "nearest_defender_post", 15.0), 2),
                "nearest_distance_delta": round(getattr(feats, "nearest_distance_delta", 0.0), 2),
                "density_r3_post": round(getattr(feats, "density_r3_post", 0.0), 2),
                "density_r5_post": round(getattr(feats, "density_r5_post", 0.0), 2),
                "centroid_ball_distance_delta": round(getattr(feats, "centroid_ball_distance_delta", 0.0), 2),
                "defensive_line_velocity": round(getattr(feats, "defensive_line_velocity", 0.0), 2),
                "ball_delta_x_attack": round(getattr(feats, "ball_delta_x_attack", 0.0), 2),
            })
            p_change_conf = getattr(feats, "possession_change_confidence", 0.65)
        else:
            p_change_conf = 0.65

        # Accumulate score statistics
        if losing_team in self._counterpress_scores:
            self._counterpress_scores[losing_team].append(float(cp_score))
            self._recovery_scores[losing_team].append(float(rec_score))

        # Assign family & semantic level
        if candidate_label == "COUNTERPRESS_CANDIDATE":
            family = EventFamily.POST_LOSS_ENGAGEMENT
            base_score = float(cp_score)
        elif candidate_label == "DEFENSIVE_RECOVERY_CANDIDATE":
            family = EventFamily.DEFENSIVE_RECOVERY
            base_score = float(rec_score)
        else:
            family = EventFamily.POST_LOSS_ENGAGEMENT
            base_score = max(float(cp_score), float(rec_score), 0.40)

        # LEVEL 3 because it is a candidate interpretation
        sem_level = SemanticLevel.LEVEL_3_TACTICAL_CANDIDATE

        # Strictly enforce upstream confidence ceiling (EXP-22 possession confidence)
        qual = ConfidencePropagator.determine_quality("VALID" if calibration_valid else "INVALID", visible_players)
        final_conf = ConfidencePropagator.compute_confidence(
            base_score=base_score,
            upstream_confidences=[float(p_change_conf)],
            semantic_level=sem_level,
            calibration_valid=calibration_valid,
            visible_outfield=visible_players,
        )

        evt = TacticalEvidenceEvent(
            event_id=f"trans_{loss_frame}_{confirm_frame}_{losing_team}_{candidate_label}",
            sequence_id=self.sequence_id,
            start_frame=loss_frame,
            end_frame=confirm_frame,
            start_timestamp=loss_ts,
            end_timestamp=confirm_ts,
            event_family=family,
            semantic_level=sem_level,
            subject_team=losing_team,
            opponent_team=gaining_team,
            confidence=final_conf,
            quality_level=qual,
            source_modules=["EXP-22 possession_v2", "EXP-23 defensive_pressure", "EXP-24 tactical_transitions"],
            supporting_metrics=metrics,
            limitations=["Diagnostic candidate semantics; physics-derived GT evaluation"],
            visibility_quality="HIGH" if visible_players >= 8 else ("MEDIUM" if visible_players >= 6 else "LOW"),
            calibration_quality="VALID" if calibration_valid else "INVALID",
        )
        evt.summary_text = DeterministicSummaryFormatter.format_summary(evt)
        self.timeline.add_event(evt)
        self.graph.add_event(evt)
        return evt

    def ingest_pass_event(
        self,
        event: Any,
        calibration_valid: bool = True,
        min_pass_confidence: float = 0.30,
    ) -> Optional[TacticalEvidenceEvent]:
        """Converts an EXP-19 pass event into an Evidence Card with strict quality gating (Phase 17)."""
        rel_frame = getattr(event, "release_frame", 0)
        rec_frame = getattr(event, "reception_frame", rel_frame + 15) or (rel_frame + 15)
        rel_ts = getattr(event, "release_timestamp", rel_frame / self.fps)
        rec_ts = getattr(event, "reception_timestamp", rec_frame / self.fps) or (rec_frame / self.fps)
        sender_team = getattr(event, "sender_team", "UNKNOWN")
        receiver_team = getattr(event, "receiver_team", sender_team)
        evt_type = getattr(event, "event_type", None)
        if isinstance(evt_type, Enum):
            evt_type = evt_type.value
        evt_type = str(evt_type)

        conf = getattr(event, "event_confidence", 0.0)
        dist = getattr(event, "pass_displacement_m", 0.0) or 0.0
        fwd = getattr(event, "forward_displacement_m", 0.0) or (getattr(event, "delta_x_attack", 0.0) or 0.0)
        traj = getattr(event, "trajectory", None)
        aerial = getattr(traj, "aerial_suspected", False) if traj else False

        # Phase 17 Quality Gate: reject low-confidence or aerial-gated passes from authoritative timeline
        if conf < min_pass_confidence or aerial or not calibration_valid:
            return None

        if sender_team in self._pass_completed_count and "COMPLETED" in evt_type:
            self._pass_completed_count[sender_team] += 1
        if sender_team in self._progression_totals:
            self._progression_totals[sender_team] += max(0.0, float(fwd))

        qual = QualityLevel.MEDIUM if conf < 0.60 else QualityLevel.HIGH
        final_conf = ConfidencePropagator.compute_confidence(
            base_score=float(conf),
            upstream_confidences=[float(conf)],
            semantic_level=SemanticLevel.LEVEL_1_PHYSICAL_FACT,
            calibration_valid=calibration_valid,
            visible_outfield=10,
        )

        evt = TacticalEvidenceEvent(
            event_id=f"pass_{rel_frame}_{rec_frame}_{sender_team}_{evt_type}",
            sequence_id=self.sequence_id,
            start_frame=rel_frame,
            end_frame=rec_frame,
            start_timestamp=rel_ts,
            end_timestamp=rec_ts,
            event_family=EventFamily.BALL_TRANSFER,
            semantic_level=SemanticLevel.LEVEL_1_PHYSICAL_FACT,
            subject_team=sender_team,
            opponent_team="TEAM_1" if sender_team == "TEAM_0" else "TEAM_0",
            confidence=final_conf,
            quality_level=qual,
            source_modules=["EXP-18/EXP-22 possession", "EXP-19 pass_detector"],
            supporting_metrics={
                "event_type": evt_type,
                "pass_distance_m": round(float(dist), 2),
                "forward_displacement_m": round(float(fwd), 2),
                "sender_track_id": getattr(event, "sender_track_id", None),
                "receiver_track_id": getattr(event, "receiver_track_id", None),
            },
            limitations=["Downstream of pass detector baseline; precision limited by tracking flicker"],
            visibility_quality="HIGH",
            calibration_quality="VALID" if calibration_valid else "INVALID",
        )
        evt.summary_text = DeterministicSummaryFormatter.format_summary(evt)
        self.timeline.add_event(evt)
        self.graph.add_event(evt)
        return evt

    def finalize(
        self,
        last_frame: int,
        last_timestamp: float,
    ) -> Tuple[MatchTacticalTimeline, EventRelationGraph, Dict[str, TeamTacticalAggregate]]:
        """Flushes open continuous episodes, links the graph, and computes team tactical summaries."""
        # 1. Flush open episodes
        flush_events = self.segmenter.finalize(last_frame, last_timestamp)
        for fe in flush_events:
            fe.sequence_id = self.sequence_id
            self.timeline.add_event(fe)
            self.graph.add_event(fe)

        # 2. Sort timeline
        self.timeline.sort()

        # 3. Deduplicate & Link evidential relationships
        EventDeduplicator.link_and_deduplicate(self.timeline.events, self.graph)

        # 4. Compile Team Tactical Aggregates with Reliability Bands
        team_summaries: Dict[str, TeamTacticalAggregate] = {}
        total_f = max(1, self._frames_processed)

        for team_id in ("TEAM_0", "TEAM_1"):
            # Possession metrics
            poss_f = self._possession_frames.get(team_id, 0)
            poss_sec = poss_f / self.fps
            poss_pct = round(100.0 * poss_f / total_f, 1)

            # Block geometry metrics
            h_list = self._block_heights[team_id]
            d_list = self._block_depths[team_id]
            w_list = self._block_widths[team_id]
            hull_list = self._block_hulls[team_id]

            mean_h = float(np.mean(h_list)) if h_list else None
            mean_d = float(np.mean(d_list)) if d_list else None
            mean_w = float(np.mean(w_list)) if w_list else None
            mean_hull = float(np.mean(hull_list)) if hull_list else None

            # Pressure metrics
            p_list = self._pressure_indices[team_id]
            mean_p = float(np.mean(p_list)) if p_list else 0.0
            peak_p = float(np.max(p_list)) if p_list else 0.0

            # Count high quality pressure episodes
            high_q_press = sum(
                1 for e in self.timeline.events
                if e.event_family == EventFamily.PRESSURE_EPISODE
                and e.subject_team == team_id
                and e.quality_level in (QualityLevel.HIGH, QualityLevel.MEDIUM)
            )

            # Transitions
            cp_list = self._counterpress_scores[team_id]
            rec_list = self._recovery_scores[team_id]
            mean_cp = float(np.mean(cp_list)) if cp_list else 0.0
            mean_rec = float(np.mean(rec_list)) if rec_list else 0.0

            # Reliability band
            conf_list = self._confidences[team_id]
            valid_f = len(conf_list)
            cov_pct = round(100.0 * valid_f / total_f, 1)
            mean_conf = float(np.mean(conf_list)) if conf_list else 0.0
            p10_conf = float(np.percentile(conf_list, 10)) if conf_list else 0.0

            rel_band = TeamReliabilityBand(
                coverage_pct=cov_pct,
                valid_frames=valid_f,
                total_frames=total_f,
                confidence_mean=round(mean_conf, 3),
                confidence_p10=round(p10_conf, 3),
                quality_distribution=dict(self._qualities[team_id]),
            )

            # Formation structure policy: line structures primary, nominal hypothesis restricted
            lines_samples = self._formation_lines_samples[team_id]
            lines_summary: List[Dict[str, Any]] = []
            if lines_samples:
                # Count frequency of line structures
                struct_counts = Counter(tuple(s) for s in lines_samples)
                for struct, count in struct_counts.most_common(3):
                    lines_summary.append({
                        "line_structure": list(struct),
                        "frequency": count,
                        "pct": round(100.0 * count / len(lines_samples), 1),
                    })

            # Nominal formation hypothesis only if stable consensus exists
            form_counter = self._formation_consensuses[team_id]
            formation_hypo = None
            if form_counter:
                top_label, top_count = form_counter.most_common(1)[0]
                if top_count >= 25:  # At least 1.0s of continuous stable consensus
                    formation_hypo = top_label

            agg = TeamTacticalAggregate(
                team_id=team_id,
                reliability=rel_band,
                secure_possession_duration_s=round(poss_sec, 2),
                secure_possession_pct=poss_pct,
                possession_change_count=self._possession_change_count[team_id],
                mean_defensive_line_height_m=round(mean_h, 2) if mean_h is not None else None,
                mean_team_depth_m=round(mean_d, 2) if mean_d is not None else None,
                mean_team_width_m=round(mean_w, 2) if mean_w is not None else None,
                mean_hull_area_m2=round(mean_hull, 2) if mean_hull is not None else None,
                mean_pressure_index=round(mean_p, 3),
                peak_pressure_index=round(peak_p, 3),
                high_quality_pressure_episode_count=high_q_press,
                post_loss_counterpress_mean=round(mean_cp, 3),
                defensive_recovery_mean=round(mean_rec, 3),
                net_forward_progression_m=round(self._progression_totals[team_id], 2),
                completed_pass_count=self._pass_completed_count[team_id],
                observed_line_structures=lines_summary,
                formation_hypothesis=formation_hypo,
            )
            team_summaries[team_id] = agg

        return self.timeline, self.graph, team_summaries
