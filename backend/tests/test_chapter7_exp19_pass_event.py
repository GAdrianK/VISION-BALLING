"""
Unit tests for Chapter 7 EXP-19: Pass Detection & Ball Event Trajectories.
Covers:
  - Same-team pass completion
  - Opponent interception
  - Self-recontrol / dribble rejection
  - Timeout unresolved ball release
  - Clearance candidate detection
  - Aerial ground-jump invalidation
  - Tracker ID switch robustness
  - Directional features (forward / backward attack displacement)
  - Causal state progression (PENDING_TRANSFER during flight)
  - Confidence calculation
"""
import pytest
import numpy as np

from app.video_analysis.pass_detector import (
    BallTransferCandidate,
    BallTransferTrajectory,
    PassCandidateState,
    PassDetectorConfig,
    PassEvent,
    PassEventDetector,
    PassEventType,
    PassFrameState,
)
from app.video_analysis.possession import (
    PossessionStatus,
    TeamPossessionFrameState,
    BallControlState,
)
from app.video_analysis.tactical_lines import AttackDirection


def _make_player(track_id: int, team: str, x_px: float, y_px: float, pitch_x: float = 0.0, pitch_y: float = 0.0, role: str = "OUTFIELD_PLAYER"):
    return {
        "track_id": track_id,
        "team_label": team,
        "team_confidence": 0.95,
        "role": role,
        "bbox": [x_px - 15.0, y_px - 80.0, x_px + 15.0, y_px],
        "pitch_x_m": pitch_x,
        "pitch_y_m": pitch_y,
    }


def _make_ball(x_px: float, y_px: float, pitch_x: float = 0.0, pitch_y: float = 0.0, conf: float = 0.90):
    return {
        "bbox": [x_px - 6.0, y_px - 6.0, x_px + 6.0, y_px + 6.0],
        "pitch_x_m": pitch_x,
        "pitch_y_m": pitch_y,
        "confidence": conf,
    }


def _make_poss_state(frame_idx: int, timestamp: float, team: str, player_id: int, status: PossessionStatus = PossessionStatus.SECURE):
    return TeamPossessionFrameState(
        frame_index=frame_idx,
        timestamp=timestamp,
        possession_team=team,
        possession_status=status,
        possession_confidence=0.85,
        controlling_player_id=player_id,
        controlling_player_team=team,
        control_state=BallControlState.CONTROLLED,
    )


def test_pass_completed_same_team():
    """Player 1 (TEAM_0) passes to Player 2 (TEAM_0) -> PASS_COMPLETED."""
    detector = PassEventDetector()

    p1 = _make_player(1, "TEAM_0", 400.0, 500.0, pitch_x=-10.0, pitch_y=0.0)
    p2 = _make_player(2, "TEAM_0", 600.0, 500.0, pitch_x=10.0, pitch_y=0.0)

    # 1. P1 controls ball at frame 1..3
    for f in range(1, 4):
        ball = _make_ball(405.0, 500.0, pitch_x=-9.5, pitch_y=0.0)
        poss = _make_poss_state(f, f * 0.04, "TEAM_0", 1, PossessionStatus.SECURE)
        st = detector.process_frame(f, f * 0.04, [p1, p2], ball, poss)
        assert st.active_state != PassEventType.PENDING_TRANSFER

    # 2. P1 releases ball towards P2 at frame 4..8 (in transit)
    for f in range(4, 9):
        alpha = (f - 3) / 6.0
        bx = 405.0 + alpha * 190.0
        b_pitch = -9.5 + alpha * 19.0
        ball = _make_ball(bx, 500.0, pitch_x=b_pitch, pitch_y=0.0)
        poss = _make_poss_state(f, f * 0.04, "TEAM_0", None, PossessionStatus.PROVISIONAL_TRANSIT)
        st = detector.process_frame(f, f * 0.04, [p1, p2], ball, poss)
        assert st.active_state == PassEventType.PENDING_TRANSFER
        assert st.recent_finalized_event is None

    # 3. P2 receives ball at frame 9
    ball_rec = _make_ball(598.0, 500.0, pitch_x=9.8, pitch_y=0.0)
    poss_rec = _make_poss_state(9, 9 * 0.04, "TEAM_0", 2, PossessionStatus.SECURE)
    st = detector.process_frame(9, 9 * 0.04, [p1, p2], ball_rec, poss_rec)

    assert st.recent_finalized_event is not None
    evt = st.recent_finalized_event
    assert evt.event_type == PassEventType.PASS_COMPLETED
    assert evt.sender_track_id == 1
    assert evt.receiver_track_id == 2
    assert evt.sender_team == "TEAM_0"
    assert evt.receiver_team == "TEAM_0"
    assert evt.release_frame == 4
    assert evt.reception_frame == 9
    assert evt.pass_displacement_m is not None
    assert evt.pass_displacement_m > 15.0


