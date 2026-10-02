"""Ball Control, Team Possession & Possession Changes Engine (EXP-18 / Chapter 7).

Infers:
1. Player-level ball control candidates and scores from fused multi-evidence signals
   (normalized image-space proximity, footpoint distance, ground-plane metric proximity,
   aerial ball discount, ball tracking state, and team attribution confidence).
2. Ambiguity resolution: distinguishes clear control from contested duels and free balls.
3. Causal team possession state machine with temporal control hysteresis and provisional
   free-ball transit grace windows.
4. Confirmed possession changes (turnovers) with causal confirmation delays, resistant
   to tracker ID switches, aerial balls, and 1-frame proximity noise.
"""

from __future__ import annotations

import logging
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
except ImportError:
    from backend.app.video_analysis.pitch_calibration import PitchDimensions
    from backend.app.video_analysis.metric_trajectories import (
        PlayerMetricObservation,
        BallMetricObservation,
    )

logger = logging.getLogger(__name__)


# ==============================================================================
# ENUMS & DATA STRUCTURES
# ==============================================================================

class BallControlState(str, Enum):
    """Micro-state describing immediate physical interaction with the ball."""

    CONTROLLED = "CONTROLLED"  # A single player has established physical control
    CONTESTED = "CONTESTED"    # Opposing players are actively challenging / dueling
    FREE_BALL = "FREE_BALL"    # Ball is loose, cleared, in flight, or in pass transit
    UNKNOWN = "UNKNOWN"        # Ball is not observed, occluded, or unresolvable


class TeamPossessionState(str, Enum):
    """Team currently holding tactical possession of the ball."""

    TEAM_0 = "TEAM_0"
    TEAM_1 = "TEAM_1"
    CONTESTED = "CONTESTED"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"


class PossessionStatus(str, Enum):
    """Confidence regime of the team possession state."""

    SECURE = "SECURE"                            # Confirmed player control established
    PROVISIONAL_TRANSIT = "PROVISIONAL_TRANSIT"  # Same-team pass transit / short free ball
    CONTESTED = "CONTESTED"                      # 50/50 challenge or duel
    NEUTRAL = "NEUTRAL"                          # Extended loose ball with no team in control
    UNKNOWN = "UNKNOWN"                          # Ball lost or occluded beyond grace period


@dataclass
class PlayerControlCandidate:
    """Individual player's proximity and control evidence relative to the ball."""

    track_id: int
    team_label: str
    team_confidence: float
    control_score: float                     # Normalized control score in [0.0, 1.0]
    image_distance_px: float
    normalized_image_distance: float         # Distance divided by player bbox height
    footpoint_distance_px: float
    normalized_footpoint_distance: float
    metric_distance_m: Optional[float] = None
    relative_velocity_ms: Optional[float] = None
    is_inside_bbox: bool = False
    gt_tracklet_id: Optional[int] = None


@dataclass
class BallControlEvaluation:
    """Frame-level evaluation of ball control across all nearby players."""

    state: BallControlState
    primary_candidate: Optional[PlayerControlCandidate] = None
    secondary_candidate: Optional[PlayerControlCandidate] = None
    score_margin: float = 0.0                # primary_score - secondary_score
    confidence: float = 0.0
    is_aerial_suspect: bool = False
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PossessionChangeEvent:
    """Confirmed possession turnover event between opposing teams."""

    frame_index: int
    timestamp: float
    from_team: str
    to_team: str
    from_player_track_id: Optional[int] = None
    to_player_track_id: Optional[int] = None
    confirmation_delay_frames: int = 5
    confidence: float = 0.80


