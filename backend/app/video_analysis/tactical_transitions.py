"""Tactical Transitions & Counter-Press Candidates Engine (EXP-24 / Chapter 7).

Detects tactical transition states and immediate post-loss defensive engagement from:
- Possession V2 changes (PossessionChangeEvent)
- Continuous Defensive Pressure Index (EXP-23)
- Defender closing dynamics & multi-scale density (EXP-23)
- Defensive block motion & team centroid motion (EXP-20)
- Oriented tactical attacking direction & ball progression (EXP-17)
without relying on nominal formation labels (EXP-21 closed).

Outputs candidate semantics:
- POSSESSION_LOSS, POSSESSION_GAIN
- ATTACK_TO_DEFENSE_TRANSITION, DEFENSE_TO_ATTACK_TRANSITION
- COUNTERPRESS_CANDIDATE, DEFENSIVE_RECOVERY_CANDIDATE, NEUTRAL_TRANSITION
- AMBIGUOUS, NOT_VISIBLE
- PENDING_TRANSITION (strictly causal during post-loss evidence accumulation)
- Continuous CounterpressScore in [0.0, 1.0] and RecoveryScore in [0.0, 1.0]
"""

from __future__ import annotations

import logging
import math
from collections import deque
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
        OrientedTacticalFrameState,
        TeamOrientedTactics,
    )
    from app.video_analysis.defensive_block import (
        DefensiveBlockFrameState,
        DefensiveBlockMetrics,
    )
    from app.video_analysis.possession import (
        PossessionChangeEvent,
        TeamPossessionFrameState,
        PossessionStatus,
    )
    from app.video_analysis.defensive_pressure import (
        FrameDefensivePressureState,
        PressureTargetType,
        IndividualDefenderPressure,
    )
except ImportError:
    # Relative fallback
    from .pitch_calibration import PitchDimensions
    from .metric_trajectories import (
        PlayerMetricObservation,
        BallMetricObservation,
    )
    from .tactical_geometry import (
        TacticalFrameState,
        TeamTacticalGeometry,
    )
    from .tactical_lines import (
        OrientedTacticalFrameState,
        TeamOrientedTactics,
    )
    from .defensive_block import (
        DefensiveBlockFrameState,
        DefensiveBlockMetrics,
    )
    from .possession import (
        PossessionChangeEvent,
        TeamPossessionFrameState,
        PossessionStatus,
    )
    from .defensive_pressure import (
        FrameDefensivePressureState,
        PressureTargetType,
        IndividualDefenderPressure,
    )

logger = logging.getLogger("TACTICAL_TRANSITIONS")


# ==============================================================================
# ENUMS & TYPES
# ==============================================================================

class TransitionType(str, Enum):
    """Team-level macro tactical state change."""
    POSSESSION_LOSS = "POSSESSION_LOSS"
    POSSESSION_GAIN = "POSSESSION_GAIN"
    ATTACK_TO_DEFENSE = "ATTACK_TO_DEFENSE"
    DEFENSE_TO_ATTACK = "DEFENSE_TO_ATTACK"
    NO_TRANSITION = "NO_TRANSITION"


class TransitionCandidate(str, Enum):
    """Causal transition engagement candidate classifications."""
    COUNTERPRESS_CANDIDATE = "COUNTERPRESS_CANDIDATE"
    DEFENSIVE_RECOVERY_CANDIDATE = "DEFENSIVE_RECOVERY_CANDIDATE"
    NEUTRAL_TRANSITION = "NEUTRAL_TRANSITION"
    PENDING_TRANSITION = "PENDING_TRANSITION"
    AMBIGUOUS = "AMBIGUOUS"
    NOT_VISIBLE = "NOT_VISIBLE"


class AttackingResponse(str, Enum):
    """Attacking team progression response following possession recovery."""
    FAST_ATTACK = "FAST_ATTACK"
    SLOW_BUILDUP = "SLOW_BUILDUP"
    AMBIGUOUS = "AMBIGUOUS"


