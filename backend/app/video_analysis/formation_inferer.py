"""Dynamic Formation Structure Inference Engine (EXP-21 / Chapter 7).

Infers a team's dynamic structural formation from metric player positions (EXP-15)
and oriented tactical lines (EXP-17) without assigning fixed player roles (CB, CM, ST).

Key Architectural Principles:
1. Temporal structural pattern: distinguishes instantaneous frame structure from stable formation state.
2. Outfield-only: canonical formations use 10 outfield players; goalkeeper is excluded from line counts.
3. Multi-scale signature: preserves continuous geometry (centers, widths, depths, inter-line distances)
   alongside discrete line counts.
4. Visibility gating: requires >=9 outfield for FULL_EVIDENCE, 7-8 for PARTIAL_EVIDENCE, and <=6
   strictly abstains (LOW_EVIDENCE -> UNKNOWN/PARTIAL).
5. Interpretable prototype distance: integer DP sequence alignment + backline anchor + line count penalty.
6. Permutation-invariant: identical result regardless of player IDs or role swaps.
7. Explicit ambiguity: marks AMBIGUOUS (e.g. 3-5-2 vs 5-3-2 wingback ambiguity) rather than forced semantics.
8. Possession context: EXP-18 ball control is consumed purely as an optional diagnostic annotation.
9. Causal temporal state machine: filters frame flutter, emits FORMATION_STRUCTURE_CHANGE on stable transitions.
"""

from __future__ import annotations

import logging
import math
from collections import Counter, deque
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

try:
    from app.video_analysis.pitch_calibration import PitchDimensions
    from app.video_analysis.metric_trajectories import (
        PlayerMetricObservation,
        BallMetricObservation,
    )
    from app.video_analysis.tactical_geometry import (
        TacticalFrameState,
        TeamTacticalGeometry,
    )
    from app.video_analysis.tactical_lines import (
        AttackDirection,
        OrientedTacticalFrameState,
        TeamOrientedTactics,
        TacticalLine,
    )
except ImportError:
    from backend.app.video_analysis.pitch_calibration import PitchDimensions
    from backend.app.video_analysis.metric_trajectories import (
        PlayerMetricObservation,
        BallMetricObservation,
    )
    from backend.app.video_analysis.tactical_geometry import (
        TacticalFrameState,
        TeamTacticalGeometry,
    )
    from backend.app.video_analysis.tactical_lines import (
        AttackDirection,
        OrientedTacticalFrameState,
        TeamOrientedTactics,
        TacticalLine,
    )

logger = logging.getLogger(__name__)


# ==============================================================================
# ENUMS & SCHEMAS
# ==============================================================================

class FormationState(str, Enum):
    """Categorical operational state of the formation inferer."""

    STABLE = "STABLE"                    # High-confidence persistent temporal consensus
    TRANSITIONING = "TRANSITIONING"      # Moving between formations or phase shifts
    AMBIGUOUS = "AMBIGUOUS"              # Competing prototypes close in distance (e.g. 3-5-2 vs 5-3-2)
    PARTIAL = "PARTIAL"                  # Partial outfield visibility (7-8 players)
    UNKNOWN = "UNKNOWN"                  # Low visibility (<=6 players) or uncalibrated


class VisibilityClass(str, Enum):
    """Visibility evidence tier based on visible outfield count (10 outfield total)."""

    FULL_EVIDENCE = "FULL_EVIDENCE"        # N >= 9 trusted outfield players
    PARTIAL_EVIDENCE = "PARTIAL_EVIDENCE"  # N in [7, 8] trusted outfield players
    LOW_EVIDENCE = "LOW_EVIDENCE"          # N <= 6 trusted outfield players


class FormationContext(str, Enum):
    """Optional contextual annotation derived from EXP-18 ball control."""

    IN_POSSESSION = "IN_POSSESSION"
    OUT_OF_POSSESSION = "OUT_OF_POSSESSION"
    CONTESTED = "CONTESTED"
    NONE = "NONE"