def test_pass_intercepted_opponent():
    """Player 1 (TEAM_0) passes, Player 10 (TEAM_1) intercepts -> PASS_INTERCEPTED."""
    detector = PassEventDetector()

    p1 = _make_player(1, "TEAM_0", 400.0, 500.0, pitch_x=-10.0, pitch_y=0.0)
    p_opp = _make_player(10, "TEAM_1", 550.0, 500.0, pitch_x=5.0, pitch_y=0.0)

    # 1. P1 controls ball
    for f in range(1, 4):
        ball = _make_ball(405.0, 500.0, pitch_x=-9.5, pitch_y=0.0)
        poss = _make_poss_state(f, f * 0.04, "TEAM_0", 1, PossessionStatus.SECURE)
        detector.process_frame(f, f * 0.04, [p1, p_opp], ball, poss)

    # 2. Ball released in flight
    for f in range(4, 7):
        alpha = (f - 3) / 4.0
        ball = _make_ball(405.0 + alpha * 140.0, 500.0, pitch_x=-9.5 + alpha * 14.0, pitch_y=0.0)
        poss = _make_poss_state(f, f * 0.04, "TEAM_0", None, PossessionStatus.PROVISIONAL_TRANSIT)
        detector.process_frame(f, f * 0.04, [p1, p_opp], ball, poss)

    # 3. Opponent intercepts
    ball_rec = _make_ball(548.0, 500.0, pitch_x=4.8, pitch_y=0.0)
    poss_rec = _make_poss_state(7, 7 * 0.04, "TEAM_1", 10, PossessionStatus.SECURE)
    st = detector.process_frame(7, 7 * 0.04, [p1, p_opp], ball_rec, poss_rec)

    assert st.recent_finalized_event is not None
    evt = st.recent_finalized_event
    assert evt.event_type == PassEventType.PASS_INTERCEPTED
    assert evt.sender_team == "TEAM_0"
    assert evt.receiver_team == "TEAM_1"
    assert evt.sender_track_id == 1
    assert evt.receiver_track_id == 10


def test_self_recontrol_dribble_rejection():
    """Player 1 pushes ball 1.5m and touches again -> rejected as pass (dribble)."""
    detector = PassEventDetector(config=PassDetectorConfig(self_recontrol_max_displacement_m=3.5))

    p1 = _make_player(1, "TEAM_0", 400.0, 500.0, pitch_x=0.0, pitch_y=0.0)

    # 1. P1 controls ball
    for f in range(1, 4):
        ball = _make_ball(405.0, 500.0, pitch_x=0.2, pitch_y=0.0)
        poss = _make_poss_state(f, f * 0.04, "TEAM_0", 1, PossessionStatus.SECURE)
        detector.process_frame(f, f * 0.04, [p1], ball, poss)

    # 2. P1 taps ball ahead 1.2m
    for f in range(4, 7):
        ball = _make_ball(420.0, 500.0, pitch_x=1.2, pitch_y=0.0)
        poss = _make_poss_state(f, f * 0.04, "TEAM_0", None, PossessionStatus.PROVISIONAL_TRANSIT)
        detector.process_frame(f, f * 0.04, [p1], ball, poss)

    # 3. P1 regains control at pitch_x=1.5m (net displacement 1.3m < 3.5m)
    p1_fwd = _make_player(1, "TEAM_0", 425.0, 500.0, pitch_x=1.5, pitch_y=0.0)
    ball_rec = _make_ball(425.0, 500.0, pitch_x=1.5, pitch_y=0.0)
    poss_rec = _make_poss_state(7, 7 * 0.04, "TEAM_0", 1, PossessionStatus.SECURE)
    st = detector.process_frame(7, 7 * 0.04, [p1_fwd], ball_rec, poss_rec)

    # Must NOT emit a pass completed event
    assert st.recent_finalized_event is None
    assert len(detector.finalized_events) == 0


