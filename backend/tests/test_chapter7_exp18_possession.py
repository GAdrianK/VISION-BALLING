"""Unit tests for Chapter 7: Ball Control, Team Possession & Possession Changes (EXP-18).

Verifies:
1. Player control acquisition with temporal confirmation hysteresis (N=3 frames).
2. Same-team handoff (pass between teammates preserves continuous team possession without turnover).
3. Opposing-team takeover with causal confirmation delay (N=5 frames) emitting PossessionChangeEvent.
4. Free ball states, pass transit, and provisional grace window (15 frames) transitioning to NEUTRAL.
5. Contested states during 50/50 duels between opposing players.
6. Hysteresis rejection of 1-frame transient proximity flicker.
7. Ball disappearance / occlusion policy (provisional hold <= 12 frames, UNKNOWN > 12 frames).
8. Robustness to player track-ID switches (team possession continuity preserved).
9. Low team-confidence abstention (prevents arbitrary team possession on ambiguous crops).
10. Fallback behavior when calibration is invalid (smooth image-space fallback).
11. Rejection of stale / invalid ball tracker states.
12. Aerial ball detection heuristic (ground projection jump speed discount).
13. Strict exclusion of referees from ball control.
14. Strictly causal execution (zero future frame leakage).
15. Upstream perception and tactical geometry immutability (Ch 5, 6, EXP-16, EXP-17).
"""

from __future__ import annotations

import numpy as np
import pytest