class ConfidenceGate(str, Enum):
    """Upstream possession change confidence tier."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


# ==============================================================================
# FEATURE VECTOR & TRANSITION EVENT DATACLASSES
# ==============================================================================

@dataclass
class TransitionFeatureVector:
    """17-dimensional continuous feature vector capturing pre/post turnover dynamics."""

    possession_change_confidence: float = 0.0

    # Pressure signals (EXP-23)
    pressure_pre_mean: float = 0.0
    pressure_post_mean: float = 0.0
    pressure_delta: float = 0.0

    # Nearest defender proximity
    nearest_defender_pre: float = 15.0
    nearest_defender_post: float = 15.0
    nearest_distance_delta: float = 0.0

    # Defender closing kinematics
    closing_speed_post_mean: Optional[float] = None
    max_closing_speed_post: Optional[float] = None

    # Defensive density near new carrier
    density_r3_post: float = 0.0
    density_r5_post: float = 0.0
    coverage_ratio_post: float = 0.0

    # Team spatial response
    centroid_ball_distance_delta: float = 0.0
    defensive_line_velocity: float = 0.0
    team_depth_delta: float = 0.0
    team_width_delta: float = 0.0

    # Gaining team progression
    ball_delta_x_attack: float = 0.0


@dataclass
class TacticalTransitionEvent:
    """Discrete transition event anchored on a confirmed possession turnover."""

    event_id: str
    loss_frame_index: int
    loss_timestamp: float
    losing_team: str
    gaining_team: str
    confidence_level: ConfidenceGate
    features: TransitionFeatureVector
    counterpress_score: float = 0.0
    recovery_score: float = 0.0
    candidate_label: TransitionCandidate = TransitionCandidate.PENDING_TRANSITION
    attacking_response: AttackingResponse = AttackingResponse.AMBIGUOUS
    is_confirmed: bool = False
    confirmation_frame_index: Optional[int] = None
    visible_outfield_count: int = 0
    pressure_visibility_quality: str = "UNKNOWN"
    block_geometry_valid: bool = True
    failure_reason: Optional[str] = None


@dataclass
class FrameTacticalTransitionState:
    """Frame-level tactical transition state output."""

    frame_index: int
    timestamp: float
    team_0_transition_type: TransitionType = TransitionType.NO_TRANSITION
    team_1_transition_type: TransitionType = TransitionType.NO_TRANSITION
    active_event: Optional[TacticalTransitionEvent] = None
    candidate_label: TransitionCandidate = TransitionCandidate.NEUTRAL_TRANSITION
    counterpress_score: float = 0.0
    recovery_score: float = 0.0
    is_pending: bool = False
    causal_confirmation_frame: Optional[int] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serializes frame state into JSON-compatible dictionary."""
        d = asdict(self)
        d["team_0_transition_type"] = self.team_0_transition_type.value
        d["team_1_transition_type"] = self.team_1_transition_type.value
        d["candidate_label"] = self.candidate_label.value
        if self.active_event is not None:
            d["active_event"]["confidence_level"] = self.active_event.confidence_level.value
            d["active_event"]["candidate_label"] = self.active_event.candidate_label.value
            d["active_event"]["attacking_response"] = self.active_event.attacking_response.value
        return d


# ==============================================================================
# CONFIGURATION
# ==============================================================================

@dataclass
class TacticalTransitionsConfig:
    """Configuration for causal transition windowing, thresholds, and scoring."""

    window_pre_frames: int = 25       # 1.0 s at 25 fps
    window_post_frames: int = 25      # 1.0 s at 25 fps
    min_possession_confidence: float = 0.40
    high_confidence_threshold: float = 0.70
    med_confidence_threshold: float = 0.45
    min_visible_outfield: int = 6
    counterpress_score_threshold: float = 0.52
    recovery_score_threshold: float = 0.48
    fast_attack_progression_m: float = 5.0
    slow_buildup_progression_m: float = 2.0
    fps: float = 25.0


# ==============================================================================
# SLIDING BUFFER SNAPSHOT
# ==============================================================================

@dataclass
class _FrameSnapshot:
    """Internal lightweight snapshot of historical frames for causal pre/post extraction."""

    frame_index: int
    timestamp: float
    pressure_state: Optional[FrameDefensivePressureState]
    block_state: Optional[DefensiveBlockFrameState]
    oriented_state: Optional[OrientedTacticalFrameState]
    possession_state: Optional[TeamPossessionFrameState]
    ball_pos: Optional[Tuple[float, float]]
    visible_outfield_count: int