@dataclass(frozen=True)
class FormationPrototype:
    """Interpretable canonical formation template."""

    name: str
    line_count: int
    expected_players_per_line: Tuple[int, ...]
    min_defense_width_m: float = 24.0
    min_inter_line_dist_m: float = 8.0

    @property
    def total_players(self) -> int:
        return sum(self.expected_players_per_line)


# Canonical Prototype Registry (Phase 8)
CANONICAL_PROTOTYPES: Dict[str, FormationPrototype] = {
    "4-4-2": FormationPrototype(name="4-4-2", line_count=3, expected_players_per_line=(4, 4, 2), min_defense_width_m=28.0),
    "4-3-3": FormationPrototype(name="4-3-3", line_count=3, expected_players_per_line=(4, 3, 3), min_defense_width_m=28.0),
    "4-2-3-1": FormationPrototype(name="4-2-3-1", line_count=4, expected_players_per_line=(4, 2, 3, 1), min_defense_width_m=28.0),
    "4-1-4-1": FormationPrototype(name="4-1-4-1", line_count=4, expected_players_per_line=(4, 1, 4, 1), min_defense_width_m=28.0),
    "3-5-2": FormationPrototype(name="3-5-2", line_count=3, expected_players_per_line=(3, 5, 2), min_defense_width_m=20.0),
    "3-4-3": FormationPrototype(name="3-4-3", line_count=3, expected_players_per_line=(3, 4, 3), min_defense_width_m=20.0),
    "5-3-2": FormationPrototype(name="5-3-2", line_count=3, expected_players_per_line=(5, 3, 2), min_defense_width_m=32.0),
    "5-4-1": FormationPrototype(name="5-4-1", line_count=3, expected_players_per_line=(5, 4, 1), min_defense_width_m=32.0),
}


@dataclass
class FormationSignature:
    """Multi-scale structural formation representation for a single frame."""

    team_id: str                          # "TEAM_0", "TEAM_1"
    frame_index: int
    timestamp: float
    visible_outfield_count: int

    # Discrete structure
    line_count: int
    players_per_line: List[int]

    # Continuous metric geometry
    line_centers_x_attack: List[float]    # Metric distance from own goal line or attack axis
    line_widths_m: List[float]            # Lateral width per line
    inter_line_distances_m: List[float]   # Longitudinal spacing between consecutive lines
    team_width_m: float                   # Outfield lateral spread
    team_depth_m: float                   # Outfield longitudinal spread

    # Semantic evaluation
    visibility_class: VisibilityClass
    formation_confidence: float
    formation_state: FormationState
    formation_label: str                  # e.g. "4-4-2", "4-3-3", "AMBIGUOUS", "UNKNOWN", "PARTIAL"
    best_prototype: Optional[str] = None
    prototype_distances: Dict[str, float] = field(default_factory=dict)
    observed_lines: List[Dict[str, Any]] = field(default_factory=list)
    missing_player_count: int = 0
    formation_context: FormationContext = FormationContext.NONE
    invalidation_reason: Optional[str] = None


@dataclass
class FormationTransitionEvent:
    """Structured event emitted when stable formation consensus shifts persistently."""

    frame_index: int
    timestamp: float
    team_id: str
    old_formation: str
    new_formation: str
    old_state: FormationState
    new_state: FormationState
    confidence: float
    confirmation_delay_frames: int
    event_type: str = "FORMATION_STRUCTURE_CHANGE"


@dataclass
class TeamFormationState:
    """Consolidated formation state container for a team on a given frame."""

    team_id: str
    instantaneous_signature: FormationSignature
    stable_formation_label: str
    stable_state: FormationState
    state_confidence: float
    stable_duration_frames: int
    evidence_history_length: int
    is_set_piece_deformed: bool = False


@dataclass
class FormationFrameState:
    """Frame-level state container for both teams' formation inference and events."""

    frame_index: int
    timestamp: float
    team_0: TeamFormationState
    team_1: TeamFormationState
    transitions: List[FormationTransitionEvent] = field(default_factory=list)