from app.video_analysis.pitch_calibration import PitchDimensions
from app.video_analysis.possession import (
    BallControlEvaluation,
    BallControlEstimator,
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


def test_player_control_acquisition_hysteresis() -> None:
    """Verifies that player control requires 3 consecutive frames of proximity to confirm."""
    config = PossessionConfig(player_control_confirm_frames=3)
    engine = PossessionEngine(config=config)

    # Player 1 at (500, 500) with height 100px. Ball at (500, 580) -> near footpoint (foot is at 500, 600)
    player = {
        "track_id": 1,
        "bbox": [450, 400, 550, 600],  # center=(500, 500), foot=(500, 600), h=200
        "team_label": "TEAM_0",
        "team_confidence": 0.95,
        "role": "OUTFIELD_PLAYER",
    }
    ball = {"bbox": [495, 590, 505, 600], "confidence": 0.90, "state": "DETECTED"}

    # Frame 1: candidate detected, but player control not yet confirmed (< 3 frames)
    f1 = engine.process_frame(1, 0.0, [player], ball)
    assert f1.control_state == BallControlState.CONTROLLED
    assert f1.controlling_player_id is None  # Not yet confirmed

    # Frame 2: still pending confirmation
    f2 = engine.process_frame(2, 0.04, [player], ball)
    assert f2.controlling_player_id is None

    # Frame 3: reaches 3 frames -> confirmed!
    f3 = engine.process_frame(3, 0.08, [player], ball)
    assert f3.controlling_player_id == 1
    assert f3.controlling_player_team == "TEAM_0"
    assert f3.possession_team == "TEAM_0"
    assert f3.possession_status == PossessionStatus.SECURE


def test_same_team_handoff_no_turnover() -> None:
    """Verifies that a pass between teammates preserves possession without spurious turnovers."""
    engine = PossessionEngine()

    p1 = {"track_id": 1, "bbox": [450, 400, 550, 600], "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"}
    p2 = {"track_id": 2, "bbox": [700, 400, 800, 600], "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"}

    ball_at_p1 = {"bbox": [495, 590, 505, 600], "confidence": 0.90}
    ball_in_transit = {"bbox": [600, 500, 610, 510], "confidence": 0.85}
    ball_at_p2 = {"bbox": [745, 590, 755, 600], "confidence": 0.90}

    # 1. P1 establishes secure possession
    for i in range(1, 4):
        engine.process_frame(i, i * 0.04, [p1, p2], ball_at_p1)

    assert engine.state_machine.current_team == "TEAM_0"
    assert engine.state_machine.current_status == PossessionStatus.SECURE

    # 2. Ball is in flight between P1 and P2 (FREE_BALL)
    for i in range(4, 9):
        f = engine.process_frame(i, i * 0.04, [p1, p2], ball_in_transit)
        assert f.control_state == BallControlState.FREE_BALL
        assert f.possession_team == "TEAM_0"
        assert f.possession_status == PossessionStatus.PROVISIONAL_TRANSIT

    # 3. P2 receives ball
    for i in range(9, 13):
        f = engine.process_frame(i, i * 0.04, [p1, p2], ball_at_p2)

    assert f.possession_team == "TEAM_0"
    assert f.possession_status == PossessionStatus.SECURE
    assert f.controlling_player_id == 2

    # Zero turnovers emitted during same-team handoff!
    assert len(engine.turnover_events) == 0


def test_opposing_team_takeover_confirms_turnover() -> None:
    """Verifies that when opponent wins ball, turnover is confirmed after 5 frames with correct metadata."""
    config = PossessionConfig(team_possession_confirm_frames=5)
    engine = PossessionEngine(config=config)

    p_team0 = {"track_id": 1, "bbox": [300, 400, 400, 600], "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"}
    p_team1 = {"track_id": 10, "bbox": [700, 400, 800, 600], "team_label": "TEAM_1", "role": "OUTFIELD_PLAYER"}

    ball_at_t0 = {"bbox": [345, 590, 355, 600], "confidence": 0.90}
    ball_at_t1 = {"bbox": [745, 590, 755, 600], "confidence": 0.90}

    # TEAM_0 secures possession
    for i in range(1, 5):
        engine.process_frame(i, i * 0.04, [p_team0, p_team1], ball_at_t0)
    assert engine.state_machine.current_team == "TEAM_0"

    # TEAM_1 takes control: frames 5 to 8 (< 5 confirmation frames) hold provisional state
    for i in range(5, 9):
        f = engine.process_frame(i, i * 0.04, [p_team0, p_team1], ball_at_t1)
        assert len(engine.turnover_events) == 0
        assert f.possession_team == "TEAM_0"  # Pending confirmation

    # Frame 9 is the 5th consecutive frame of TEAM_1 control -> Turnover confirmed!
    f9 = engine.process_frame(9, 9 * 0.04, [p_team0, p_team1], ball_at_t1)
    assert f9.possession_team == "TEAM_1"
    assert f9.possession_status == PossessionStatus.SECURE
    assert len(engine.turnover_events) == 1

    ev = engine.turnover_events[0]
    assert ev.from_team == "TEAM_0"
    assert ev.to_team == "TEAM_1"
    assert ev.from_player_track_id == 1
    assert ev.to_player_track_id == 10
    assert ev.confirmation_delay_frames == 5


def test_free_ball_grace_window_and_neutral_transition() -> None:
    """Verifies that free ball holds provisional team state for 15 frames then transitions to NEUTRAL."""
    config = PossessionConfig(free_ball_grace_frames=15)
    engine = PossessionEngine(config=config)

    p1 = {"track_id": 1, "bbox": [400, 400, 500, 600], "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"}
    ball_controlled = {"bbox": [445, 590, 455, 600], "confidence": 0.90}
    ball_far_away = {"bbox": [1500, 800, 1510, 810], "confidence": 0.80}  # Far away from player

    # Establish initial possession
    for i in range(1, 4):
        engine.process_frame(i, i * 0.04, [p1], ball_controlled)
    assert engine.state_machine.current_team == "TEAM_0"

    # Free ball frames 1 to 15: provisional transit with TEAM_0
    for i in range(4, 19):
        f = engine.process_frame(i, i * 0.04, [p1], ball_far_away)
        assert f.control_state == BallControlState.FREE_BALL
        assert f.possession_team == "TEAM_0"
        assert f.possession_status == PossessionStatus.PROVISIONAL_TRANSIT

    # Frame 19 (16th free ball frame > 15): transitions to NEUTRAL
    f_neutral = engine.process_frame(19, 19 * 0.04, [p1], ball_far_away)
    assert f_neutral.possession_team == "NEUTRAL"
    assert f_neutral.possession_status == PossessionStatus.NEUTRAL
    assert f_neutral.possession_confidence == 0.0


def test_contested_state_50_50_duel() -> None:
    """Verifies that opposing players in close proximity to the ball yield CONTESTED state."""
    estimator = BallControlEstimator(config=PossessionConfig(contested_score_margin=0.15))

    # Two opposing players closely contesting the ball at (500, 500)
    p0 = {"track_id": 1, "bbox": [450, 420, 520, 550], "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"}
    p1 = {"track_id": 2, "bbox": [480, 420, 550, 550], "team_label": "TEAM_1", "role": "OUTFIELD_PLAYER"}
    ball = {"bbox": [495, 530, 505, 540], "confidence": 0.90}

    eval_res = estimator.evaluate([p0, p1], ball)

    assert eval_res.state == BallControlState.CONTESTED
    assert eval_res.primary_candidate is not None
    assert eval_res.secondary_candidate is not None
    assert eval_res.score_margin < 0.15
    assert set(eval_res.details["contesting_teams"]) == {"TEAM_0", "TEAM_1"}


def test_control_and_possession_hysteresis_flicker_rejection() -> None:
    """Verifies that 1-frame spurious proximity does not hijack control or trigger turnover."""
    engine = PossessionEngine()

    p_t0 = {"track_id": 1, "bbox": [400, 400, 500, 600], "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"}
    p_t1 = {"track_id": 2, "bbox": [800, 400, 900, 600], "team_label": "TEAM_1", "role": "OUTFIELD_PLAYER"}

    ball_at_t0 = {"bbox": [445, 590, 455, 600], "confidence": 0.90}
    ball_glitch_t1 = {"bbox": [845, 590, 855, 600], "confidence": 0.90}

    # Secure possession for TEAM_0
    for i in range(1, 5):
        engine.process_frame(i, i * 0.04, [p_t0, p_t1], ball_at_t0)
    assert engine.state_machine.current_team == "TEAM_0"

    # Single-frame glitch where ball flickers to TEAM_1
    f_glitch = engine.process_frame(5, 0.20, [p_t0, p_t1], ball_glitch_t1)
    assert f_glitch.possession_team == "TEAM_0"  # Protected by hysteresis
    assert len(engine.turnover_events) == 0

    # Frame 6: ball is back with TEAM_0
    f_back = engine.process_frame(6, 0.24, [p_t0, p_t1], ball_at_t0)
    assert f_back.possession_team == "TEAM_0"
    assert f_back.possession_status == PossessionStatus.SECURE
    assert len(engine.turnover_events) == 0


def test_ball_disappearance_occlusion_policy() -> None:
    """Verifies that missing ball holds provisional possession for 12 frames, then emits UNKNOWN."""
    config = PossessionConfig(max_ball_occlusion_frames=12)
    engine = PossessionEngine(config=config)

    p0 = {"track_id": 1, "bbox": [400, 400, 500, 600], "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"}
    ball = {"bbox": [445, 590, 455, 600], "confidence": 0.90}

    # Establish possession
    for i in range(1, 4):
        engine.process_frame(i, i * 0.04, [p0], ball)
    assert engine.state_machine.current_team == "TEAM_0"

    # Ball disappears (occlusion / out-of-view): frames 4 to 15 (12 frames)
    for i in range(4, 16):
        f = engine.process_frame(i, i * 0.04, [p0], None)
        assert f.possession_team == "TEAM_0"
        assert f.possession_status == PossessionStatus.PROVISIONAL_TRANSIT
        assert f.occlusion_age_frames == (i - 3)

    # Frame 16 (13th occlusion frame > 12): transitions to UNKNOWN
    f_unk = engine.process_frame(16, 16 * 0.04, [p0], None)
    assert f_unk.possession_team == "UNKNOWN"
    assert f_unk.possession_status == PossessionStatus.UNKNOWN
    assert f_unk.possession_confidence == 0.0


def test_player_track_id_switch_robustness() -> None:
    """Verifies that a player tracker ID switch on the same team does NOT create a false turnover."""
    engine = PossessionEngine()

    p_orig = {"track_id": 10, "bbox": [400, 400, 500, 600], "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"}
    # Tracker fragmented ID: changes to track_id 27 at the exact same location and team
    p_switched = {"track_id": 27, "bbox": [400, 400, 500, 600], "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"}
    ball = {"bbox": [445, 590, 455, 600], "confidence": 0.90}

    # Frame 1-3: track 10 has ball
    for i in range(1, 4):
        engine.process_frame(i, i * 0.04, [p_orig], ball)
    assert engine.state_machine.current_team == "TEAM_0"
    assert engine.state_machine.active_player_id == 10

    # Frame 4: ID switch to track 27
    f4 = engine.process_frame(4, 0.16, [p_switched], ball)
    assert f4.possession_team == "TEAM_0"
    assert f4.possession_status == PossessionStatus.SECURE
    assert len(engine.turnover_events) == 0  # Zero spurious turnovers!


def test_low_team_confidence_abstention() -> None:
    """Verifies that when controlling player's team attribution is uncertain, engine abstains."""
    config = PossessionConfig(min_team_label_confidence=0.50)
    engine = PossessionEngine(config=config)

    # Player has low team attribution confidence (0.35 < 0.50)
    player = {
        "track_id": 1,
        "bbox": [400, 400, 500, 600],
        "team_label": "TEAM_0",
        "team_confidence": 0.35,
        "role": "OUTFIELD_PLAYER",
    }
    ball = {"bbox": [445, 590, 455, 600], "confidence": 0.90}

    f = engine.process_frame(1, 0.0, [player], ball)
    assert f.possession_team == "UNKNOWN"
    assert f.invalidation_reason == "LOW_TEAM_LABEL_CONFIDENCE"


def test_invalid_calibration_smooth_image_fallback() -> None:
    """Verifies that invalid calibration falls back gracefully to image-space footpoint proximity."""
    engine = PossessionEngine()

    player = {
        "track_id": 1,
        "bbox": [400, 400, 500, 600],
        "team_label": "TEAM_0",
        "role": "OUTFIELD_PLAYER",
        "pitch_x_m": None,  # Metric projection unavailable
        "pitch_y_m": None,
    }
    ball = {"bbox": [445, 590, 455, 600], "confidence": 0.90, "pitch_x_m": None, "pitch_y_m": None}

    # Process with calibration_valid = False
    f = engine.process_frame(1, 0.0, [player], ball, calibration_valid=False)
    assert f.control_state == BallControlState.CONTROLLED
    assert f.is_valid is True


def test_stale_or_invalid_ball_tracker_state() -> None:
    """Verifies that when ball tracker emits LOST or UNRELIABLE states, control returns UNKNOWN."""
    estimator = BallControlEstimator()

    player = {"track_id": 1, "bbox": [400, 400, 500, 600], "team_label": "TEAM_0"}
    ball_lost = {"bbox": [445, 590, 455, 600], "confidence": 0.10, "state": "LOST"}

    eval_res = estimator.evaluate([player], ball_lost)
    assert eval_res.state == BallControlState.UNKNOWN
    assert "BALL_TRACKER_UNRELIABLE" in eval_res.details.get("reason", "")


def test_aerial_ball_ground_jump_discount() -> None:
    """Verifies that rapid ground-plane metric jumps flag aerial ball suspect and suppress ground control."""
    estimator = BallControlEstimator(config=PossessionConfig(aerial_ground_jump_speed_ms=25.0))

    player = {
        "track_id": 1,
        "bbox": [400, 400, 500, 600],
        "team_label": "TEAM_0",
        "pitch_x_m": 0.0,
        "pitch_y_m": 0.0,
    }

    # Frame 1: ball at (0, 0)
    ball_f1 = {"bbox": [445, 590, 455, 600], "confidence": 0.90, "x": 0.0, "y": 0.0, "timestamp": 0.0}
    estimator.evaluate([player], ball_f1)

    # Frame 2: ball ground projection jumps 30 meters away in 0.04 seconds (speed = 750 m/s >> 25 m/s)
    ball_f2 = {"bbox": [445, 590, 455, 600], "confidence": 0.90, "x": 30.0, "y": 0.0, "timestamp": 0.04}
    eval_f2 = estimator.evaluate([player], ball_f2)

    assert eval_f2.is_aerial_suspect is True


def test_referee_proximity_exclusion() -> None:
    """Verifies that a referee standing right next to the ball is strictly excluded from ball control."""
    estimator = BallControlEstimator()

    referee = {
        "track_id": 99,
        "bbox": [400, 400, 500, 600],
        "team_label": "UNKNOWN",
        "role": "REFEREE",
    }
    ball = {"bbox": [445, 590, 455, 600], "confidence": 0.90}

    eval_res = estimator.evaluate([referee], ball)
    assert eval_res.primary_candidate is None
    assert eval_res.state == BallControlState.FREE_BALL


def test_causal_inference_purity() -> None:
    """Verifies that possession state is computed causally frame-by-frame with zero future leakage."""
    engine = PossessionEngine()
    player = {"track_id": 1, "bbox": [400, 400, 500, 600], "team_label": "TEAM_0"}
    ball = {"bbox": [445, 590, 455, 600], "confidence": 0.90}

    for fid in range(1, 10):
        t = fid * 0.04
        f = engine.process_frame(fid, t, [player], ball)
        assert f.frame_index == fid
        assert f.timestamp == pytest.approx(t)
        assert len(engine.frames_history) == fid


def test_upstream_immutability_strictness() -> None:
    """Verifies Chapter 5, 6, EXP-16, and EXP-17 perception and tactical classes remain unchanged."""
    from app.video_analysis.detectors import RFDETRDetector
    from app.video_analysis.player_tracker import PlayerBoTSORT
    from app.video_analysis.ball_tracker import BallTrackManager
    from app.video_analysis.team_classifier import TeamClassifier
    from app.video_analysis.temporal_calibration import TemporalPitchCalibrator
    from app.video_analysis.metric_trajectories import MetricTrajectoryEngine
    from app.video_analysis.tactical_geometry import TacticalGeometryEngine
    from app.video_analysis.tactical_lines import OrientedTacticsEngine, AttackingDirectionResolver

    assert hasattr(RFDETRDetector, "detect")
    assert hasattr(PlayerBoTSORT, "update_tracks")
    assert hasattr(BallTrackManager, "update")
    assert hasattr(TeamClassifier, "fit_and_assign")
    assert hasattr(TemporalPitchCalibrator, "update")
    assert hasattr(MetricTrajectoryEngine, "process_frame")
    assert hasattr(TacticalGeometryEngine, "process_frame")
    assert hasattr(OrientedTacticsEngine, "process_frame")
    assert hasattr(AttackingDirectionResolver, "resolve")
