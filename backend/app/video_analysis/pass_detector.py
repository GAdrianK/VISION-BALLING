"""
Chapter 7: Pass Detection & Ball Event Trajectories (EXP-19).
Downstream consumer of EXP-18 (Possession Engine) and EXP-17 (Attacking Direction).

Detects causal ball-transfer events:
  - PASS_COMPLETED
  - PASS_INTERCEPTED
  - BALL_RELEASE_UNRESOLVED
  - CLEARANCE_CANDIDATE
  - PENDING_TRANSFER

Physical Trajectory Guarantees:
  - Dual representation: 2D image coordinates (u, v) and ground-plane projection (x, y, Z=0).
  - Explicit aerial gating: when ground-plane speed jump > 25.0 m/s or pitch uncalibrated,
    sets aerial_suspected=True, trajectory_ground_valid=False.
  - ZERO claim of 3D ball trajectory reconstruction.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

from app.video_analysis.metric_trajectories import (
    BallMetricObservation,
    PlayerMetricObservation,
)
from app.video_analysis.pitch_calibration import PitchDimensions
from app.video_analysis.possession import (
    BallControlEvaluation,
    BallControlState,
    PossessionStatus,
    TeamPossessionFrameState,
)
from app.video_analysis.tactical_lines import AttackDirection

logger = logging.getLogger(__name__)


# ==============================================================================
# ENUMS & DATA STRUCTURES
# ==============================================================================

class PassEventType(str, Enum):
    """Classification of ball transfer / pass events."""

    PASS_COMPLETED = "PASS_COMPLETED"
    PASS_INTERCEPTED = "PASS_INTERCEPTED"
    BALL_RELEASE_UNRESOLVED = "BALL_RELEASE_UNRESOLVED"
    CLEARANCE_CANDIDATE = "CLEARANCE_CANDIDATE"
    PENDING_TRANSFER = "PENDING_TRANSFER"
    AMBIGUOUS = "AMBIGUOUS"


class PassCandidateState(str, Enum):
    """Lifecycle state of an active in-flight transfer candidate."""

    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    INTERCEPTED = "INTERCEPTED"
    UNRESOLVED = "UNRESOLVED"
    CANCELLED = "CANCELLED"


@dataclass
class BallTransferTrajectory:
    """Causal trajectory record for ball transfer flight."""

    timestamps: List[float] = field(default_factory=list)
    image_positions_px: List[Tuple[float, float]] = field(default_factory=list)
    metric_positions_m: List[Tuple[float, float]] = field(default_factory=list)
    trajectory_ground_valid: bool = True
    aerial_suspected: bool = False
    flight_duration_s: float = 0.0
    image_path_length_px: float = 0.0
    ground_projected_path_length_m: Optional[float] = None
    net_ground_displacement_m: Optional[float] = None
    mean_image_speed_px_s: float = 0.0
    mean_ground_projected_speed_ms: Optional[float] = None


@dataclass
class PassEvent:
    """Finalized ball transfer / pass event record."""

    event_id: str
    sequence_id: str
    event_type: PassEventType
    sender_track_id: int
    sender_team: str
    sender_gt_tracklet_id: Optional[int] = None

    release_frame: int = 0
    release_timestamp: float = 0.0
    release_position_image: Tuple[float, float] = (0.0, 0.0)
    release_position_pitch: Optional[Tuple[float, float]] = None
    release_confidence: float = 1.0

    receiver_track_id: Optional[int] = None
    receiver_team: Optional[str] = None
    receiver_gt_tracklet_id: Optional[int] = None

    reception_frame: Optional[int] = None
    reception_timestamp: Optional[float] = None
    reception_position_image: Optional[Tuple[float, float]] = None
    reception_position_pitch: Optional[Tuple[float, float]] = None
    reception_confidence: Optional[float] = None

    trajectory: Optional[BallTransferTrajectory] = None
    pass_displacement_m: Optional[float] = None
    delta_x_attack: Optional[float] = None
    delta_y: Optional[float] = None
    forward_displacement_m: Optional[float] = None
    event_confidence: float = 0.0
    is_self_recontrol: bool = False
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PassDetectorConfig:
    """Configuration parameters for pass release, transit, and reception detection."""

    # Release detection thresholds
    min_release_ball_speed_px: float = 5.0
    min_release_carrier_dist_px: float = 38.0
    min_release_confidence: float = 0.30

    # Reception parameters
    reception_proximity_dist_px: float = 28.0
    reception_max_ball_speed_px_s: float = 200.0

    # Flight / Transit parameters
    min_transit_frames: int = 2               # Minimum flight frames before reception (~0.08s)
    max_transit_frames: int = 35              # Maximum flight frames before timeout (~1.40s)
    timeout_unresolved_frames: int = 35
    max_ball_lost_frames: int = 12            # Tolerance for missing ball before unresolving

    # Self-recontrol / Dribble rejection
    self_recontrol_max_displacement_m: float = 4.0
    self_recontrol_max_frames: int = 15

    # Clearance candidate thresholds
    clearance_min_speed_ms: float = 16.0
    clearance_min_displacement_m: float = 22.0

    # Physical / Gating thresholds
    aerial_ground_jump_speed_ms: float = 25.0 # Speed above which Z=0 projection is deemed aerial
    min_event_confidence_threshold: float = 0.35
    pitch_dimensions: PitchDimensions = field(default_factory=PitchDimensions)


@dataclass
class BallTransferCandidate:
    """Active in-flight ball transfer candidate state."""

    sender_track_id: int
    sender_team: str
    sender_gt_tracklet_id: Optional[int] = None
    release_frame: int = 0
    release_timestamp: float = 0.0
    release_pos_image: Tuple[float, float] = (0.0, 0.0)
    release_pos_pitch: Optional[Tuple[float, float]] = None
    release_confidence: float = 1.0

    trajectory: BallTransferTrajectory = field(default_factory=BallTransferTrajectory)
    frame_age: int = 0
    ball_lost_frames: int = 0
    is_active: bool = True
    prev_metric_pos: Optional[Tuple[float, float, float]] = None


@dataclass
class PassFrameState:
    """Frame-level diagnostic state from pass event detector."""

    frame_index: int
    timestamp: float
    active_state: PassEventType
    recent_finalized_event: Optional[PassEvent] = None
    active_candidate_sender_id: Optional[int] = None
    active_candidate_sender_team: Optional[str] = None
    flight_age_frames: int = 0
    is_aerial_suspected: bool = False


# ==============================================================================
# PASS EVENT DETECTOR
# ==============================================================================

class PassEventDetector:
    """Causal, stateful pass release, transit, and reception event detector."""

    def __init__(self, config: Optional[PassDetectorConfig] = None) -> None:
        self.config = config or PassDetectorConfig()
        self.active_candidate: Optional[BallTransferCandidate] = None
        self.finalized_events: List[PassEvent] = []
        self.event_counter: int = 0

        # Memory for release detection
        self.prev_controlling_player_id: Optional[int] = None
        self.prev_controlling_team: Optional[str] = None
        self.prev_controlling_gt_id: Optional[int] = None
        self.prev_carrier_pos_img: Optional[Tuple[float, float]] = None
        self.prev_carrier_pos_pitch: Optional[Tuple[float, float]] = None
        self.prev_carrier_confidence: float = 1.0
        self.prev_carrier_frame: Optional[int] = None
        self.last_finalized_frame: Optional[int] = None

        # Ball kinematic memory
        self.prev_ball_img_pos: Optional[Tuple[float, float, float]] = None
        self.prev_ball_metric_pos: Optional[Tuple[float, float, float]] = None

    def reset(self) -> None:
        """Resets detector state between sequences."""
        self.active_candidate = None
        self.finalized_events.clear()
        self.event_counter = 0

        self.prev_controlling_player_id = None
        self.prev_controlling_team = None
        self.prev_controlling_gt_id = None
        self.prev_carrier_pos_img = None
        self.prev_carrier_pos_pitch = None
        self.prev_carrier_confidence = 1.0
        self.prev_carrier_frame = None
        self.last_finalized_frame = None

        self.prev_ball_img_pos = None
        self.prev_ball_metric_pos = None

    def process_frame(
        self,
        frame_index: int,
        timestamp: float,
        player_observations: Sequence[Union[PlayerMetricObservation, Dict[str, Any]]],
        ball_observation: Optional[Union[BallMetricObservation, Dict[str, Any]]],
        possession_state: Optional[Union[TeamPossessionFrameState, Dict[str, Any]]],
        calibration_valid: bool = True,
        attack_directions: Optional[Dict[str, AttackDirection]] = None,
        sequence_id: str = "seq",
    ) -> PassFrameState:
        """Causally processes current frame and updates candidate / event states."""
        # 1. Parse Ball Data
        ball_u, ball_v, ball_metric, ball_conf = self._extract_ball_point(ball_observation)

        # Compute Ball Kinematics
        ball_speed_px = 0.0
        is_aerial_step = False
        if ball_u is not None and ball_v is not None:
            if self.prev_ball_img_pos is not None:
                pbu, pbv, pbt = self.prev_ball_img_pos
                dt = max(1e-3, timestamp - pbt)
                ball_speed_px = np.hypot(ball_u - pbu, ball_v - pbv) / dt
            self.prev_ball_img_pos = (ball_u, ball_v, timestamp)

        if ball_metric is not None:
            bx, by = ball_metric
            if self.prev_ball_metric_pos is not None:
                pbx, pby, pbt = self.prev_ball_metric_pos
                dt = max(1e-3, timestamp - pbt)
                metric_speed = np.hypot(bx - pbx, by - pby) / dt
                if metric_speed > self.config.aerial_ground_jump_speed_ms:
                    is_aerial_step = True
            self.prev_ball_metric_pos = (bx, by, timestamp)

        # 2. Parse Possession State
        curr_carrier_id, curr_carrier_team, curr_carrier_gt_id, poss_status = self._extract_possession_info(
            possession_state, player_observations
        )

        finalized_event: Optional[PassEvent] = None

        # 3. Active Candidate Transit Update
        if self.active_candidate is not None:
            cand = self.active_candidate
            cand.frame_age += 1

            if ball_u is not None and ball_v is not None:
                cand.trajectory.timestamps.append(timestamp)
                cand.trajectory.image_positions_px.append((ball_u, ball_v))
                cand.ball_lost_frames = 0

                if calibration_valid and not is_aerial_step and ball_metric is not None:
                    cand.trajectory.metric_positions_m.append(ball_metric)
                else:
                    if is_aerial_step:
                        cand.trajectory.aerial_suspected = True
                        cand.trajectory.trajectory_ground_valid = False
            else:
                cand.ball_lost_frames += 1

            # Check for Reception
            reception_detected, rec_p_id, rec_team, rec_gt_id, rec_pos_img, rec_pos_pitch, rec_conf = self._check_reception(
                cand=cand,
                curr_carrier_id=curr_carrier_id,
                curr_carrier_team=curr_carrier_team,
                curr_carrier_gt_id=curr_carrier_gt_id,
                player_observations=player_observations,
                ball_u=ball_u,
                ball_v=ball_v,
                ball_metric=ball_metric,
                poss_status=poss_status,
                ball_speed_px_s=ball_speed_px,
            )

            if reception_detected:
                finalized_event = self._finalize_reception_event(
                    cand=cand,
                    frame_index=frame_index,
                    timestamp=timestamp,
                    rec_p_id=rec_p_id,
                    rec_team=rec_team,
                    rec_gt_id=rec_gt_id,
                    rec_pos_img=rec_pos_img,
                    rec_pos_pitch=rec_pos_pitch,
                    rec_conf=rec_conf,
                    attack_directions=attack_directions,
                    sequence_id=sequence_id,
                )
                self.active_candidate = None
            elif cand.frame_age >= self.config.max_transit_frames or cand.ball_lost_frames >= self.config.max_ball_lost_frames:
                # Timeout or ball lost -> Unresolved / Clearance
                finalized_event = self._finalize_timeout_event(
                    cand=cand,
                    frame_index=frame_index,
                    timestamp=timestamp,
                    attack_directions=attack_directions,
                    sequence_id=sequence_id,
                )
                self.active_candidate = None

        # 4. Release Detection (if no candidate active and no event just finalized)
        if self.active_candidate is None and finalized_event is None:
            release_candidate = self._check_release(
                frame_index=frame_index,
                timestamp=timestamp,
                curr_carrier_id=curr_carrier_id,
                curr_carrier_team=curr_carrier_team,
                curr_carrier_gt_id=curr_carrier_gt_id,
                poss_status=poss_status,
                ball_u=ball_u,
                ball_v=ball_v,
                ball_metric=ball_metric,
                ball_speed_px=ball_speed_px,
                player_observations=player_observations,
            )
            if release_candidate is not None:
                self.active_candidate = release_candidate

        # 5. Update Carrier Memory
        if curr_carrier_id is not None and poss_status in (PossessionStatus.SECURE, "SECURE"):
            self.prev_controlling_player_id = curr_carrier_id
            self.prev_controlling_team = curr_carrier_team
            self.prev_controlling_gt_id = curr_carrier_gt_id
            self.prev_carrier_frame = frame_index
            # Find carrier position
            c_img, c_pitch = self._find_player_position(curr_carrier_id, player_observations)
            if c_img is not None:
                self.prev_carrier_pos_img = c_img
            if c_pitch is not None:
                self.prev_carrier_pos_pitch = c_pitch

        # 6. Build Frame State Output
        active_type = PassEventType.PENDING_TRANSFER if self.active_candidate is not None else PassEventType.AMBIGUOUS
        f_state = PassFrameState(
            frame_index=frame_index,
            timestamp=timestamp,
            active_state=active_type,
            recent_finalized_event=finalized_event,
            active_candidate_sender_id=self.active_candidate.sender_track_id if self.active_candidate else None,
            active_candidate_sender_team=self.active_candidate.sender_team if self.active_candidate else None,
            flight_age_frames=self.active_candidate.frame_age if self.active_candidate else 0,
            is_aerial_suspected=self.active_candidate.trajectory.aerial_suspected if self.active_candidate else False,
        )
        return f_state

    # --------------------------------------------------------------------------
    # INTERNAL LOGIC: RELEASE DETECTION
    # --------------------------------------------------------------------------

    def _check_release(
        self,
        frame_index: int,
        timestamp: float,
        curr_carrier_id: Optional[int],
        curr_carrier_team: Optional[str],
        curr_carrier_gt_id: Optional[int],
        poss_status: Optional[Union[PossessionStatus, str]],
        ball_u: Optional[float],
        ball_v: Optional[float],
        ball_metric: Optional[Tuple[float, float]],
        ball_speed_px: float,
        player_observations: Sequence[Union[PlayerMetricObservation, Dict[str, Any]]],
    ) -> Optional[BallTransferCandidate]:
        """Evaluates whether the ball was released from previous secure carrier."""
        if self.prev_controlling_player_id is None or self.prev_controlling_team in (None, "UNKNOWN"):
            return None

        # Cooldown right after an event finalized
        if self.last_finalized_frame is not None and (frame_index - self.last_finalized_frame < self.config.min_transit_frames):
            return None

        # Previous carrier must be recent (< 8 frames ago)
        if self.prev_carrier_frame is not None and (frame_index - self.prev_carrier_frame > 8):
            return None

        # Case A: Carrier is no longer controlling ball (ball is in transit, neutral, or unpossessed)
        carrier_departed = (curr_carrier_id != self.prev_controlling_player_id)
        status_transit = (poss_status in (PossessionStatus.PROVISIONAL_TRANSIT, PossessionStatus.NEUTRAL,
                                          "PROVISIONAL_TRANSIT", "NEUTRAL", PossessionStatus.UNKNOWN))

        if not (carrier_departed or status_transit):
            return None

        # Check distance between ball and previous carrier
        p_img_pos = self.prev_carrier_pos_img
        if p_img_pos is None:
            p_img_pos, _ = self._find_player_position(self.prev_controlling_player_id, player_observations)

        if p_img_pos is not None and ball_u is not None and ball_v is not None:
            dist_px = np.hypot(ball_u - p_img_pos[0], ball_v - p_img_pos[1])
            # Release requires either adequate physical separation or significant ball flight speed
            if dist_px < self.config.min_release_carrier_dist_px and ball_speed_px < self.config.min_release_ball_speed_px:
                return None

        # Construct Candidate
        rel_pos_img = self.prev_carrier_pos_img or ((float(ball_u), float(ball_v)) if (ball_u is not None and ball_v is not None) else (0.0, 0.0))
        rel_pos_pitch = self.prev_carrier_pos_pitch or ball_metric

        ball_img = (float(ball_u), float(ball_v)) if (ball_u is not None and ball_v is not None) else rel_pos_img
        traj = BallTransferTrajectory(
            timestamps=[timestamp],
            image_positions_px=[ball_img],
            metric_positions_m=[ball_metric] if ball_metric is not None else ([rel_pos_pitch] if rel_pos_pitch is not None else []),
            trajectory_ground_valid=(ball_metric is not None or rel_pos_pitch is not None),
        )

        candidate = BallTransferCandidate(
            sender_track_id=self.prev_controlling_player_id,
            sender_team=self.prev_controlling_team,
            sender_gt_tracklet_id=self.prev_controlling_gt_id,
            release_frame=frame_index,
            release_timestamp=timestamp,
            release_pos_image=rel_pos_img,
            release_pos_pitch=rel_pos_pitch,
            release_confidence=0.85,
            trajectory=traj,
            frame_age=1,
            prev_metric_pos=(ball_metric[0], ball_metric[1], timestamp) if ball_metric is not None else None,
        )
        return candidate

    # --------------------------------------------------------------------------
    # INTERNAL LOGIC: RECEPTION CHECK
    # --------------------------------------------------------------------------

    def _check_reception(
        self,
        cand: BallTransferCandidate,
        curr_carrier_id: Optional[int],
        curr_carrier_team: Optional[str],
        curr_carrier_gt_id: Optional[int],
        player_observations: Sequence[Union[PlayerMetricObservation, Dict[str, Any]]],
        ball_u: Optional[float],
        ball_v: Optional[float],
        ball_metric: Optional[Tuple[float, float]],
        poss_status: Optional[Union[PossessionStatus, str]],
        ball_speed_px_s: float = 0.0,
    ) -> Tuple[bool, Optional[int], Optional[str], Optional[int], Optional[Tuple[float, float]], Optional[Tuple[float, float]], float]:
        """Detects whether in-flight transfer has reached a receiver."""
        # Require minimal flight frames
        if cand.frame_age < self.config.min_transit_frames:
            return False, None, None, None, None, None, 0.0

        # Method A: Possession engine declared a secure carrier
        if curr_carrier_id is not None and curr_carrier_team not in (None, "UNKNOWN"):
            c_img, c_pitch = self._find_player_position(curr_carrier_id, player_observations)
            return True, curr_carrier_id, curr_carrier_team, curr_carrier_gt_id, c_img, c_pitch, 0.85

        # Method B: Direct proximity check to any player if ball is visible
        if ball_u is not None and ball_v is not None:
            best_p_id, best_team, best_gt_id, best_d, best_pos_img, best_pos_pitch = None, None, None, 999.0, None, None
            for p in player_observations:
                tid = p["track_id"] if isinstance(p, dict) else p.track_id
                tlabel = p.get("team_label", "UNKNOWN") if isinstance(p, dict) else getattr(p, "team_label", "UNKNOWN")
                role = p.get("role", "OUTFIELD_PLAYER") if isinstance(p, dict) else getattr(p, "role", "OUTFIELD_PLAYER")
                gt_id = p.get("gt_tracklet_id") if isinstance(p, dict) else getattr(p, "gt_tracklet_id", None)
                if "REFEREE" in str(role).upper():
                    continue

                pos_img, pos_pitch = self._find_player_position(tid, [p])
                if pos_img is not None:
                    d = np.hypot(ball_u - pos_img[0], ball_v - pos_img[1])
                    if d < best_d:
                        best_d = d
                        best_p_id = tid
                        best_team = tlabel
                        best_gt_id = gt_id
                        best_pos_img = pos_img
                        best_pos_pitch = pos_pitch

            if best_p_id is not None:
                # Do not trigger reception on the sender in early flight frames
                if best_p_id == cand.sender_track_id and cand.frame_age < 5:
                    return False, None, None, None, None, None, 0.0

                is_transit = poss_status in (PossessionStatus.PROVISIONAL_TRANSIT, "PROVISIONAL_TRANSIT")
                if is_transit:
                    # During active transit, ball is in flight; only trigger if ball has slowed down or transit is near timeout
                    if (best_d < self.config.reception_proximity_dist_px and ball_speed_px_s < self.config.reception_max_ball_speed_px_s) or \
                       (cand.frame_age >= self.config.max_transit_frames - 2 and best_d < self.config.reception_proximity_dist_px):
                        return True, best_p_id, best_team, best_gt_id, best_pos_img, best_pos_pitch, 0.70
                else:
                    if best_d < self.config.reception_proximity_dist_px:
                        return True, best_p_id, best_team, best_gt_id, best_pos_img, best_pos_pitch, 0.75

        return False, None, None, None, None, None, 0.0

    # --------------------------------------------------------------------------
    # INTERNAL LOGIC: EVENT FINALIZATION
    # --------------------------------------------------------------------------

    def _finalize_reception_event(
        self,
        cand: BallTransferCandidate,
        frame_index: int,
        timestamp: float,
        rec_p_id: Optional[int],
        rec_team: Optional[str],
        rec_gt_id: Optional[int],
        rec_pos_img: Optional[Tuple[float, float]],
        rec_pos_pitch: Optional[Tuple[float, float]],
        rec_conf: float,
        attack_directions: Optional[Dict[str, AttackDirection]],
        sequence_id: str,
    ) -> Optional[PassEvent]:
        """Finalizes completed pass, interception, or self-recontrol."""
        assert rec_p_id is not None
        self.event_counter += 1
        evt_id = f"PEVT_{sequence_id}_{self.event_counter:04d}"

        traj = self._finalize_trajectory(cand.trajectory, timestamp)

        # Calculate Ground Displacement & Features
        disp_m = None
        dx_att = None
        dy = None
        fwd_disp_m = None

        if cand.release_pos_pitch is not None and rec_pos_pitch is not None:
            rx, ry = cand.release_pos_pitch
            cx, cy = rec_pos_pitch
            disp_m = float(np.hypot(cx - rx, cy - ry))
            dy = float(cy - ry)

            att_dir = None
            if attack_directions and cand.sender_team in attack_directions:
                att_dir = attack_directions[cand.sender_team]

            if att_dir in (AttackDirection.NEGATIVE_X, -1):
                dx_att = float(-(cx - rx))
            elif att_dir in (AttackDirection.POSITIVE_X, 1):
                dx_att = float(cx - rx)

            fwd_disp_m = dx_att

        # Check for Self-Recontrol (Dribble touch / self pass rejection)
        is_self_recontrol = False
        if rec_p_id == cand.sender_track_id:
            if disp_m is None or disp_m <= self.config.self_recontrol_max_displacement_m:
                is_self_recontrol = True

        if is_self_recontrol:
            # Self touch is not a pass event
            return None

        # Determine Event Type
        if rec_team == cand.sender_team:
            event_type = PassEventType.PASS_COMPLETED
        else:
            event_type = PassEventType.PASS_INTERCEPTED

        # Multi-factor Confidence
        event_conf = self._compute_event_confidence(
            rel_conf=cand.release_confidence,
            rec_conf=rec_conf,
            traj=traj,
            sender_team=cand.sender_team,
            rec_team=rec_team,
        )

        if event_conf < self.config.min_event_confidence_threshold:
            event_type = PassEventType.BALL_RELEASE_UNRESOLVED

        event = PassEvent(
            event_id=evt_id,
            sequence_id=sequence_id,
            event_type=event_type,
            sender_track_id=cand.sender_track_id,
            sender_team=cand.sender_team,
            sender_gt_tracklet_id=cand.sender_gt_tracklet_id,
            release_frame=cand.release_frame,
            release_timestamp=cand.release_timestamp,
            release_position_image=cand.release_pos_image,
            release_position_pitch=cand.release_pos_pitch,
            release_confidence=cand.release_confidence,
            receiver_track_id=rec_p_id,
            receiver_team=rec_team,
            receiver_gt_tracklet_id=rec_gt_id,
            reception_frame=frame_index,
            reception_timestamp=timestamp,
            reception_position_image=rec_pos_img,
            reception_position_pitch=rec_pos_pitch,
            reception_confidence=rec_conf,
            trajectory=traj,
            pass_displacement_m=disp_m,
            delta_x_attack=dx_att,
            delta_y=dy,
            forward_displacement_m=fwd_disp_m,
            event_confidence=event_conf,
            is_self_recontrol=False,
            details={"flight_frames": cand.frame_age},
        )

        # Update carrier memory to the receiver
        self.prev_controlling_player_id = rec_p_id
        self.prev_controlling_team = rec_team
        self.prev_controlling_gt_id = rec_gt_id
        self.prev_carrier_frame = frame_index
        self.prev_carrier_pos_img = rec_pos_img
        self.prev_carrier_pos_pitch = rec_pos_pitch
        self.last_finalized_frame = frame_index

        self.finalized_events.append(event)
        return event

    def _finalize_timeout_event(
        self,
        cand: BallTransferCandidate,
        frame_index: int,
        timestamp: float,
        attack_directions: Optional[Dict[str, AttackDirection]],
        sequence_id: str,
    ) -> PassEvent:
        """Finalizes timed-out transfer as either CLEARANCE_CANDIDATE or BALL_RELEASE_UNRESOLVED."""
        self.event_counter += 1
        evt_id = f"PEVT_{sequence_id}_{self.event_counter:04d}"

        traj = self._finalize_trajectory(cand.trajectory, timestamp)

        # Check for Clearance Candidate
        is_clearance = False
        if traj.mean_ground_projected_speed_ms is not None and traj.net_ground_displacement_m is not None:
            if (traj.mean_ground_projected_speed_ms >= self.config.clearance_min_speed_ms or
                    traj.net_ground_displacement_m >= self.config.clearance_min_displacement_m):
                is_clearance = True
        elif cand.release_pos_pitch is not None and len(traj.metric_positions_m) > 0:
            end_pitch = traj.metric_positions_m[-1]
            ground_disp = float(np.hypot(end_pitch[0] - cand.release_pos_pitch[0], end_pitch[1] - cand.release_pos_pitch[1]))
            if ground_disp >= self.config.clearance_min_displacement_m:
                is_clearance = True

        if not is_clearance:
            if traj.mean_image_speed_px_s >= 350.0 or traj.image_path_length_px >= 200.0:
                is_clearance = True

        event_type = PassEventType.CLEARANCE_CANDIDATE if is_clearance else PassEventType.BALL_RELEASE_UNRESOLVED

        # Timed out transfer: old sender no longer controls ball
        self.prev_controlling_player_id = None
        self.prev_controlling_team = None
        self.prev_controlling_gt_id = None
        self.prev_carrier_frame = None
        self.prev_carrier_pos_img = None
        self.prev_carrier_pos_pitch = None
        self.last_finalized_frame = frame_index

        event = PassEvent(
            event_id=evt_id,
            sequence_id=sequence_id,
            event_type=event_type,
            sender_track_id=cand.sender_track_id,
            sender_team=cand.sender_team,
            sender_gt_tracklet_id=cand.sender_gt_tracklet_id,
            release_frame=cand.release_frame,
            release_timestamp=cand.release_timestamp,
            release_position_image=cand.release_pos_image,
            release_position_pitch=cand.release_pos_pitch,
            release_confidence=cand.release_confidence,
            receiver_track_id=None,
            receiver_team=None,
            reception_frame=None,
            reception_timestamp=None,
            trajectory=traj,
            event_confidence=0.50,
            details={"reason": "TIMEOUT_NO_RECEIVER", "flight_frames": cand.frame_age},
        )
        self.finalized_events.append(event)
        return event

    # --------------------------------------------------------------------------
    # TRAJECTORY & CONFIDENCE HELPERS
    # --------------------------------------------------------------------------

    def _finalize_trajectory(self, traj: BallTransferTrajectory, current_timestamp: float) -> BallTransferTrajectory:
        """Calculates path lengths, speeds, and displacements over recorded trajectory points."""
        pts_img = traj.image_positions_px
        pts_metric = traj.metric_positions_m

        if pts_img:
            # Image path length
            img_dist = 0.0
            for i in range(len(pts_img) - 1):
                img_dist += np.hypot(pts_img[i + 1][0] - pts_img[i][0], pts_img[i + 1][1] - pts_img[i][1])
            traj.image_path_length_px = float(img_dist)

        dt = max(1e-3, current_timestamp - (traj.timestamps[0] if traj.timestamps else current_timestamp))
        traj.flight_duration_s = float(dt)
        traj.mean_image_speed_px_s = float(traj.image_path_length_px / dt)

        if pts_metric and traj.trajectory_ground_valid and len(pts_metric) >= 2:
            m_dist = 0.0
            for i in range(len(pts_metric) - 1):
                m_dist += np.hypot(pts_metric[i + 1][0] - pts_metric[i][0], pts_metric[i + 1][1] - pts_metric[i][1])
            traj.ground_projected_path_length_m = float(m_dist)
            traj.net_ground_displacement_m = float(np.hypot(
                pts_metric[-1][0] - pts_metric[0][0],
                pts_metric[-1][1] - pts_metric[0][1],
            ))
            traj.mean_ground_projected_speed_ms = float(m_dist / dt)
        else:
            traj.ground_projected_path_length_m = None
            traj.net_ground_displacement_m = None
            traj.mean_ground_projected_speed_ms = None

        return traj

    def _compute_event_confidence(
        self,
        rel_conf: float,
        rec_conf: float,
        traj: BallTransferTrajectory,
        sender_team: str,
        rec_team: Optional[str],
    ) -> float:
        """Fused event confidence model combining release, trajectory, and reception."""
        # 1. Trajectory continuity
        traj_conf = 0.85 if len(traj.image_positions_px) >= 3 else 0.50
        if traj.aerial_suspected:
            traj_conf *= 0.85

        # 2. Team confidence
        team_conf = 0.90 if (sender_team not in ("UNKNOWN", None) and rec_team not in ("UNKNOWN", None)) else 0.40

        score = 0.25 * rel_conf + 0.25 * rec_conf + 0.25 * traj_conf + 0.25 * team_conf
        return float(np.clip(score, 0.0, 1.0))

    # --------------------------------------------------------------------------
    # DATA EXTRACTION HELPERS
    # --------------------------------------------------------------------------

    def _extract_ball_point(
        self,
        ball_obs: Optional[Union[BallMetricObservation, Dict[str, Any]]],
    ) -> Tuple[Optional[float], Optional[float], Optional[Tuple[float, float]], float]:
        """Extracts (u, v) and (x, y) coordinates from ball observation."""
        if ball_obs is None:
            return None, None, None, 0.0

        if isinstance(ball_obs, dict):
            bbox = ball_obs.get("bbox")
            conf = float(ball_obs.get("confidence", 1.0) or 1.0)
            u, v = None, None
            if bbox and len(bbox) >= 4:
                u = (bbox[0] + bbox[2]) / 2.0
                v = (bbox[1] + bbox[3]) / 2.0
            x = ball_obs.get("pitch_x_m") if ball_obs.get("pitch_x_m") is not None else ball_obs.get("x")
            y = ball_obs.get("pitch_y_m") if ball_obs.get("pitch_y_m") is not None else ball_obs.get("y")
            metric = (float(x), float(y)) if (x is not None and y is not None) else None
            return u, v, metric, conf

        # BallMetricObservation object
        u, v = None, None
        bbox = getattr(ball_obs, "bbox", None)
        if bbox is not None and len(bbox) >= 4:
            u = (bbox[0] + bbox[2]) / 2.0
            v = (bbox[1] + bbox[3]) / 2.0
        elif hasattr(ball_obs, "image_anchor_px") and ball_obs.image_anchor_px is not None:
            u, v = ball_obs.image_anchor_px

        conf = float(getattr(ball_obs, "confidence", 1.0) or 1.0)
        x = ball_obs.pitch_x_m
        y = ball_obs.pitch_y_m
        metric = (float(x), float(y)) if (x is not None and y is not None) else None
        return u, v, metric, conf

    def _extract_possession_info(
        self,
        possession_state: Optional[Union[TeamPossessionFrameState, Dict[str, Any]]],
        player_observations: Sequence[Union[PlayerMetricObservation, Dict[str, Any]]],
    ) -> Tuple[Optional[int], Optional[str], Optional[int], Optional[Union[PossessionStatus, str]]]:
        """Extracts controlling player ID, team, GT ID, and possession status."""
        if possession_state is None:
            return None, None, None, None

        if isinstance(possession_state, dict):
            pid = possession_state.get("controlling_player_id")
            team = possession_state.get("controlling_player_team") or possession_state.get("possession_team")
            gt_id = possession_state.get("controlling_player_gt_id") or possession_state.get("details", {}).get("controlling_player_gt_id")
            status = possession_state.get("possession_status")
            return pid, team, gt_id, status

        # TeamPossessionFrameState object
        pid = possession_state.controlling_player_id
        team = possession_state.controlling_player_team or possession_state.possession_team
        gt_id = getattr(possession_state, "controlling_player_gt_id", None)
        if gt_id is None and hasattr(possession_state, "details"):
            gt_id = possession_state.details.get("controlling_player_gt_id")
        status = possession_state.possession_status
        return pid, team, gt_id, status

    def _find_player_position(
        self,
        player_id: int,
        player_observations: Sequence[Union[PlayerMetricObservation, Dict[str, Any]]],
    ) -> Tuple[Optional[Tuple[float, float]], Optional[Tuple[float, float]]]:
        """Finds player footpoint in image and pitch coordinates."""
        for p in player_observations:
            tid = p["track_id"] if isinstance(p, dict) else p.track_id
            if tid == player_id:
                # Image footpoint
                img_pos = None
                bbox = p.get("bbox") if isinstance(p, dict) else getattr(p, "bbox", None)
                if bbox and len(bbox) >= 4:
                    img_pos = ((bbox[0] + bbox[2]) / 2.0, float(bbox[3]))
                elif not isinstance(p, dict) and hasattr(p, "image_anchor_px") and p.image_anchor_px:
                    img_pos = p.image_anchor_px

                # Pitch position
                pitch_pos = None
                if isinstance(p, dict):
                    px = p.get("smoothed_x_m") if p.get("smoothed_x_m") is not None else p.get("pitch_x_m")
                    py = p.get("smoothed_y_m") if p.get("smoothed_y_m") is not None else p.get("pitch_y_m")
                else:
                    px = getattr(p, "smoothed_x_m", None)
                    if px is None:
                        px = getattr(p, "pitch_x_m", None)
                    py = getattr(p, "smoothed_y_m", None)
                    if py is None:
                        py = getattr(p, "pitch_y_m", None)
                if px is not None and py is not None:
                    pitch_pos = (float(px), float(py))
                return img_pos, pitch_pos
        return None, None