def test_timeout_unresolved_event():
    """Ball released but no player receives within max_transit_frames -> BALL_RELEASE_UNRESOLVED."""
    detector = PassEventDetector(config=PassDetectorConfig(max_transit_frames=10))

    p1 = _make_player(1, "TEAM_0", 400.0, 500.0, pitch_x=0.0, pitch_y=0.0)

    # Control
    for f in range(1, 3):
        ball = _make_ball(405.0, 500.0, pitch_x=0.2, pitch_y=0.0)
        poss = _make_poss_state(f, f * 0.04, "TEAM_0", 1, PossessionStatus.SECURE)
        detector.process_frame(f, f * 0.04, [p1], ball, poss)

    # Release into empty space
    for f in range(3, 14):
        bx = 405.0 + (f - 2) * 10.0
        ball = _make_ball(bx, 500.0, pitch_x=(f - 2) * 1.0, pitch_y=0.0)
        poss = _make_poss_state(f, f * 0.04, "TEAM_0", None, PossessionStatus.NEUTRAL)
        st = detector.process_frame(f, f * 0.04, [], ball, poss)

    # After frame 13 (transit age > 10 frames), an unresolved event must be finalized
    assert len(detector.finalized_events) == 1
    evt = detector.finalized_events[0]
    assert evt.event_type == PassEventType.BALL_RELEASE_UNRESOLVED
    assert evt.sender_track_id == 1
    assert evt.receiver_track_id is None


def test_clearance_candidate_high_speed():
    """Defensive kick with high speed and large displacement -> CLEARANCE_CANDIDATE."""
    cfg = PassDetectorConfig(
        max_transit_frames=8,
        clearance_min_speed_ms=15.0,
        clearance_min_displacement_m=20.0,
    )
    detector = PassEventDetector(config=cfg)
    p1 = _make_player(5, "TEAM_0", 200.0, 500.0, pitch_x=-40.0, pitch_y=0.0)

    # Control
    for f in range(1, 3):
        ball = _make_ball(205.0, 500.0, pitch_x=-39.5, pitch_y=0.0)
        poss = _make_poss_state(f, f * 0.04, "TEAM_0", 5, PossessionStatus.SECURE)
        detector.process_frame(f, f * 0.04, [p1], ball, poss)

    # Hard clearance forward: travels 30m in 8 frames (0.32s -> 93 m/s ground speed)
    for f in range(3, 12):
        alpha = (f - 2) / 8.0
        ball = _make_ball(205.0 + alpha * 500.0, 500.0, pitch_x=-39.5 + alpha * 35.0, pitch_y=0.0)
        poss = _make_poss_state(f, f * 0.04, "TEAM_0", None, PossessionStatus.NEUTRAL)
        detector.process_frame(f, f * 0.04, [], ball, poss)

    assert len(detector.finalized_events) == 1
    evt = detector.finalized_events[0]
    assert evt.event_type == PassEventType.CLEARANCE_CANDIDATE
    assert evt.sender_track_id == 5


def test_aerial_ground_jump_invalidation():
    """Aerial ball ground speed jump > 25 m/s invalidates ground metric trajectory."""
    detector = PassEventDetector(config=PassDetectorConfig(aerial_ground_jump_speed_ms=25.0, max_transit_frames=10))
    p1 = _make_player(1, "TEAM_0", 400.0, 500.0, pitch_x=0.0, pitch_y=0.0)

    for f in range(1, 3):
        ball = _make_ball(405.0, 500.0, pitch_x=0.0, pitch_y=0.0)
        poss = _make_poss_state(f, f * 0.04, "TEAM_0", 1, PossessionStatus.SECURE)
        detector.process_frame(f, f * 0.04, [p1], ball, poss)

    # Frame 3: release
    ball = _make_ball(420.0, 500.0, pitch_x=1.0, pitch_y=0.0)
    poss = _make_poss_state(3, 0.12, "TEAM_0", None, PossessionStatus.PROVISIONAL_TRANSIT)
    st = detector.process_frame(3, 0.12, [p1], ball, poss)

    # Frame 4: huge artificial jump in ground projection (30m in 0.04s -> 750 m/s)
    ball_aerial = _make_ball(450.0, 480.0, pitch_x=31.0, pitch_y=0.0)
    poss_flight = _make_poss_state(4, 0.16, "TEAM_0", None, PossessionStatus.PROVISIONAL_TRANSIT)
    st2 = detector.process_frame(4, 0.16, [p1], ball_aerial, poss_flight)

    assert st2.is_aerial_suspected is True
    assert detector.active_candidate.trajectory.trajectory_ground_valid is False
    assert len(detector.active_candidate.trajectory.image_positions_px) == 2