@dataclass
class TeamPossessionFrameState:
    """Comprehensive frame-level possession state output."""

    frame_index: int
    timestamp: float
    possession_team: str                     # "TEAM_0", "TEAM_1", "CONTESTED", "NEUTRAL", "UNKNOWN"
    possession_status: PossessionStatus      # SECURE, PROVISIONAL_TRANSIT, CONTESTED, NEUTRAL, UNKNOWN
    possession_confidence: float             # [0.0, 1.0]
    controlling_player_id: Optional[int] = None
    controlling_player_team: Optional[str] = None
    control_state: BallControlState = BallControlState.UNKNOWN
    free_ball_age_frames: int = 0
    occlusion_age_frames: int = 0
    last_confirmed_team: Optional[str] = None
    last_confirmed_player_id: Optional[int] = None
    recent_possession_change: Optional[PossessionChangeEvent] = None
    is_valid: bool = True
    invalidation_reason: Optional[str] = None
    controlling_player_gt_id: Optional[int] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PossessionConfig:
    """Tunable thresholds and parameters for ball control and team possession."""

    pitch_dimensions: PitchDimensions = field(default_factory=PitchDimensions)

    # Image-space control thresholds (normalized by player bbox height)
    max_norm_dist_control: float = 0.70      # Maximum normalized distance to consider control
    max_norm_footpoint_control: float = 0.55 # Maximum normalized footpoint distance
    footpoint_weight: float = 0.40
    bbox_weight: float = 0.30
    metric_weight: float = 0.30

    # Metric control thresholds (ground plane Z=0)
    metric_max_dist_control_m: float = 2.50  # Max metric distance for ground control (meters)
    metric_close_dist_m: float = 1.20       # High-confidence metric proximity (meters)
    aerial_ground_jump_speed_ms: float = 25.0 # Suspect aerial ball if ground projection speed exceeds this

    # Candidate scoring & contested thresholds
    min_control_score_threshold: float = 0.28 # Minimum score to declare player control vs free ball
    contested_score_margin: float = 0.15      # If top opposing candidates differ by less, state is CONTESTED
    min_contested_candidate_score: float = 0.22

    # Hysteresis & temporal confirmation
    player_control_confirm_frames: int = 3   # Consecutive frames to confirm a new carrier
    team_possession_confirm_frames: int = 5  # Consecutive frames of opposing control to confirm turnover
    free_ball_grace_frames: int = 15         # Frames (~0.6s) provisional possession remains with kicking team
    max_ball_occlusion_frames: int = 12      # Frames (~0.48s) before missing ball transitions to UNKNOWN
    min_team_label_confidence: float = 0.45  # Gating threshold for team label attribution


# ==============================================================================
# BALL CONTROL ESTIMATOR
# ==============================================================================