# ==============================================================================
# CONTINUOUS TRANSITION SCORER
# ==============================================================================

class ContinuousTransitionScorer:
    """Computes monotonic CounterpressScore and RecoveryScore in [0.0, 1.0]."""

    def __init__(self, config: TacticalTransitionsConfig) -> None:
        self.config = config

    def compute_scores(self, fv: TransitionFeatureVector) -> Tuple[float, float, TransitionCandidate]:
        """Calculates CounterpressScore and RecoveryScore with verified mathematical monotonicity."""
        # ----------------------------------------------------------------------
        # 1. COUNTERPRESS SCORE COMPONENTS
        # ----------------------------------------------------------------------
        # A. Pressure Intensity & Increase (higher post pressure and positive delta)
        p_post = min(1.0, max(0.0, fv.pressure_post_mean))
        p_delta = min(1.0, max(0.0, (fv.pressure_delta + 0.20) / 0.50))
        s_pressure = 0.50 * p_post + 0.50 * p_delta

        # B. Distance & Closing Speed (closer defender and positive closing velocity)
        d_post_norm = min(1.0, max(0.0, (8.0 - fv.nearest_defender_post) / 8.0))
        if fv.closing_speed_post_mean is not None:
            v_close_norm = min(1.0, max(0.0, (fv.closing_speed_post_mean + 1.0) / 5.0))
            s_close = 0.45 * d_post_norm + 0.55 * v_close_norm
        else:
            s_close = d_post_norm

        # C. Defensive Density near New Carrier
        r3_norm = min(1.0, fv.density_r3_post / 2.0)
        r5_norm = min(1.0, fv.density_r5_post / 3.0)
        s_density = 0.50 * r3_norm + 0.50 * r5_norm

        # D. Geometric Convergence (centroid approaching ball, defensive line advancing)
        # Negative delta centroid-ball distance means approaching the ball
        c_close_norm = min(1.0, max(0.0, (-fv.centroid_ball_distance_delta + 1.5) / 3.0))
        # Positive line velocity means stepping up toward the ball/midfield
        line_norm = min(1.0, max(0.0, (fv.defensive_line_velocity + 1.0) / 2.5))
        s_geom = 0.50 * c_close_norm + 0.50 * line_norm

        # Monotonic weighted CounterpressScore in [0.0, 1.0]
        cp_score = 0.35 * s_pressure + 0.25 * s_close + 0.20 * s_density + 0.20 * s_geom
        cp_score = float(np.clip(cp_score, 0.0, 1.0))

        # ----------------------------------------------------------------------
        # 2. DEFENSIVE RECOVERY SCORE COMPONENTS
        # ----------------------------------------------------------------------
        # A. Absence of Immediate Pressure
        s_no_press = min(1.0, max(0.0, (0.25 - fv.pressure_post_mean) / 0.25))

        # B. Separation from New Carrier (increasing distance, negative closing velocity)
        d_sep_norm = min(1.0, max(0.0, (fv.nearest_distance_delta + 1.0) / 4.0))
        if fv.closing_speed_post_mean is not None:
            v_sep_norm = min(1.0, max(0.0, (-fv.closing_speed_post_mean + 1.0) / 4.0))
            s_separate = 0.50 * d_sep_norm + 0.50 * v_sep_norm
        else:
            s_separate = d_sep_norm

        # C. Geometric Retreat (centroid moving away from ball, line retreating toward own goal)
        c_retreat_norm = min(1.0, max(0.0, (fv.centroid_ball_distance_delta + 1.0) / 3.0))
        line_retreat_norm = min(1.0, max(0.0, (-fv.defensive_line_velocity + 1.0) / 2.5))
        s_retreat = 0.50 * c_retreat_norm + 0.50 * line_retreat_norm

        # D. Low Opponent Density
        s_low_density = max(0.0, 1.0 - (fv.density_r3_post + fv.density_r5_post) / 3.0)

        # Monotonic weighted RecoveryScore in [0.0, 1.0]
        rec_score = 0.30 * s_no_press + 0.30 * s_retreat + 0.25 * s_separate + 0.15 * s_low_density
        rec_score = float(np.clip(rec_score, 0.0, 1.0))

        # ----------------------------------------------------------------------
        # 3. CANDIDATE LABEL ASSIGNMENT
        # ----------------------------------------------------------------------
        # Gate on confidence
        if fv.possession_change_confidence < self.config.med_confidence_threshold:
            candidate = TransitionCandidate.AMBIGUOUS
        elif cp_score >= self.config.counterpress_score_threshold and cp_score > rec_score + 0.10:
            candidate = TransitionCandidate.COUNTERPRESS_CANDIDATE
        elif rec_score >= self.config.recovery_score_threshold and rec_score > cp_score + 0.08:
            candidate = TransitionCandidate.DEFENSIVE_RECOVERY_CANDIDATE
        else:
            candidate = TransitionCandidate.NEUTRAL_TRANSITION

        return cp_score, rec_score, candidate


