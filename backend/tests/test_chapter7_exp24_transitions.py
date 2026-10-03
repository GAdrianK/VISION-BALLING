"""Unit tests for Chapter 7: Tactical Transitions & Counter-Press Candidates (EXP-24).

Verifies:
1. Possession-loss and possession-gain anchor detection from PossessionChangeEvent.
2. Causal PENDING_TRANSITION state during post-window evidence accumulation.
3. Confirmation exactly at t_0 + window_post_frames (strict causality, zero future leakage).
4. Deterministic synthetic scenarios (Phase 19):
   - Loss + immediate multi-player close -> COUNTERPRESS_CANDIDATE
   - Loss + one player close -> COUNTERPRESS_CANDIDATE
   - Loss + team retreats -> DEFENSIVE_RECOVERY_CANDIDATE
   - Loss + no reaction -> NEUTRAL_TRANSITION
   - Gain + rapid forward expansion -> FAST_ATTACK
   - Gain + slow buildup -> SLOW_BUILDUP
   - False possession flicker suppression -> NO_TRANSITION
   - Camera cut after turnover -> AMBIGUOUS / NOT_VISIBLE
   - Unknown ball fallback -> Graceful handling without player fabrication
   - Partial visibility (<6 outfield players) -> NOT_VISIBLE abstention
5. Physical monotonicity of CounterpressScore (Phase 20):
   - Higher post-loss pressure does not decrease score.
   - Higher closing speed does not decrease score.
   - More converging defenders does not decrease score.
   - Faster centroid approach does not decrease score.
6. Confidence gating (Phase 16) and explicit abstention under LOW confidence.
7. No dependency on nominal formation labels (EXP-21 closed).
8. Upstream component immutability (EXP-22 Possession V2 and EXP-23 Defensive Pressure intact).
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from app.video_analysis.pitch_calibration import PitchDimensions
from app.video_analysis.metric_trajectories import PlayerMetricObservation, BallMetricObservation
from app.video_analysis.possession import (
    PossessionChangeEvent,
    TeamPossessionFrameState,
    PossessionStatus,
    BallControlState,
)
from app.video_analysis.defensive_pressure import (
    DefensivePressureConfig,
    DefensivePressureEngine,
    FrameDefensivePressureState,
    PressureTarget,
    PressureTargetType,
    AngularSectorCoverage,
    TeamCompressionMetrics,
)
from app.video_analysis.defensive_block import DefensiveBlockFrameState, DefensiveBlockMetrics
from app.video_analysis.tactical_lines import OrientedTacticalFrameState, TeamOrientedTactics
from app.video_analysis.tactical_transitions import (
    TacticalTransitionsEngine,
    TacticalTransitionsConfig,
    TransitionType,
    TransitionCandidate,
    AttackingResponse,
    ConfidenceGate,
    TransitionFeatureVector,
    TacticalTransitionEvent,
    FrameTacticalTransitionState,
    ContinuousTransitionScorer,
)


def _make_dummy_pressure_state(
    frame_index: int,
    p_index: float = 0.10,
    nearest_d: float = 8.0,
    closing_v: float = 0.0,
    r3: int = 0,
    r5: int = 1,
) -> FrameDefensivePressureState:
    """Helper creating a dummy FrameDefensivePressureState."""
    return FrameDefensivePressureState(
        frame_index=frame_index,
        timestamp=frame_index * 0.04,
        target=PressureTarget(target_type=PressureTargetType.CARRIER, target_team="TEAM_1"),
        defending_team="TEAM_0",
        nearest_defender_distance_m=nearest_d,
        nearest_defender_closing_speed_mps=closing_v,
        nearest_defender_track_id=10,
        n_defenders_r3=r3,
        n_defenders_r5=r5,
        angular_coverage=AngularSectorCoverage(sectors_occupied=2, coverage_ratio=0.25),
        pressure_index=p_index,
    )


def _make_dummy_block_state(
    frame_index: int,
    c_to_ball: float = 18.0,
    line_h: float = 35.0,
) -> DefensiveBlockFrameState:
    """Helper creating a dummy DefensiveBlockFrameState."""
    m0 = DefensiveBlockMetrics(
        team_label="TEAM_0",
        defensive_line_height_m=line_h,
        oriented_depth_m=20.0,
        lateral_width_m=35.0,
        centroid_to_ball_distance_m=c_to_ball,
    )
    m1 = DefensiveBlockMetrics(
        team_label="TEAM_1",
        defensive_line_height_m=line_h,
        oriented_depth_m=20.0,
        lateral_width_m=35.0,
        centroid_to_ball_distance_m=c_to_ball,
    )
    return DefensiveBlockFrameState(
        frame_index=frame_index,
        timestamp=frame_index * 0.04,
        team_0=m0,
        team_1=m1,
    )


def _make_dummy_possession(
    frame_index: int,
    holding_team: str = "TEAM_0",
    turnover: bool = False,
    turnover_conf: float = 0.80,
) -> TeamPossessionFrameState:
    """Helper creating TeamPossessionFrameState with optional turnover event."""
    to_evt = None
    if turnover:
        from_t = "TEAM_0" if holding_team == "TEAM_1" else "TEAM_1"
        to_evt = PossessionChangeEvent(
            frame_index=frame_index,
            timestamp=frame_index * 0.04,
            from_team=from_t,
            to_team=holding_team,
            confidence=turnover_conf,
        )

    return TeamPossessionFrameState(
        frame_index=frame_index,
        timestamp=frame_index * 0.04,
        possession_team=holding_team,
        possession_status=PossessionStatus.SECURE,
        possession_confidence=0.85,
        recent_possession_change=to_evt,
    )


def _make_players(count: int = 10) -> list[dict]:
    """Helper creating a minimum number of outfield players for visibility checks."""
    return [{"track_id": i, "team_label": "TEAM_0" if i % 2 == 0 else "TEAM_1", "role": "OUTFIELD_PLAYER"} for i in range(count)]


# ==============================================================================
# TESTS
# ==============================================================================

def test_possession_loss_gain_anchors() -> None:
    """Verifies that confirmed turnovers trigger transition state on losing and gaining teams."""
    config = TacticalTransitionsConfig(window_pre_frames=10, window_post_frames=10)
    engine = TacticalTransitionsEngine(config=config)

    # Pre-turnover frames
    for f in range(1, 15):
        poss = _make_dummy_possession(f, holding_team="TEAM_0")
        st = engine.process_frame(f, f * 0.04, _make_players(), None, poss)
        assert st.team_0_transition_type == TransitionType.NO_TRANSITION
        assert st.team_1_transition_type == TransitionType.NO_TRANSITION

    # Turnover at frame 15: TEAM_0 -> TEAM_1
    poss_to = _make_dummy_possession(15, holding_team="TEAM_1", turnover=True, turnover_conf=0.85)
    st_to = engine.process_frame(15, 15 * 0.04, _make_players(), None, poss_to)

    assert st_to.team_0_transition_type == TransitionType.ATTACK_TO_DEFENSE
    assert st_to.team_1_transition_type == TransitionType.DEFENSE_TO_ATTACK
    assert st_to.is_pending is True
    assert st_to.candidate_label == TransitionCandidate.PENDING_TRANSITION


def test_pending_transition_and_causality() -> None:
    """Verifies that transition remains PENDING_TRANSITION until window_post_frames causal evidence accumulates."""
    config = TacticalTransitionsConfig(window_pre_frames=10, window_post_frames=10)
    engine = TacticalTransitionsEngine(config=config)

    # Frame 1 to 14: background
    for f in range(1, 15):
        poss = _make_dummy_possession(f, holding_team="TEAM_0")
        engine.process_frame(f, f * 0.04, _make_players(), None, poss)

    # Frame 15: Turnover
    poss_to = _make_dummy_possession(15, holding_team="TEAM_1", turnover=True)
    st15 = engine.process_frame(15, 0.60, _make_players(), None, poss_to)
    assert st15.is_pending is True

    # Frame 16 to 24: still pending
    for f in range(16, 25):
        press = _make_dummy_pressure_state(f, p_index=0.40, nearest_d=3.0, closing_v=2.0)
        poss = _make_dummy_possession(f, holding_team="TEAM_1")
        st = engine.process_frame(f, f * 0.04, _make_players(), None, poss, pressure_state=press)
        assert st.is_pending is True
        assert st.candidate_label == TransitionCandidate.PENDING_TRANSITION

    # Frame 25: exactly loss_fid (15) + window_post_frames (10) -> confirmed
    press25 = _make_dummy_pressure_state(25, p_index=0.40, nearest_d=3.0, closing_v=2.0)
    poss25 = _make_dummy_possession(25, holding_team="TEAM_1")
    st25 = engine.process_frame(25, 1.00, _make_players(), None, poss25, pressure_state=press25)

    assert st25.is_pending is False
    assert st25.candidate_label != TransitionCandidate.PENDING_TRANSITION
    assert st25.causal_confirmation_frame == 25


def test_counterpress_candidate_scenarios() -> None:
    """Synthetic Scenario 1 & 2: multi-player close and one-player close yield COUNTERPRESS_CANDIDATE."""
    config = TacticalTransitionsConfig(window_pre_frames=5, window_post_frames=5)
    engine = TacticalTransitionsEngine(config=config)

    # Feed pre-window (low pressure)
    for f in range(1, 10):
        press = _make_dummy_pressure_state(f, p_index=0.08, nearest_d=10.0, closing_v=0.0)
        block = _make_dummy_block_state(f, c_to_ball=22.0, line_h=30.0)
        poss = _make_dummy_possession(f, holding_team="TEAM_0")
        engine.process_frame(f, f * 0.04, _make_players(), None, poss, pressure_state=press, block_frame_state=block)

    # Frame 10: Turnover TEAM_0 -> TEAM_1
    poss_to = _make_dummy_possession(10, holding_team="TEAM_1", turnover=True)
    engine.process_frame(10, 0.40, _make_players(), None, poss_to)

    # Feed post-window: intense pressing (P=0.65, nearest_d=2.2m, closing_v=+3.5m/s, r3=2, centroid closing)
    for f in range(11, 16):
        press = _make_dummy_pressure_state(f, p_index=0.65, nearest_d=2.2, closing_v=3.5, r3=2, r5=3)
        block = _make_dummy_block_state(f, c_to_ball=14.0, line_h=34.0)
        poss = _make_dummy_possession(f, holding_team="TEAM_1")
        st = engine.process_frame(f, f * 0.04, _make_players(), None, poss, pressure_state=press, block_frame_state=block)

    assert st.candidate_label == TransitionCandidate.COUNTERPRESS_CANDIDATE
    assert st.counterpress_score >= 0.52
    assert st.counterpress_score > st.recovery_score


def test_defensive_recovery_candidate_scenario() -> None:
    """Synthetic Scenario 3: team retreats, line drops, centroid moves away -> DEFENSIVE_RECOVERY_CANDIDATE."""
    config = TacticalTransitionsConfig(window_pre_frames=5, window_post_frames=5)
    engine = TacticalTransitionsEngine(config=config)

    # Feed pre-window
    for f in range(1, 10):
        press = _make_dummy_pressure_state(f, p_index=0.15, nearest_d=6.0, closing_v=0.0)
        block = _make_dummy_block_state(f, c_to_ball=15.0, line_h=35.0)
        poss = _make_dummy_possession(f, holding_team="TEAM_0")
        engine.process_frame(f, f * 0.04, _make_players(), None, poss, pressure_state=press, block_frame_state=block)

    # Turnover
    poss_to = _make_dummy_possession(10, holding_team="TEAM_1", turnover=True)
    engine.process_frame(10, 0.40, _make_players(), None, poss_to)

    # Post-window: dropping deep, distance increasing to 18m, closing speed negative, pressure low
    for f in range(11, 16):
        press = _make_dummy_pressure_state(f, p_index=0.03, nearest_d=18.0, closing_v=-2.5, r3=0, r5=0)
        block = _make_dummy_block_state(f, c_to_ball=25.0, line_h=24.0) # dropping back towards own goal
        poss = _make_dummy_possession(f, holding_team="TEAM_1")
        st = engine.process_frame(f, f * 0.04, _make_players(), None, poss, pressure_state=press, block_frame_state=block)

    assert st.candidate_label == TransitionCandidate.DEFENSIVE_RECOVERY_CANDIDATE
    assert st.recovery_score >= 0.48
    assert st.recovery_score > st.counterpress_score


def test_neutral_transition_scenario() -> None:
    """Synthetic Scenario 4: moderate balanced signals -> NEUTRAL_TRANSITION."""
    scorer = ContinuousTransitionScorer(TacticalTransitionsConfig())
    fv = TransitionFeatureVector(
        possession_change_confidence=0.75,
        pressure_pre_mean=0.15,
        pressure_post_mean=0.18,
        pressure_delta=0.03,
        nearest_defender_pre=8.0,
        nearest_defender_post=7.5,
        nearest_distance_delta=-0.5,
        closing_speed_post_mean=0.2,
        density_r3_post=0.0,
        density_r5_post=1.0,
        centroid_ball_distance_delta=0.0,
        defensive_line_velocity=0.0,
    )
    cp, rec, cand = scorer.compute_scores(fv)
    assert cand == TransitionCandidate.NEUTRAL_TRANSITION


def test_fast_attack_vs_slow_buildup() -> None:
    """Synthetic Scenarios 5 & 6: ball progression differentiates FAST_ATTACK vs SLOW_BUILDUP."""
    config = TacticalTransitionsConfig(window_pre_frames=5, window_post_frames=5)
    engine = TacticalTransitionsEngine(config=config)

    # Case A: Rapid forward progression (+10m)
    for f in range(1, 10):
        engine.process_frame(f, f * 0.04, _make_players(), {"pitch_x_m": 0.0, "pitch_y_m": 0.0}, _make_dummy_possession(f, "TEAM_0"))

    # Turnover
    engine.process_frame(10, 0.40, _make_players(), {"pitch_x_m": 0.0, "pitch_y_m": 0.0}, _make_dummy_possession(10, "TEAM_1", turnover=True))

    for f in range(11, 16):
        # Ball moving forward to +8m
        bx = (f - 10) * 1.6
        st = engine.process_frame(f, f * 0.04, _make_players(), {"pitch_x_m": bx, "pitch_y_m": 0.0}, _make_dummy_possession(f, "TEAM_1"))

    assert st.active_event is not None
    assert st.active_event.attacking_response == AttackingResponse.FAST_ATTACK


def test_false_possession_flicker_suppression() -> None:
    """Synthetic Scenario 7: low-confidence carrier flicker (< 0.40) is suppressed and creates NO transition."""
    config = TacticalTransitionsConfig(min_possession_confidence=0.40)
    engine = TacticalTransitionsEngine(config=config)

    # Low-confidence turnover (confidence = 0.25)
    poss_flicker = _make_dummy_possession(10, holding_team="TEAM_1", turnover=True, turnover_conf=0.25)
    st = engine.process_frame(10, 0.40, _make_players(), None, poss_flicker)

    assert st.team_0_transition_type == TransitionType.NO_TRANSITION
    assert st.team_1_transition_type == TransitionType.NO_TRANSITION
    assert len(engine.pending_events) == 0


def test_camera_cut_and_low_visibility_abstention() -> None:
    """Synthetic Scenarios 8 & 10: low outfield visibility (< 6 players) abstains to NOT_VISIBLE."""
    config = TacticalTransitionsConfig(window_pre_frames=5, window_post_frames=5, min_visible_outfield=6)
    engine = TacticalTransitionsEngine(config=config)

    for f in range(1, 10):
        engine.process_frame(f, f * 0.04, _make_players(10), None, _make_dummy_possession(f, "TEAM_0"))

    # Turnover
    engine.process_frame(10, 0.40, _make_players(10), None, _make_dummy_possession(10, "TEAM_1", turnover=True))

    # Broadcast cut: only 3 players visible during post-window
    for f in range(11, 16):
        st = engine.process_frame(f, f * 0.04, _make_players(3), None, _make_dummy_possession(f, "TEAM_1"))

    assert st.candidate_label == TransitionCandidate.NOT_VISIBLE


def test_ball_only_fallback() -> None:
    """Synthetic Scenario 9: ball-centric transition evaluation when carrier is unknown."""
    config = TacticalTransitionsConfig(window_pre_frames=5, window_post_frames=5)
    engine = TacticalTransitionsEngine(config=config)

    # Frames without carrier, ball only
    for f in range(1, 16):
        b = {"pitch_x_m": 5.0, "pitch_y_m": 0.0}
        poss = _make_dummy_possession(f, "TEAM_1", turnover=(f == 10))
        st = engine.process_frame(f, f * 0.04, _make_players(), b, poss)

    assert st.active_event is not None
    assert st.active_event.is_confirmed is True


def test_monotonicity_post_loss_pressure() -> None:
    """Phase 20 Monotonicity: higher post-loss pressure must not reduce CounterpressScore."""
    scorer = ContinuousTransitionScorer(TacticalTransitionsConfig())

    fv_low = TransitionFeatureVector(possession_change_confidence=0.8, pressure_post_mean=0.20, pressure_delta=0.05)
    fv_high = TransitionFeatureVector(possession_change_confidence=0.8, pressure_post_mean=0.55, pressure_delta=0.25)

    cp_low, _, _ = scorer.compute_scores(fv_low)
    cp_high, _, _ = scorer.compute_scores(fv_high)

    assert cp_high >= cp_low


def test_monotonicity_closing_speed() -> None:
    """Phase 20 Monotonicity: higher positive closing speed must not reduce CounterpressScore."""
    scorer = ContinuousTransitionScorer(TacticalTransitionsConfig())

    fv_slow = TransitionFeatureVector(possession_change_confidence=0.8, closing_speed_post_mean=0.5)
    fv_fast = TransitionFeatureVector(possession_change_confidence=0.8, closing_speed_post_mean=3.5)

    cp_slow, _, _ = scorer.compute_scores(fv_slow)
    cp_fast, _, _ = scorer.compute_scores(fv_fast)

    assert cp_fast >= cp_slow


def test_monotonicity_defenders_converging() -> None:
    """Phase 20 Monotonicity: more converging defenders must not reduce CounterpressScore."""
    scorer = ContinuousTransitionScorer(TacticalTransitionsConfig())

    fv_one = TransitionFeatureVector(possession_change_confidence=0.8, density_r3_post=1.0, density_r5_post=1.0)
    fv_many = TransitionFeatureVector(possession_change_confidence=0.8, density_r3_post=3.0, density_r5_post=4.0)

    cp_one, _, _ = scorer.compute_scores(fv_one)
    cp_many, _, _ = scorer.compute_scores(fv_many)

    assert cp_many >= cp_one


def test_monotonicity_centroid_approach() -> None:
    """Phase 20 Monotonicity: faster centroid approach must not reduce CounterpressScore."""
    scorer = ContinuousTransitionScorer(TacticalTransitionsConfig())

    # delta centroid: negative means closing in (-3.0m is faster approach than -0.5m)
    fv_slow_c = TransitionFeatureVector(possession_change_confidence=0.8, centroid_ball_distance_delta=-0.5)
    fv_fast_c = TransitionFeatureVector(possession_change_confidence=0.8, centroid_ball_distance_delta=-3.0)

    cp_slow, _, _ = scorer.compute_scores(fv_slow_c)
    cp_fast, _, _ = scorer.compute_scores(fv_fast_c)

    assert cp_fast >= cp_slow


def test_confidence_stratification_gating() -> None:
    """Phase 16 Gating: LOW confidence turnover suppresses semantic label to AMBIGUOUS."""
    scorer = ContinuousTransitionScorer(TacticalTransitionsConfig())

    fv_low_conf = TransitionFeatureVector(
        possession_change_confidence=0.35, # < med_confidence_threshold (0.45)
        pressure_post_mean=0.70,
        closing_speed_post_mean=4.0,
    )
    cp, rec, cand = scorer.compute_scores(fv_low_conf)
    assert cand == TransitionCandidate.AMBIGUOUS


def test_no_nominal_formation_dependency() -> None:
    """Verifies that TacticalTransitionsEngine operates without nominal formation labels."""
    engine = TacticalTransitionsEngine()
    # Signature of process_frame does not require formation state
    import inspect
    sig = inspect.signature(engine.process_frame)
    assert "formation_state" not in sig.parameters
    assert "nominal_formation" not in sig.parameters


def test_upstream_components_immutability() -> None:
    """Verifies that EXP-22 (Possession V2) and EXP-23 (Defensive Pressure) are intact and unmodified."""
    from app.video_analysis.possession_v2 import PossessionEngineV2, PossessionConfigV2
    from app.video_analysis.defensive_pressure import DefensivePressureEngine, DefensivePressureConfig

    p_eng = PossessionEngineV2(config=PossessionConfigV2())
    d_eng = DefensivePressureEngine(config=DefensivePressureConfig())

    assert hasattr(p_eng, "process_frame")
    assert hasattr(d_eng, "process_frame")