class BallControlEstimator:
    """Extracts, normalizes, and fuses multi-evidence signals for player ball control."""

    def __init__(self, config: Optional[PossessionConfig] = None) -> None:
        self.config = config or PossessionConfig()
        self.prev_ball_metric_pos: Optional[Tuple[float, float, float]] = None

    def evaluate(
        self,
        player_observations: Sequence[Union[PlayerMetricObservation, Dict[str, Any]]],
        ball_observation: Optional[Union[BallMetricObservation, Dict[str, Any]]],
        calibration_valid: bool = True,
    ) -> BallControlEvaluation:
        """Evaluates ball control across all visible players for a single frame."""
        # 1. Check ball availability and validity
        if ball_observation is None:
            return BallControlEvaluation(
                state=BallControlState.UNKNOWN,
                details={"reason": "NO_BALL_OBSERVATION"},
            )

        ball_bbox, ball_metric, ball_conf, ball_state_str = self._extract_ball_data(ball_observation)
        if ball_bbox is None:
            return BallControlEvaluation(
                state=BallControlState.UNKNOWN,
                details={"reason": "NO_BALL_BBOX"},
            )

        # Check for stale or invalid tracker state
        if ball_state_str in ("LOST", "INVALID", "OUT_OF_BOUNDS") or ball_conf < 0.15:
            return BallControlEvaluation(
                state=BallControlState.UNKNOWN,
                details={"reason": f"BALL_TRACKER_UNRELIABLE_{ball_state_str}"},
            )

        ball_center_u = (ball_bbox[0] + ball_bbox[2]) / 2.0
        ball_center_v = (ball_bbox[1] + ball_bbox[3]) / 2.0

        # 2. Check for aerial ball suspicion (ground plane jump)
        is_aerial = False
        if ball_metric is not None and self.prev_ball_metric_pos is not None:
            bx, by, b_time = ball_metric
            pbx, pby, p_time = self.prev_ball_metric_pos
            dt = max(1e-3, b_time - p_time)
            dist_jump = np.hypot(bx - pbx, by - pby)
            speed = dist_jump / dt
            if speed > self.config.aerial_ground_jump_speed_ms:
                is_aerial = True

        if ball_metric is not None:
            self.prev_ball_metric_pos = ball_metric

        # 3. Score all player candidates
        candidates: List[PlayerControlCandidate] = []
        for p in player_observations:
            cand = self._score_player(p, ball_center_u, ball_center_v, ball_metric, ball_conf, is_aerial, calibration_valid)
            if cand is not None:
                candidates.append(cand)

        # Sort candidates descending by control score
        candidates.sort(key=lambda c: c.control_score, reverse=True)

        if not candidates or candidates[0].control_score < self.config.min_control_score_threshold:
            return BallControlEvaluation(
                state=BallControlState.FREE_BALL,
                primary_candidate=candidates[0] if candidates else None,
                confidence=float(1.0 - (candidates[0].control_score if candidates else 0.0)),
                is_aerial_suspect=is_aerial,
                details={"candidates_evaluated": len(candidates)},
            )

        primary = candidates[0]
        secondary = candidates[1] if len(candidates) > 1 else None
        score_margin = float(primary.control_score - (secondary.control_score if secondary else 0.0))

        # 4. Check for contested duel between opposing teams
        if (
            secondary is not None
            and secondary.team_label != primary.team_label
            and secondary.team_label not in ("UNKNOWN", "")
            and primary.team_label not in ("UNKNOWN", "")
            and score_margin < self.config.contested_score_margin
            and secondary.control_score >= self.config.min_contested_candidate_score
        ):
            return BallControlEvaluation(
                state=BallControlState.CONTESTED,
                primary_candidate=primary,
                secondary_candidate=secondary,
                score_margin=score_margin,
                confidence=float(np.mean([primary.control_score, secondary.control_score])),
                is_aerial_suspect=is_aerial,
                details={"contesting_teams": [primary.team_label, secondary.team_label]},
            )

        # 5. Clear player control
        return BallControlEvaluation(
            state=BallControlState.CONTROLLED,
            primary_candidate=primary,
            secondary_candidate=secondary,
            score_margin=score_margin,
            confidence=primary.control_score,
            is_aerial_suspect=is_aerial,
            details={"controlling_player": primary.track_id, "team": primary.team_label},
        )

    def _score_player(
        self,
        player_obs: Union[PlayerMetricObservation, Dict[str, Any]],
        ball_u: float,
        ball_v: float,
        ball_metric: Optional[Tuple[float, float, float]],
        ball_conf: float,
        is_aerial: bool,
        calibration_valid: bool,
    ) -> Optional[PlayerControlCandidate]:
        """Calculates normalized control evidence score for a single player."""
        if isinstance(player_obs, dict):
            tid = int(player_obs.get("track_id", -1))
            bbox = player_obs.get("bbox")
            t_label = player_obs.get("team_label", "UNKNOWN")
            t_conf = float(player_obs.get("team_confidence", 1.0))
            role = str(player_obs.get("role", "OUTFIELD_PLAYER")).upper()
            px = player_obs.get("smoothed_x_m") if player_obs.get("smoothed_x_m") is not None else player_obs.get("pitch_x_m")
            py = player_obs.get("smoothed_y_m") if player_obs.get("smoothed_y_m") is not None else player_obs.get("pitch_y_m")
            gt_tid = player_obs.get("gt_tracklet_id")
        else:
            tid = player_obs.track_id
            bbox = getattr(player_obs, "bbox", None)
            if bbox is None and hasattr(player_obs, "image_anchor_px") and player_obs.image_anchor_px is not None:
                u, v = player_obs.image_anchor_px
                bbox = [float(u) - 15.0, float(v) - 90.0, float(u) + 15.0, float(v)]
            t_label = player_obs.team_label or "UNKNOWN"
            t_conf = float(getattr(player_obs, "team_confidence", 1.0))
            role = str(player_obs.role or "OUTFIELD_PLAYER").upper()
            px = player_obs.smoothed_x_m if player_obs.smoothed_x_m is not None else player_obs.pitch_x_m
            py = player_obs.smoothed_y_m if player_obs.smoothed_y_m is not None else player_obs.pitch_y_m
            gt_tid = getattr(player_obs, "gt_tracklet_id", None)

        # Referees do not possess or control the ball
        if "REFEREE" in role:
            return None

        if bbox is None or len(bbox) < 4:
            return None

        u1, v1, u2, v2 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
        h_px = max(10.0, v2 - v1)

        # A. Footpoint distance
        foot_u = (u1 + u2) / 2.0
        foot_v = v2
        d_foot_px = float(np.hypot(ball_u - foot_u, ball_v - foot_v))
        norm_foot = d_foot_px / h_px

        # B. Bbox proximity / containment
        is_inside = (u1 <= ball_u <= u2) and (v1 <= ball_v <= v2)
        if is_inside:
            d_bbox_px = 0.0
        else:
            du = max(0.0, max(u1 - ball_u, ball_u - u2))
            dv = max(0.0, max(v1 - ball_v, ball_v - v2))
            d_bbox_px = float(np.hypot(du, dv))
        norm_bbox = d_bbox_px / h_px

        # Proximity scores in [0.0, 1.0]
        s_foot = max(0.0, 1.0 - norm_foot / self.config.max_norm_footpoint_control)
        s_bbox = 1.0 if is_inside else max(0.0, 1.0 - norm_bbox / 0.50)

        # C. Metric ground distance (when calibrated and available)
        d_metric = None
        s_metric = 0.0
        if calibration_valid and not is_aerial and ball_metric is not None and px is not None and py is not None:
            bx, by, _ = ball_metric
            d_metric = float(np.hypot(px - bx, py - by))
            s_metric = max(0.0, 1.0 - d_metric / self.config.metric_max_dist_control_m)
        else:
            # If metric is unavailable or aerial suspect, redistribute metric weight to image signals
            s_metric = (s_foot + s_bbox) / 2.0

        # Weighted combination
        raw_score = (
            self.config.footpoint_weight * s_foot
            + self.config.bbox_weight * s_bbox
            + self.config.metric_weight * s_metric
        )

        # Scale by ball confidence and team confidence
        gated_score = float(raw_score * min(1.0, ball_conf * 1.5) * max(0.2, t_conf))

        norm_img = float(np.hypot(ball_u - (u1 + u2) / 2.0, ball_v - (v1 + v2) / 2.0) / h_px)

        return PlayerControlCandidate(
            track_id=tid,
            team_label=t_label,
            team_confidence=t_conf,
            control_score=gated_score,
            image_distance_px=d_bbox_px,
            normalized_image_distance=norm_img,
            footpoint_distance_px=d_foot_px,
            normalized_footpoint_distance=norm_foot,
            metric_distance_m=d_metric,
            is_inside_bbox=is_inside,
            gt_tracklet_id=gt_tid,
        )

    def _extract_ball_data(
        self,
        ball_obs: Union[BallMetricObservation, Dict[str, Any]],
    ) -> Tuple[Optional[List[float]], Optional[Tuple[float, float, float]], float, str]:
        """Extracts bounding box, metric coordinates, confidence, and state from ball observation."""
        if isinstance(ball_obs, dict):
            bbox = ball_obs.get("bbox")
            x = ball_obs.get("pitch_x_m") or ball_obs.get("x")
            y = ball_obs.get("pitch_y_m") or ball_obs.get("y")
            timestamp = float(ball_obs.get("timestamp", 0.0) or 0.0)
            raw_c = ball_obs.get("confidence")
            conf = float(raw_c) if raw_c is not None else 1.0
            state_str = str(ball_obs.get("state", "DETECTED")).upper()
        else:
            bbox = list(ball_obs.bbox) if hasattr(ball_obs, "bbox") and ball_obs.bbox is not None else None
            if bbox is None and hasattr(ball_obs, "image_anchor_px") and ball_obs.image_anchor_px is not None:
                u, v = ball_obs.image_anchor_px
                if u is not None and v is not None and (u != 0.0 or v != 0.0):
                    bbox = [float(u) - 6.0, float(v) - 6.0, float(u) + 6.0, float(v) + 6.0]
            x = ball_obs.pitch_x_m
            y = ball_obs.pitch_y_m
            timestamp = getattr(ball_obs, "timestamp", 0.0) or 0.0
            raw_c = getattr(ball_obs, "confidence", 1.0)
            conf = float(raw_c) if raw_c is not None else 1.0
            state_str = "DETECTED" if getattr(ball_obs, "position_valid", True) else "UNCERTAIN"

        metric_data = None
        if x is not None and y is not None:
            metric_data = (float(x), float(y), timestamp)

        return bbox, metric_data, conf, state_str