def test_sender_and_receiver_id_switch_robustness():
    """Tracker ID flips do not disrupt team-level pass completion."""
    detector = PassEventDetector()

    p1 = _make_player(1, "TEAM_0", 400.0, 500.0, pitch_x=-5.0, pitch_y=0.0)
    p2_switched = _make_player(999, "TEAM_0", 600.0, 500.0, pitch_x=15.0, pitch_y=0.0)

    # 1. P1 controls
    for f in range(1, 4):
        ball = _make_ball(405.0, 500.0, pitch_x=-4.8, pitch_y=0.0)
        poss = _make_poss_state(f, f * 0.04, "TEAM_0", 1, PossessionStatus.SECURE)
        detector.process_frame(f, f * 0.04, [p1], ball, poss)

    # 2. Release & flight
    for f in range(4, 8):
        alpha = (f - 3) / 5.0
        ball = _make_ball(405.0 + alpha * 190.0, 500.0, pitch_x=-4.8 + alpha * 19.5, pitch_y=0.0)
        poss = _make_poss_state(f, f * 0.04, "TEAM_0", None, PossessionStatus.PROVISIONAL_TRANSIT)
        detector.process_frame(f, f * 0.04, [p1, p2_switched], ball, poss)

    # 3. Reception by ID 999
    ball_rec = _make_ball(600.0, 500.0, pitch_x=15.0, pitch_y=0.0)
    poss_rec = _make_poss_state(8, 0.32, "TEAM_0", 999, PossessionStatus.SECURE)
    st = detector.process_frame(8, 0.32, [p1, p2_switched], ball_rec, poss_rec)

    assert st.recent_finalized_event is not None
    evt = st.recent_finalized_event
    assert evt.event_type == PassEventType.PASS_COMPLETED
    assert evt.sender_team == "TEAM_0"
    assert evt.receiver_team == "TEAM_0"
    assert evt.receiver_track_id == 999


def test_directional_attack_features():
    """Forward displacement reflects attacking direction properly."""
    detector = PassEventDetector()

    p1 = _make_player(1, "TEAM_0", 400.0, 500.0, pitch_x=-10.0, pitch_y=5.0)
    p2 = _make_player(2, "TEAM_0", 550.0, 520.0, pitch_x=5.0, pitch_y=10.0)

    # Attacking LEFT_TO_RIGHT (+X)
    att_dirs = {"TEAM_0": AttackDirection.POSITIVE_X}

    for f in range(1, 3):
        ball = _make_ball(405.0, 500.0, pitch_x=-10.0, pitch_y=5.0)
        poss = _make_poss_state(f, f * 0.04, "TEAM_0", 1, PossessionStatus.SECURE)
        detector.process_frame(f, f * 0.04, [p1, p2], ball, poss, attack_directions=att_dirs)

    # Flight
    for f in range(3, 7):
        ball = _make_ball(405.0 + (f - 2) * 35.0, 500.0, pitch_x=-10.0 + (f - 2) * 3.5, pitch_y=6.0)
        poss = _make_poss_state(f, f * 0.04, "TEAM_0", None, PossessionStatus.PROVISIONAL_TRANSIT)
        detector.process_frame(f, f * 0.04, [p1, p2], ball, poss, attack_directions=att_dirs)

    # Reception
    ball_rec = _make_ball(550.0, 520.0, pitch_x=5.0, pitch_y=10.0)
    poss_rec = _make_poss_state(7, 0.28, "TEAM_0", 2, PossessionStatus.SECURE)
    st = detector.process_frame(7, 0.28, [p1, p2], ball_rec, poss_rec, attack_directions=att_dirs)

    evt = st.recent_finalized_event
    assert evt is not None
    assert evt.forward_displacement_m == pytest.approx(15.0, abs=1e-2)
    assert evt.delta_y == pytest.approx(5.0, abs=1e-2)