# ==============================================================================
# MAIN TACTICAL TRANSITIONS ENGINE
# ==============================================================================

class TacticalTransitionsEngine:
    """End-to-end causal engine for tactical transitions and counter-press candidate inference."""

    def __init__(self, config: Optional[TacticalTransitionsConfig] = None) -> None:
        self.config = config or TacticalTransitionsConfig()
        self.scorer = ContinuousTransitionScorer(self.config)

        # Causal sliding historical buffer (stores up to ~6 seconds at 25 fps)
        self.history: deque[_FrameSnapshot] = deque(maxlen=150)

        # Active events pending causal post-window confirmation
        self.pending_events: List[TacticalTransitionEvent] = []

        # Chronological confirmed event store
        self.confirmed_events: List[TacticalTransitionEvent] = []

        # State tracking
        self.active_transition_event: Optional[TacticalTransitionEvent] = None
        self.transition_frames_remaining: int = 0
        self.current_losing_team: Optional[str] = None
        self.current_gaining_team: Optional[str] = None

    def reset(self) -> None:
        """Resets all internal history and pending events."""
        self.history.clear()
        self.pending_events.clear()
        self.confirmed_events.clear()
        self.active_transition_event = None
        self.transition_frames_remaining = 0
        self.current_losing_team = None
        self.current_gaining_team = None

    def process_frame(
        self,
        frame_index: int,
        timestamp: float,
        player_observations: Sequence[Union[PlayerMetricObservation, Dict[str, Any]]],
        ball_observation: Optional[Union[BallMetricObservation, Dict[str, Any]]],
        possession_state_v2: Optional[TeamPossessionFrameState],
        pressure_state: Optional[FrameDefensivePressureState] = None,
        block_frame_state: Optional[DefensiveBlockFrameState] = None,
        oriented_tactics_state: Optional[OrientedTacticalFrameState] = None,
        calibration_valid: bool = True,
    ) -> FrameTacticalTransitionState:
        """Processes a single frame causally and emits FrameTacticalTransitionState."""
        # 1. Count outfield players
        vis_outfield = 0
        for p in player_observations:
            role = p.get("role") if isinstance(p, dict) else getattr(p, "role", "OUTFIELD_PLAYER")
            if role != "REFEREE":
                vis_outfield += 1

        # Extract ball position
        ball_pos = None
        if ball_observation is not None:
            bx = ball_observation.get("pitch_x_m") if isinstance(ball_observation, dict) else getattr(ball_observation, "pitch_x_m", None)
            by = ball_observation.get("pitch_y_m") if isinstance(ball_observation, dict) else getattr(ball_observation, "pitch_y_m", None)
            if bx is not None and by is not None:
                ball_pos = (float(bx), float(by))

        # 2. Append causal snapshot to historical ring buffer
        snapshot = _FrameSnapshot(
            frame_index=frame_index,
            timestamp=timestamp,
            pressure_state=pressure_state,
            block_state=block_frame_state,
            oriented_state=oriented_tactics_state,
            possession_state=possession_state_v2,
            ball_pos=ball_pos,
            visible_outfield_count=vis_outfield,
        )
        self.history.append(snapshot)

        # 3. Detect Turnover Anchor (PossessionChangeEvent)
        turnover_event: Optional[PossessionChangeEvent] = None
        if possession_state_v2 is not None:
            turnover_event = possession_state_v2.recent_possession_change

        if turnover_event is not None and turnover_event.confidence >= self.config.min_possession_confidence:
            losing = turnover_event.from_team
            gaining = turnover_event.to_team

            if losing in ("TEAM_0", "TEAM_1") and gaining in ("TEAM_0", "TEAM_1") and losing != gaining:
                # Assign confidence tier
                if turnover_event.confidence >= self.config.high_confidence_threshold:
                    conf_tier = ConfidenceGate.HIGH
                elif turnover_event.confidence >= self.config.med_confidence_threshold:
                    conf_tier = ConfidenceGate.MEDIUM
                else:
                    conf_tier = ConfidenceGate.LOW

                # Create pending transition event
                event_id = f"trans_{frame_index}_{losing}_to_{gaining}"
                evt = TacticalTransitionEvent(
                    event_id=event_id,
                    loss_frame_index=frame_index,
                    loss_timestamp=timestamp,
                    losing_team=losing,
                    gaining_team=gaining,
                    confidence_level=conf_tier,
                    features=TransitionFeatureVector(possession_change_confidence=turnover_event.confidence),
                    candidate_label=TransitionCandidate.PENDING_TRANSITION,
                    is_confirmed=False,
                    visible_outfield_count=vis_outfield,
                    block_geometry_valid=bool(block_frame_state is not None),
                )
                self.pending_events.append(evt)
                self.active_transition_event = evt
                self.transition_frames_remaining = self.config.window_post_frames
                self.current_losing_team = losing
                self.current_gaining_team = gaining

        # 4. Check Pending Events for Causal Confirmation
        for evt in list(self.pending_events):
            frames_since_loss = frame_index - evt.loss_frame_index
            if frames_since_loss >= self.config.window_post_frames:
                # Post-window evidence is now complete and strictly causal
                self._resolve_pending_event(evt, frame_index)
                self.pending_events.remove(evt)
                self.confirmed_events.append(evt)

        # 5. Determine Current Frame Macro Transition Types
        t0_type = TransitionType.NO_TRANSITION
        t1_type = TransitionType.NO_TRANSITION

        if self.transition_frames_remaining > 0:
            self.transition_frames_remaining -= 1
            if self.current_losing_team == "TEAM_0":
                t0_type = TransitionType.ATTACK_TO_DEFENSE
                t1_type = TransitionType.DEFENSE_TO_ATTACK
            elif self.current_losing_team == "TEAM_1":
                t1_type = TransitionType.ATTACK_TO_DEFENSE
                t0_type = TransitionType.DEFENSE_TO_ATTACK

        # 6. Current Candidate Label & Scores
        cand_label = TransitionCandidate.NEUTRAL_TRANSITION
        cp_score = 0.0
        rec_score = 0.0
        is_pending = False
        confirmation_fid = None

        if self.active_transition_event is not None:
            cand_label = self.active_transition_event.candidate_label
            cp_score = self.active_transition_event.counterpress_score
            rec_score = self.active_transition_event.recovery_score
            is_pending = not self.active_transition_event.is_confirmed
            confirmation_fid = self.active_transition_event.confirmation_frame_index

        return FrameTacticalTransitionState(
            frame_index=frame_index,
            timestamp=timestamp,
            team_0_transition_type=t0_type,
            team_1_transition_type=t1_type,
            active_event=self.active_transition_event,
            candidate_label=cand_label,
            counterpress_score=cp_score,
            recovery_score=rec_score,
            is_pending=is_pending,
            causal_confirmation_frame=confirmation_fid,
            details={
                "transition_frames_remaining": self.transition_frames_remaining,
                "pending_events_count": len(self.pending_events),
                "confirmed_events_count": len(self.confirmed_events),
                "visible_outfield_count": vis_outfield,
                "is_low_visibility": bool(vis_outfield < self.config.min_visible_outfield),
            },
        )

    def _resolve_pending_event(self, evt: TacticalTransitionEvent, current_frame_index: int) -> None:
        """Extracts causal pre/post signals and calculates final candidate classification."""
        loss_fid = evt.loss_frame_index
        pre_start = loss_fid - self.config.window_pre_frames
        post_end = loss_fid + self.config.window_post_frames

        # Extract snapshots from history buffer
        pre_snaps = [s for s in self.history if pre_start <= s.frame_index < loss_fid]
        post_snaps = [s for s in self.history if loss_fid <= s.frame_index <= post_end]

        if not post_snaps:
            evt.candidate_label = TransitionCandidate.AMBIGUOUS
            evt.failure_reason = "insufficient_post_snapshots"
            evt.is_confirmed = True
            evt.confirmation_frame_index = current_frame_index
            return

        # Check visibility gating
        mean_vis = float(np.mean([s.visible_outfield_count for s in post_snaps]))
        if mean_vis < self.config.min_visible_outfield:
            evt.candidate_label = TransitionCandidate.NOT_VISIBLE
            evt.failure_reason = "low_camera_visibility"
            evt.is_confirmed = True
            evt.confirmation_frame_index = current_frame_index
            return

        # ----------------------------------------------------------------------
        # Extract Continuous Pre/Post Signals
        # ----------------------------------------------------------------------
        # Pressure indices
        p_pre_vals = [s.pressure_state.pressure_index for s in pre_snaps if s.pressure_state is not None]
        p_post_vals = [s.pressure_state.pressure_index for s in post_snaps if s.pressure_state is not None]

        p_pre_mean = float(np.mean(p_pre_vals)) if p_pre_vals else 0.05
        p_post_mean = float(np.mean(p_post_vals)) if p_post_vals else 0.05
        p_delta = p_post_mean - p_pre_mean

        # Nearest defender distances
        d_pre_vals = [s.pressure_state.nearest_defender_distance_m for s in pre_snaps if s.pressure_state and s.pressure_state.nearest_defender_distance_m is not None]
        d_post_vals = [s.pressure_state.nearest_defender_distance_m for s in post_snaps if s.pressure_state and s.pressure_state.nearest_defender_distance_m is not None]

        d_pre_mean = float(np.mean(d_pre_vals)) if d_pre_vals else 12.0
        d_post_mean = float(np.mean(d_post_vals)) if d_post_vals else 12.0
        d_delta = d_post_mean - d_pre_mean

        # Closing speeds post-loss
        cs_post_vals = [s.pressure_state.nearest_defender_closing_speed_mps for s in post_snaps if s.pressure_state and s.pressure_state.nearest_defender_closing_speed_mps is not None]
        cs_mean = float(np.mean(cs_post_vals)) if cs_post_vals else None
        cs_max = float(np.max(cs_post_vals)) if cs_post_vals else None

        # Densities post-loss
        r3_vals = [s.pressure_state.n_defenders_r3 for s in post_snaps if s.pressure_state is not None]
        r5_vals = [s.pressure_state.n_defenders_r5 for s in post_snaps if s.pressure_state is not None]
        cov_vals = [s.pressure_state.angular_coverage.coverage_ratio for s in post_snaps if s.pressure_state is not None and s.pressure_state.angular_coverage is not None]

        r3_post = float(np.mean(r3_vals)) if r3_vals else 0.0
        r5_post = float(np.mean(r5_vals)) if r5_vals else 0.0
        cov_post = float(np.mean(cov_vals)) if cov_vals else 0.0

        # Team Centroid-to-Ball distance delta
        # Losing team's centroid relative to the ball
        c_ball_post_vals: List[float] = []
        for s in post_snaps:
            if s.block_state is not None:
                b_metrics = s.block_state.team_0 if evt.losing_team == "TEAM_0" else s.block_state.team_1
                if b_metrics and b_metrics.centroid_to_ball_distance_m is not None:
                    c_ball_post_vals.append(b_metrics.centroid_to_ball_distance_m)

        c_ball_pre_vals: List[float] = []
        for s in pre_snaps:
            if s.block_state is not None:
                b_metrics = s.block_state.team_0 if evt.losing_team == "TEAM_0" else s.block_state.team_1
                if b_metrics and b_metrics.centroid_to_ball_distance_m is not None:
                    c_ball_pre_vals.append(b_metrics.centroid_to_ball_distance_m)

        c_pre = float(np.mean(c_ball_pre_vals)) if c_ball_pre_vals else 20.0
        c_post = float(np.mean(c_ball_post_vals)) if c_ball_post_vals else 20.0
        c_delta = c_post - c_pre

        # Defensive line velocity (step-up vs drop)
        line_h_post_vals: List[float] = []
        depth_post_vals: List[float] = []
        width_post_vals: List[float] = []
        for s in post_snaps:
            if s.block_state is not None:
                b_metrics = s.block_state.team_0 if evt.losing_team == "TEAM_0" else s.block_state.team_1
                if b_metrics:
                    if b_metrics.defensive_line_height_m is not None:
                        line_h_post_vals.append(b_metrics.defensive_line_height_m)
                    if b_metrics.oriented_depth_m is not None:
                        depth_post_vals.append(b_metrics.oriented_depth_m)
                    if b_metrics.lateral_width_m is not None:
                        width_post_vals.append(b_metrics.lateral_width_m)

        line_v = 0.0
        depth_delta = 0.0
        width_delta = 0.0
        if len(line_h_post_vals) >= 2:
            dt = max(1e-3, (post_snaps[-1].timestamp - post_snaps[0].timestamp))
            line_v = float((line_h_post_vals[-1] - line_h_post_vals[0]) / dt)
            depth_delta = float(depth_post_vals[-1] - depth_post_vals[0]) if len(depth_post_vals) >= 2 else 0.0
            width_delta = float(width_post_vals[-1] - width_post_vals[0]) if len(width_post_vals) >= 2 else 0.0

        # Attacking Progression of Gaining Team (ball delta x in attacking direction)
        ball_progression = 0.0
        if len(post_snaps) >= 2 and post_snaps[0].ball_pos is not None and post_snaps[-1].ball_pos is not None:
            bx0, by0 = post_snaps[0].ball_pos
            bx1, by1 = post_snaps[-1].ball_pos
            # Check attacking direction of gaining team
            gain_team_att_dir = 1.0  # Default left-to-right (+X)
            if post_snaps[0].oriented_state is not None:
                team_lines = post_snaps[0].oriented_state.team_0 if evt.gaining_team == "TEAM_0" else post_snaps[0].oriented_state.team_1
                if team_lines and hasattr(team_lines, "attack_direction"):
                    ad = team_lines.attack_direction
                    ad_val = int(ad.value) if hasattr(ad, "value") else int(ad or 1)
                    if ad_val in (1, -1):
                        gain_team_att_dir = float(ad_val)

            ball_progression = float((bx1 - bx0) * gain_team_att_dir)

        # Build feature vector
        fv = TransitionFeatureVector(
            possession_change_confidence=evt.features.possession_change_confidence,
            pressure_pre_mean=p_pre_mean,
            pressure_post_mean=p_post_mean,
            pressure_delta=p_delta,
            nearest_defender_pre=d_pre_mean,
            nearest_defender_post=d_post_mean,
            nearest_distance_delta=d_delta,
            closing_speed_post_mean=cs_mean,
            max_closing_speed_post=cs_max,
            density_r3_post=r3_post,
            density_r5_post=r5_post,
            coverage_ratio_post=cov_post,
            centroid_ball_distance_delta=c_delta,
            defensive_line_velocity=line_v,
            team_depth_delta=depth_delta,
            team_width_delta=width_delta,
            ball_delta_x_attack=ball_progression,
        )

        # Compute monotonic scores
        cp_score, rec_score, candidate = self.scorer.compute_scores(fv)

        # Attacking response classification
        if ball_progression >= self.config.fast_attack_progression_m:
            att_resp = AttackingResponse.FAST_ATTACK
        elif ball_progression <= self.config.slow_buildup_progression_m:
            att_resp = AttackingResponse.SLOW_BUILDUP
        else:
            att_resp = AttackingResponse.AMBIGUOUS

        # Update event
        evt.features = fv
        evt.counterpress_score = cp_score
        evt.recovery_score = rec_score
        evt.candidate_label = candidate
        evt.attacking_response = att_resp
        evt.is_confirmed = True
        evt.confirmation_frame_index = current_frame_index