# ==============================================================================
# TEAM POSSESSION STATE MACHINE
# ==============================================================================

class TeamPossessionStateMachine:
    """Maintains causal team possession states, temporal hysteresis, and turnover events."""

    def __init__(self, config: Optional[PossessionConfig] = None) -> None:
        self.config = config or PossessionConfig()

        # State tracking
        self.current_team: str = "UNKNOWN"
        self.current_status: PossessionStatus = PossessionStatus.UNKNOWN
        self.current_confidence: float = 0.0

        # Player control persistence
        self.active_player_id: Optional[int] = None
        self.active_player_team: Optional[str] = None
        self.player_control_counter: int = 0

        # Last confirmed secure state
        self.last_confirmed_team: Optional[str] = None
        self.last_confirmed_player_id: Optional[int] = None

        # Temporal counters
        self.free_ball_age_frames: int = 0
        self.occlusion_age_frames: int = 0
        self.opposing_control_candidate: Optional[str] = None
        self.opposing_control_counter: int = 0

    def reset(self) -> None:
        """Resets all internal possession and turnover state buffers."""
        self.current_team = "UNKNOWN"
        self.current_status = PossessionStatus.UNKNOWN
        self.current_confidence = 0.0
        self.active_player_id = None
        self.active_player_team = None
        self.player_control_counter = 0
        self.last_confirmed_team = None
        self.last_confirmed_player_id = None
        self.free_ball_age_frames = 0
        self.occlusion_age_frames = 0
        self.opposing_control_candidate = None
        self.opposing_control_counter = 0

    def update(
        self,
        frame_index: int,
        timestamp: float,
        control_eval: BallControlEvaluation,
    ) -> Tuple[TeamPossessionFrameState, Optional[PossessionChangeEvent]]:
        """Processes frame control evaluation into causal team possession state."""
        possession_change_event: Optional[PossessionChangeEvent] = None

        # Case 1: Ball is completely missing / occluded
        if control_eval.state == BallControlState.UNKNOWN:
            self.occlusion_age_frames += 1
            if self.occlusion_age_frames <= self.config.max_ball_occlusion_frames and self.last_confirmed_team is not None:
                # Provisional hold with decaying confidence
                decay = max(0.2, 1.0 - (self.occlusion_age_frames / self.config.max_ball_occlusion_frames) * 0.7)
                frame_state = TeamPossessionFrameState(
                    frame_index=frame_index,
                    timestamp=timestamp,
                    possession_team=self.last_confirmed_team,
                    possession_status=PossessionStatus.PROVISIONAL_TRANSIT,
                    possession_confidence=float(self.current_confidence * decay),
                    controlling_player_id=None,
                    controlling_player_team=self.last_confirmed_team,
                    control_state=BallControlState.UNKNOWN,
                    free_ball_age_frames=self.free_ball_age_frames,
                    occlusion_age_frames=self.occlusion_age_frames,
                    last_confirmed_team=self.last_confirmed_team,
                    last_confirmed_player_id=self.last_confirmed_player_id,
                )
                return frame_state, None
            else:
                self.current_team = "UNKNOWN"
                self.current_status = PossessionStatus.UNKNOWN
                self.current_confidence = 0.0
                frame_state = TeamPossessionFrameState(
                    frame_index=frame_index,
                    timestamp=timestamp,
                    possession_team="UNKNOWN",
                    possession_status=PossessionStatus.UNKNOWN,
                    possession_confidence=0.0,
                    controlling_player_id=None,
                    controlling_player_team=None,
                    control_state=BallControlState.UNKNOWN,
                    free_ball_age_frames=self.free_ball_age_frames,
                    occlusion_age_frames=self.occlusion_age_frames,
                    last_confirmed_team=self.last_confirmed_team,
                    last_confirmed_player_id=self.last_confirmed_player_id,
                )
                return frame_state, None

        # Reset occlusion age since ball is observed
        self.occlusion_age_frames = 0

        # Case 2: Contested duel between opposing players
        if control_eval.state == BallControlState.CONTESTED:
            self.current_team = "CONTESTED"
            self.current_status = PossessionStatus.CONTESTED
            self.current_confidence = control_eval.confidence
            self.opposing_control_counter = 0
            self.opposing_control_candidate = None

            frame_state = TeamPossessionFrameState(
                frame_index=frame_index,
                timestamp=timestamp,
                possession_team="CONTESTED",
                possession_status=PossessionStatus.CONTESTED,
                possession_confidence=control_eval.confidence,
                controlling_player_id=control_eval.primary_candidate.track_id if control_eval.primary_candidate else None,
                controlling_player_team="CONTESTED",
                control_state=BallControlState.CONTESTED,
                free_ball_age_frames=0,
                occlusion_age_frames=0,
                last_confirmed_team=self.last_confirmed_team,
                last_confirmed_player_id=self.last_confirmed_player_id,
            )
            return frame_state, None

        # Case 3: Free ball (transit, pass, clearance, loose ball)
        if control_eval.state == BallControlState.FREE_BALL:
            self.free_ball_age_frames += 1
            self.opposing_control_counter = 0
            self.opposing_control_candidate = None

            # Grace window: possession remains provisionally with the kicking team
            if self.free_ball_age_frames <= self.config.free_ball_grace_frames and self.last_confirmed_team is not None:
                decay = max(0.3, 1.0 - (self.free_ball_age_frames / self.config.free_ball_grace_frames) * 0.6)
                self.current_team = self.last_confirmed_team
                self.current_status = PossessionStatus.PROVISIONAL_TRANSIT
                self.current_confidence = float(self.current_confidence * decay)
            else:
                self.current_team = "NEUTRAL"
                self.current_status = PossessionStatus.NEUTRAL
                self.current_confidence = 0.0

            frame_state = TeamPossessionFrameState(
                frame_index=frame_index,
                timestamp=timestamp,
                possession_team=self.current_team,
                possession_status=self.current_status,
                possession_confidence=self.current_confidence,
                controlling_player_id=None,
                controlling_player_team=None,
                control_state=BallControlState.FREE_BALL,
                free_ball_age_frames=self.free_ball_age_frames,
                occlusion_age_frames=0,
                last_confirmed_team=self.last_confirmed_team,
                last_confirmed_player_id=self.last_confirmed_player_id,
            )
            return frame_state, None

        # Case 4: Single player clear control
        primary = control_eval.primary_candidate
        assert primary is not None
        self.free_ball_age_frames = 0

        # Check team label confidence
        if primary.team_confidence < self.config.min_team_label_confidence or primary.team_label in ("UNKNOWN", ""):
            # Player is near ball, but team identity is uncertain
            frame_state = TeamPossessionFrameState(
                frame_index=frame_index,
                timestamp=timestamp,
                possession_team="UNKNOWN",
                possession_status=PossessionStatus.UNKNOWN,
                possession_confidence=0.30,
                controlling_player_id=primary.track_id,
                controlling_player_team="UNKNOWN",
                control_state=BallControlState.CONTROLLED,
                free_ball_age_frames=0,
                occlusion_age_frames=0,
                last_confirmed_team=self.last_confirmed_team,
                last_confirmed_player_id=self.last_confirmed_player_id,
                invalidation_reason="LOW_TEAM_LABEL_CONFIDENCE",
            )
            return frame_state, None

        # A. Player Control Hysteresis
        if primary.track_id == self.active_player_id:
            self.player_control_counter += 1
        elif primary.team_label == self.active_player_team:
            # Same team, different track ID (handoff or ID switch)
            self.active_player_id = primary.track_id
            self.player_control_counter = min(self.player_control_counter + 1, self.config.player_control_confirm_frames)
        else:
            # New player from different team
            self.active_player_id = primary.track_id
            self.active_player_team = primary.team_label
            self.player_control_counter = 1

        is_player_control_confirmed = (self.player_control_counter >= self.config.player_control_confirm_frames)

        # B. Team Possession & Turnover Hysteresis
        cand_team = primary.team_label

        if self.last_confirmed_team is None:
            # Initial possession acquisition
            if is_player_control_confirmed:
                self.current_team = cand_team
                self.current_status = PossessionStatus.SECURE
                self.current_confidence = primary.control_score
                self.last_confirmed_team = cand_team
                self.last_confirmed_player_id = primary.track_id
        elif cand_team == self.last_confirmed_team:
            # Continuation of same-team possession (or same-team pass reception)
            self.current_team = cand_team
            self.current_status = PossessionStatus.SECURE
            self.current_confidence = primary.control_score
            self.last_confirmed_player_id = primary.track_id
            self.opposing_control_counter = 0
            self.opposing_control_candidate = None
        else:
            # Opposing team candidate (possible turnover)
            if self.opposing_control_candidate == cand_team:
                self.opposing_control_counter += 1
            else:
                self.opposing_control_candidate = cand_team
                self.opposing_control_counter = 1

            if self.opposing_control_counter >= self.config.team_possession_confirm_frames and is_player_control_confirmed:
                # Confirmed possession change!
                possession_change_event = PossessionChangeEvent(
                    frame_index=frame_index,
                    timestamp=timestamp,
                    from_team=self.last_confirmed_team,
                    to_team=cand_team,
                    from_player_track_id=self.last_confirmed_player_id,
                    to_player_track_id=primary.track_id,
                    confirmation_delay_frames=self.opposing_control_counter,
                    confidence=float(primary.control_score * 0.90),
                )
                logger.info(
                    "Possession turnover at frame %d: %s -> %s (confirmed in %d frames)",
                    frame_index, self.last_confirmed_team, cand_team, self.opposing_control_counter
                )
                self.current_team = cand_team
                self.current_status = PossessionStatus.SECURE
                self.current_confidence = primary.control_score
                self.last_confirmed_team = cand_team
                self.last_confirmed_player_id = primary.track_id
                self.opposing_control_counter = 0
                self.opposing_control_candidate = None
            else:
                # Turnover pending confirmation: hold previous team or emit contested/provisional
                self.current_team = self.last_confirmed_team
                self.current_status = PossessionStatus.PROVISIONAL_TRANSIT
                self.current_confidence = float(self.current_confidence * 0.70)

        frame_state = TeamPossessionFrameState(
            frame_index=frame_index,
            timestamp=timestamp,
            possession_team=self.current_team,
            possession_status=self.current_status,
            possession_confidence=self.current_confidence,
            controlling_player_id=primary.track_id if is_player_control_confirmed else None,
            controlling_player_team=primary.team_label if is_player_control_confirmed else None,
            control_state=BallControlState.CONTROLLED,
            free_ball_age_frames=0,
            occlusion_age_frames=0,
            last_confirmed_team=self.last_confirmed_team,
            last_confirmed_player_id=self.last_confirmed_player_id,
            recent_possession_change=possession_change_event,
            controlling_player_gt_id=primary.gt_tracklet_id if (is_player_control_confirmed and primary.gt_tracklet_id is not None) else None,
            details={"controlling_player_gt_id": primary.gt_tracklet_id} if (is_player_control_confirmed and primary.gt_tracklet_id is not None) else {},
        )
        return frame_state, possession_change_event