@dataclass
class FormationConfig:
    """Operational parameters for dynamic formation structure inference."""

    full_evidence_threshold: int = 9         # N >= 9 -> FULL_EVIDENCE
    partial_evidence_threshold: int = 7      # N in [7, 8] -> PARTIAL_EVIDENCE
    low_evidence_threshold: int = 6          # N <= 6 -> LOW_EVIDENCE (abstain)
    temporal_window_frames: int = 50         # Causal evidence window W (50 frames = 2.0s at 25 FPS)
    min_consensus_ratio: float = 0.65        # Fraction of valid frames in buffer required for STABLE
    ambiguity_margin: float = 0.20           # If (2nd_dist - 1st_dist) < margin -> mark AMBIGUOUS
    wingback_ambiguity_threshold: float = 0.35 # Dist margin between 3-back and 5-back variants
    possession_confidence_threshold: float = 0.65
    # Set piece deformation detection
    set_piece_max_depth_m: float = 18.0      # Outfield depth < 18m inside penalty zone
    set_piece_max_width_m: float = 24.0      # Outfield width < 24m
    max_distance_norm: float = 12.0          # Max normalization factor for distance -> confidence


# ==============================================================================
# DISTANCE & ALIGNMENT KERNEL (PHASE 9 & 10)
# ==============================================================================

def compute_formation_distance(
    observed_lines: Sequence[int],
    prototype_lines: Sequence[int],
    w_def: float = 1.5,
    w_lines: float = 1.0,
    max_dist: float = 12.0,
) -> Tuple[float, float]:
    """Interpretable formation distance via dynamic programming sequence alignment.

    Formula:
      Distance = AlignmentCost(obs, proto) + w_def * |obs[0] - proto[0]| + w_lines * |K_obs - M_proto|

    Returns:
      (raw_distance, confidence_score in [0.0, 1.0])
    """
    k = len(observed_lines)
    m = len(prototype_lines)
    if k == 0 or m == 0:
        return max_dist, 0.0

    # DP alignment matrix (Levenshtein style on line player counts)
    dp = [[0.0] * (m + 1) for _ in range(k + 1)]
    for i in range(1, k + 1):
        dp[i][0] = dp[i - 1][0] + observed_lines[i - 1]
    for j in range(1, m + 1):
        dp[0][j] = dp[0][j - 1] + prototype_lines[j - 1]

    for i in range(1, k + 1):
        for j in range(1, m + 1):
            cost_match = abs(observed_lines[i - 1] - prototype_lines[j - 1])
            dp[i][j] = min(
                dp[i - 1][j - 1] + cost_match,
                dp[i - 1][j] + observed_lines[i - 1],
                dp[i][j - 1] + prototype_lines[j - 1],
            )

    align_cost = dp[k][m]
    # Defensive line anchor penalty (first line closest to own goal)
    def_cost = abs(observed_lines[0] - prototype_lines[0]) * w_def
    # Line count difference penalty
    line_count_cost = abs(k - m) * w_lines

    total_dist = align_cost + def_cost + line_count_cost
    confidence = max(0.0, min(1.0, 1.0 - (total_dist / max_dist)))
    return float(total_dist), float(confidence)


# ==============================================================================
# DYNAMIC FORMATION INFERENCE ENGINE
# ==============================================================================