# ==============================================================================
# UNIFIED POSSESSION ENGINE
# ==============================================================================

class PossessionEngine:
    """High-level coordinator orchestrating ball control scoring and team possession state."""

    def __init__(self, config: Optional[PossessionConfig] = None) -> None:
        self.config = config or PossessionConfig()
        self.control_estimator = BallControlEstimator(config=self.config)
        self.state_machine = TeamPossessionStateMachine(config=self.config)
        self.frames_history: List[TeamPossessionFrameState] = []
        self.turnover_events: List[PossessionChangeEvent] = []

    def reset(self) -> None:
        """Resets all estimators, state machines, and historical records."""
        self.control_estimator = BallControlEstimator(config=self.config)
        self.state_machine.reset()
        self.frames_history.clear()
        self.turnover_events.clear()

    def process_frame(
        self,
        frame_index: int,
        timestamp: float,
        player_observations: Sequence[Union[PlayerMetricObservation, Dict[str, Any]]],
        ball_observation: Optional[Union[BallMetricObservation, Dict[str, Any]]],
        calibration_valid: bool = True,
    ) -> TeamPossessionFrameState:
        """Processes a single frame into ball control and team possession state."""
        # 1. Evaluate Player-Level Control Evidence
        control_eval = self.control_estimator.evaluate(
            player_observations=player_observations,
            ball_observation=ball_observation,
            calibration_valid=calibration_valid,
        )

        # 2. Update Team Possession State Machine
        frame_state, turnover = self.state_machine.update(
            frame_index=frame_index,
            timestamp=timestamp,
            control_eval=control_eval,
        )

        if turnover is not None:
            self.turnover_events.append(turnover)

        self.frames_history.append(frame_state)
        return frame_state

    def export_to_jsonl(self, output_path: Union[str, Path], sequence_id: str = "") -> int:
        """Exports possession time-series records to JSONL."""
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        import json

        count = 0
        with open(out_p, "w") as f:
            for frame in self.frames_history:
                rec = asdict(frame)
                rec["sequence_id"] = sequence_id
                rec["possession_status"] = frame.possession_status.value
                rec["control_state"] = frame.control_state.value
                if frame.recent_possession_change is not None:
                    rec["recent_possession_change"] = asdict(frame.recent_possession_change)
                f.write(json.dumps(rec) + "\n")
                count += 1

        logger.info("Exported %d possession frame records to %s", count, out_p)
        return count