class DynamicFormationEngine:
    """Causal, permutation-invariant dynamic formation structure inference engine.

    Computes multi-scale structural signatures from tactical lines and tracks
    temporal consensus across a sliding causal buffer without lookahead.
    """

    def __init__(self, config: Optional[FormationConfig] = None) -> None:
        self.config = config or FormationConfig()
        # Temporal evidence queues (Phase 7)
        self._history_0: deque[FormationSignature] = deque(maxlen=self.config.temporal_window_frames)
        self._history_1: deque[FormationSignature] = deque(maxlen=self.config.temporal_window_frames)

        # Stable state tracking
        self._stable_label_0: str = "UNKNOWN"
        self._stable_state_0: FormationState = FormationState.UNKNOWN
        self._stable_duration_0: int = 0
        self._last_confirmed_0: str = "UNKNOWN"

        self._stable_label_1: str = "UNKNOWN"
        self._stable_state_1: FormationState = FormationState.UNKNOWN
        self._stable_duration_1: int = 0
        self._last_confirmed_1: str = "UNKNOWN"

    def reset(self) -> None:
        """Resets temporal buffers and state machines."""
        self._history_0.clear()
        self._history_1.clear()
        self._stable_label_0 = "UNKNOWN"
        self._stable_state_0 = FormationState.UNKNOWN
        self._stable_duration_0 = 0
        self._last_confirmed_0 = "UNKNOWN"
        self._stable_label_1 = "UNKNOWN"
        self._stable_state_1 = FormationState.UNKNOWN
        self._stable_duration_1 = 0
        self._last_confirmed_1 = "UNKNOWN"

    def process_frame(
        self,
        frame_index: int,
        timestamp: float,
        players: Sequence[PlayerMetricObservation],
        tactical_geom: TacticalFrameState,
        oriented_tactics: OrientedTacticalFrameState,
        ball: Optional[BallMetricObservation] = None,
        ball_control: Optional[Any] = None,
    ) -> FormationFrameState:
        """Processes a single frame and outputs complete formation structure and events."""
        # 1. Resolve optional contextual possession flag (Phase 12)
        ctx_0, ctx_1 = self._resolve_possession_contexts(ball_control)

        # 2. Extract instantaneous structural signatures for both teams (Phase 3 & 4)
        sig_0 = self._extract_team_signature(
            team_label="TEAM_0",
            frame_index=frame_index,
            timestamp=timestamp,
            players=players,
            team_geom=tactical_geom.team_0,
            team_oriented=oriented_tactics.team_0,
            possession_context=ctx_0,
        )

        sig_1 = self._extract_team_signature(
            team_label="TEAM_1",
            frame_index=frame_index,
            timestamp=timestamp,
            players=players,
            team_geom=tactical_geom.team_1,
            team_oriented=oriented_tactics.team_1,
            possession_context=ctx_1,
        )

        # 3. Update causal temporal state machines & collect transitions (Phase 17 & 18)
        self._history_0.append(sig_0)
        self._history_1.append(sig_1)

        team_state_0, evt_0, new_last_0 = self._update_temporal_state(
            team_label="TEAM_0",
            current_signature=sig_0,
            history=self._history_0,
            prev_stable_label=self._stable_label_0,
            prev_stable_state=self._stable_state_0,
            prev_duration=self._stable_duration_0,
            last_confirmed=self._last_confirmed_0,
        )
        self._stable_label_0 = team_state_0.stable_formation_label
        self._stable_state_0 = team_state_0.stable_state
        self._stable_duration_0 = team_state_0.stable_duration_frames
        self._last_confirmed_0 = new_last_0

        team_state_1, evt_1, new_last_1 = self._update_temporal_state(
            team_label="TEAM_1",
            current_signature=sig_1,
            history=self._history_1,
            prev_stable_label=self._stable_label_1,
            prev_stable_state=self._stable_state_1,
            prev_duration=self._stable_duration_1,
            last_confirmed=self._last_confirmed_1,
        )
        self._stable_label_1 = team_state_1.stable_formation_label
        self._stable_state_1 = team_state_1.stable_state
        self._stable_duration_1 = team_state_1.stable_duration_frames
        self._last_confirmed_1 = new_last_1

        transitions: List[FormationTransitionEvent] = []
        if evt_0 is not None:
            transitions.append(evt_0)
        if evt_1 is not None:
            transitions.append(evt_1)

        return FormationFrameState(
            frame_index=frame_index,
            timestamp=timestamp,
            team_0=team_state_0,
            team_1=team_state_1,
            transitions=transitions,
        )

    def _extract_team_signature(
        self,
        team_label: str,
        frame_index: int,
        timestamp: float,
        players: Sequence[PlayerMetricObservation],
        team_geom: TeamTacticalGeometry,
        team_oriented: TeamOrientedTactics,
        possession_context: FormationContext,
    ) -> FormationSignature:
        """Constructs an instantaneous FormationSignature preserving geometry and discrete structure."""
        # Outfield only (Phase 2)
        team_players = [p for p in players if p.team_label == team_label]
        outfield_players = [p for p in team_players if p.role != "GOALKEEPER"]
        outfield_count = len(outfield_players)
        missing_count = max(0, 10 - outfield_count)

        # Visibility tier (Phase 5)
        if outfield_count >= self.config.full_evidence_threshold:
            vis_class = VisibilityClass.FULL_EVIDENCE
        elif outfield_count >= self.config.partial_evidence_threshold:
            vis_class = VisibilityClass.PARTIAL_EVIDENCE
        else:
            vis_class = VisibilityClass.LOW_EVIDENCE

        # Basic geometry fallbacks
        team_width = getattr(team_geom, "width_m", 0.0) or 0.0
        team_depth = getattr(team_geom, "longitudinal_span_m", 0.0) or 0.0

        # Unoriented or uncalibrated early abstention
        if not team_oriented.is_oriented or team_oriented.attack_direction == AttackDirection.UNKNOWN:
            return FormationSignature(
                team_id=team_label,
                frame_index=frame_index,
                timestamp=timestamp,
                visible_outfield_count=outfield_count,
                line_count=0,
                players_per_line=[],
                line_centers_x_attack=[],
                line_widths_m=[],
                inter_line_distances_m=[],
                team_width_m=team_width,
                team_depth_m=team_depth,
                visibility_class=vis_class,
                formation_confidence=0.0,
                formation_state=FormationState.UNKNOWN,
                formation_label="UNKNOWN",
                missing_player_count=missing_count,
                formation_context=possession_context,
                invalidation_reason="UNKNOWN_ORIENTATION",
            )

        # Extract lines
        lines: List[TacticalLine] = getattr(team_oriented, "lines", [])
        line_count = len(lines)
        players_per_line = [l.player_count for l in lines]
        line_centers = [l.median_x_attack for l in lines]
        line_widths = [l.width_y_m for l in lines]

        # Inter-line separations
        inter_line_dists = [
            float(line_centers[i + 1] - line_centers[i])
            for i in range(len(line_centers) - 1)
        ]

        # Observed lines serialization
        obs_lines_meta = [
            {
                "line_id": l.line_id,
                "player_count": l.player_count,
                "center_x_attack": l.median_x_attack,
                "width_m": l.width_y_m,
                "confidence": l.confidence,
            }
            for l in lines
        ]

        # Detect set-piece collapse (Phase 24)
        is_set_piece = False
        if (
            outfield_count >= 6
            and team_depth < self.config.set_piece_max_depth_m
            and team_width < self.config.set_piece_max_width_m
        ):
            is_set_piece = True

        # Phase 5 & 6: Low visibility abstention
        if vis_class == VisibilityClass.LOW_EVIDENCE:
            return FormationSignature(
                team_id=team_label,
                frame_index=frame_index,
                timestamp=timestamp,
                visible_outfield_count=outfield_count,
                line_count=line_count,
                players_per_line=players_per_line,
                line_centers_x_attack=line_centers,
                line_widths_m=line_widths,
                inter_line_distances_m=inter_line_dists,
                team_width_m=team_width,
                team_depth_m=team_depth,
                visibility_class=vis_class,
                formation_confidence=0.0,
                formation_state=FormationState.UNKNOWN,
                formation_label="UNKNOWN",
                observed_lines=obs_lines_meta,
                missing_player_count=missing_count,
                formation_context=possession_context,
                invalidation_reason="LOW_VISIBILITY",
            )

        if is_set_piece:
            return FormationSignature(
                team_id=team_label,
                frame_index=frame_index,
                timestamp=timestamp,
                visible_outfield_count=outfield_count,
                line_count=line_count,
                players_per_line=players_per_line,
                line_centers_x_attack=line_centers,
                line_widths_m=line_widths,
                inter_line_distances_m=inter_line_dists,
                team_width_m=team_width,
                team_depth_m=team_depth,
                visibility_class=vis_class,
                formation_confidence=0.20,
                formation_state=FormationState.TRANSITIONING,
                formation_label="SET_PIECE_DEFORMATION",
                observed_lines=obs_lines_meta,
                missing_player_count=missing_count,
                formation_context=possession_context,
                invalidation_reason="SET_PIECE_DEFORMATION",
            )

        if line_count == 0:
            return FormationSignature(
                team_id=team_label,
                frame_index=frame_index,
                timestamp=timestamp,
                visible_outfield_count=outfield_count,
                line_count=0,
                players_per_line=[],
                line_centers_x_attack=[],
                line_widths_m=[],
                inter_line_distances_m=[],
                team_width_m=team_width,
                team_depth_m=team_depth,
                visibility_class=vis_class,
                formation_confidence=0.0,
                formation_state=FormationState.UNKNOWN,
                formation_label="UNKNOWN",
                missing_player_count=missing_count,
                formation_context=possession_context,
                invalidation_reason="NO_LINES_DISCOVERED",
            )

        # ----------------------------------------------------------------------
        # Phase 8, 9, 11: Distance to Prototypes & Ambiguity Resolution
        # ----------------------------------------------------------------------
        proto_dists: Dict[str, float] = {}
        for p_name, p_obj in CANONICAL_PROTOTYPES.items():
            dist, _ = compute_formation_distance(
                observed_lines=players_per_line,
                prototype_lines=p_obj.expected_players_per_line,
                max_dist=self.config.max_distance_norm,
            )
            proto_dists[p_name] = dist

        sorted_protos = sorted(proto_dists.items(), key=lambda item: item[1])
        best_name, best_dist = sorted_protos[0]
        runner_up_name, runner_up_dist = sorted_protos[1]

        best_conf = max(0.0, min(1.0, 1.0 - (best_dist / self.config.max_distance_norm)))
        dist_margin = runner_up_dist - best_dist

        # Check for 3-back vs 5-back ambiguity (Phase 11)
        is_3_5_ambiguity = False
        three_vs_five_pairs = {("3-5-2", "5-3-2"), ("5-3-2", "3-5-2"), ("3-4-3", "5-4-1"), ("5-4-1", "3-4-3")}
        if (best_name, runner_up_name) in three_vs_five_pairs and dist_margin < self.config.wingback_ambiguity_threshold:
            is_3_5_ambiguity = True

        # Determine frame-level state & label
        if vis_class == VisibilityClass.PARTIAL_EVIDENCE:
            f_state = FormationState.PARTIAL
            f_label = "PARTIAL"
        elif is_3_5_ambiguity:
            f_state = FormationState.AMBIGUOUS
            f_label = "AMBIGUOUS_3_5_STRUCTURE"
        elif dist_margin < self.config.ambiguity_margin and best_dist > 1.0:
            f_state = FormationState.AMBIGUOUS
            f_label = "AMBIGUOUS"
        elif best_conf >= 0.50:
            f_state = FormationState.STABLE
            f_label = best_name
        else:
            f_state = FormationState.TRANSITIONING
            f_label = "TRANSITIONING"

        return FormationSignature(
            team_id=team_label,
            frame_index=frame_index,
            timestamp=timestamp,
            visible_outfield_count=outfield_count,
            line_count=line_count,
            players_per_line=players_per_line,
            line_centers_x_attack=line_centers,
            line_widths_m=line_widths,
            inter_line_distances_m=inter_line_dists,
            team_width_m=team_width,
            team_depth_m=team_depth,
            visibility_class=vis_class,
            formation_confidence=best_conf,
            formation_state=f_state,
            formation_label=f_label,
            best_prototype=best_name,
            prototype_distances=proto_dists,
            observed_lines=obs_lines_meta,
            missing_player_count=missing_count,
            formation_context=possession_context,
            invalidation_reason=None,
        )

    def _update_temporal_state(
        self,
        team_label: str,
        current_signature: FormationSignature,
        history: deque[FormationSignature],
        prev_stable_label: str,
        prev_stable_state: FormationState,
        prev_duration: int,
        last_confirmed: str = "UNKNOWN",
    ) -> Tuple[TeamFormationState, Optional[FormationTransitionEvent], str]:
        """Maintains causal formation consensus over sliding window W (Phase 17 & 18)."""
        # Collect evaluable signatures from history
        evaluable_sigs = [
            s for s in history
            if s.visibility_class != VisibilityClass.LOW_EVIDENCE
            and s.formation_label not in ("UNKNOWN", "SET_PIECE_DEFORMATION")
            and s.best_prototype is not None
        ]

        total_history = len(history)
        event: Optional[FormationTransitionEvent] = None

        if len(evaluable_sigs) < max(5, total_history // 3):
            # Not enough trusted frames in buffer
            new_label = "UNKNOWN" if current_signature.visibility_class == VisibilityClass.LOW_EVIDENCE else "PARTIAL"
            new_state = FormationState.UNKNOWN if new_label == "UNKNOWN" else FormationState.PARTIAL
            new_duration = (prev_duration + 1) if new_label == prev_stable_label else 1
            team_state = TeamFormationState(
                team_id=team_label,
                instantaneous_signature=current_signature,
                stable_formation_label=new_label,
                stable_state=new_state,
                state_confidence=0.0,
                stable_duration_frames=new_duration,
                evidence_history_length=total_history,
                is_set_piece_deformed=(current_signature.invalidation_reason == "SET_PIECE_DEFORMATION"),
            )
            return team_state, None, last_confirmed

        # Count prototype votes across evaluable buffer
        votes = Counter(s.best_prototype for s in evaluable_sigs if s.best_prototype is not None)
        top_prototype, top_count = votes.most_common(1)[0]
        consensus_ratio = top_count / len(evaluable_sigs)

        avg_conf = float(np.mean([s.formation_confidence for s in evaluable_sigs if s.best_prototype == top_prototype]))

        # Check for ambiguity across buffer
        if len(votes) >= 2:
            runner_up_proto, runner_up_count = votes.most_common(2)[1]
            vote_margin = (top_count - runner_up_count) / len(evaluable_sigs)
        else:
            vote_margin = 1.0

        if consensus_ratio >= self.config.min_consensus_ratio and avg_conf >= 0.45:
            new_state = FormationState.STABLE
            new_label = top_prototype
        elif vote_margin < 0.20:
            new_state = FormationState.AMBIGUOUS
            new_label = "AMBIGUOUS"
        else:
            new_state = FormationState.TRANSITIONING
            new_label = "TRANSITIONING"

        # Duration and transition trigger
        new_last_confirmed = last_confirmed
        if new_label == prev_stable_label:
            new_duration = prev_duration + 1
        else:
            new_duration = 1
            if (
                new_state == FormationState.STABLE
                and new_label in CANONICAL_PROTOTYPES
            ):
                if (
                    last_confirmed not in ("UNKNOWN", "PARTIAL")
                    and last_confirmed != new_label
                ):
                    event = FormationTransitionEvent(
                        frame_index=current_signature.frame_index,
                        timestamp=current_signature.timestamp,
                        team_id=team_label,
                        old_formation=last_confirmed,
                        new_formation=new_label,
                        old_state=FormationState.STABLE,
                        new_state=new_state,
                        confidence=avg_conf,
                        confirmation_delay_frames=total_history,
                    )
                new_last_confirmed = new_label

        team_state = TeamFormationState(
            team_id=team_label,
            instantaneous_signature=current_signature,
            stable_formation_label=new_label,
            stable_state=new_state,
            state_confidence=avg_conf,
            stable_duration_frames=new_duration,
            evidence_history_length=total_history,
            is_set_piece_deformed=(current_signature.invalidation_reason == "SET_PIECE_DEFORMATION"),
        )
        return team_state, event, new_last_confirmed

    def _resolve_possession_contexts(self, ball_control: Optional[Any]) -> Tuple[FormationContext, FormationContext]:
        """Maps optional EXP-18 ball control state into contextual annotations without altering formation."""
        if ball_control is None:
            return FormationContext.NONE, FormationContext.NONE

        controlling_team = getattr(ball_control, "controlling_team", None)
        confidence = getattr(ball_control, "confidence", 0.0) or 0.0

        if controlling_team is None or confidence < self.config.possession_confidence_threshold:
            return FormationContext.CONTESTED, FormationContext.CONTESTED

        if controlling_team in ("TEAM_0", 0):
            return FormationContext.IN_POSSESSION, FormationContext.OUT_OF_POSSESSION
        elif controlling_team in ("TEAM_1", 1):
            return FormationContext.OUT_OF_POSSESSION, FormationContext.IN_POSSESSION

        return FormationContext.CONTESTED, FormationContext.CONTESTED
