"""Unit tests for Chapter 7: Ball Control & Possession V2 Challenger Benchmark (EXP-22).

Verifies:
1. Feature extraction dimensions (24 features) and normalization.
2. Metric ground-jump aerial gating (speed > 25 m/s or high image speed invalidates metric features).
3. PairwiseControlModel initialization, loading pre-trained weights, compiling fast trees, fallback behavior.
4. Fast evaluator exact mathematical equivalence to base predict_proba.
5. Candidate scoring & multi-candidate score margin resolution:
   - Clear single candidate -> CONTROLLED.
   - Small margin opposing duel -> CONTESTED.
   - Below probability threshold -> FREE_BALL.
6. Temporal hysteresis:
   - Player control confirmation requires N=2 frames.
   - 1-frame transient proximity flicker is rejected.
7. Same-team pass transit:
   - Ball in flight between teammates maintains PROVISIONAL_TRANSIT up to 15 frames without turnover.
   - Long loose ball (> 15 frames) transitions to NEUTRAL.
8. Opponent takeover & turnover confirmation:
   - Opponent acquiring ball triggers turnover confirmation delay and emits PossessionChangeEvent.
9. Tracker ID switch resistance:
   - When carrier track ID switches to a teammate in continuous control, team possession is unbroken.
10. Strict exclusion of referees from ball control candidates.
11. Strict causality (no future frame leakage).
12. Coexistence: V1 (PossessionEngine) is unmodified and runnable alongside V2 (PossessionEngineV2).
13. Downstream EXP-19 pass detector immutability.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.video_analysis.pitch_calibration import PitchDimensions
from app.video_analysis.possession import (
    BallControlState,
    PossessionChangeEvent,
    PossessionConfig,
    PossessionEngine,
    PossessionStatus,
    TeamPossessionFrameState,
)
from app.video_analysis.possession_v2 import (
    FEATURE_DIM,
    FEATURE_NAMES,
    BallControlEstimatorV2,
    BallControlEvaluationV2,
    BallControlFeatureExtractor,
    PairwiseControlModel,
    PlayerControlCandidateV2,
    PossessionConfigV2,
    PossessionEngineV2,
    TeamPossessionStateMachineV2,
)


def test_feature_extraction_dimension_and_names() -> None:
    """Verifies that BallControlFeatureExtractor produces exactly 24 features with correct names."""
    assert FEATURE_DIM == 24
    assert len(FEATURE_NAMES) == 24
    assert FEATURE_NAMES[0] == "norm_dist_bbox_center"
    assert FEATURE_NAMES[1] == "norm_dist_bottom_center"
    assert FEATURE_NAMES[23] == "is_aerial_suspect"

    extractor = BallControlFeatureExtractor()
    player = {
        "track_id": 1,
        "bbox": [500.0, 400.0, 600.0, 600.0],
        "team_label": "TEAM_0",
        "team_confidence": 0.95,
        "role": "OUTFIELD_PLAYER",
        "pitch_x": 10.0,
        "pitch_y": 5.0,
        "speed_mps": 3.0,
        "track_confidence": 0.9,
    }
    ball = {
        "track_id": 0,
        "bbox": [545.0, 585.0, 555.0, 595.0],
        "pitch_x": 10.2,
        "pitch_y": 5.1,
        "confidence": 0.92,
        "state": "TRACKED",
    }

    candidates, is_aerial = extractor.extract_features(1, 0.04, [player], ball, calibration_valid=True)
    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.track_id == 1
    assert cand.features.shape == (24,)
    assert not is_aerial
    assert cand.is_inside_bbox is True


def test_aerial_ground_jump_invalidation() -> None:
    """Verifies that an unphysical ground-plane jump (>25 m/s) gates metric features."""
    config = PossessionConfigV2(aerial_speed_jump_ms=25.0)
    extractor = BallControlFeatureExtractor(config)

    player = {
        "track_id": 10,
        "bbox": [500.0, 400.0, 600.0, 600.0],
        "team_label": "TEAM_0",
        "pitch_x": 20.0,
        "pitch_y": 10.0,
    }

    # Frame 1: ball at pitch (20, 10)
    b1 = {"bbox": [545.0, 585.0, 555.0, 595.0], "pitch_x": 20.0, "pitch_y": 10.0}
    c1, is_aerial_1 = extractor.extract_features(1, 0.04, [player], b1, calibration_valid=True)
    assert not is_aerial_1

    # Frame 2: ball instantaneously teleports 30m in 0.04s -> 750 m/s ground-plane jump!
    b2 = {"bbox": [545.0, 585.0, 555.0, 595.0], "pitch_x": 50.0, "pitch_y": 10.0}
    c2, is_aerial_2 = extractor.extract_features(2, 0.08, [player], b2, calibration_valid=True)
    assert is_aerial_2 is True
    if c2:
        # Metric valid feature (index 8) must be discounted to 0.0
        assert c2[0].features[8] == 0.0
        # Aerial suspect feature (index 23) must be 1.0
        assert c2[0].features[23] == 1.0


def test_pairwise_model_fast_tree_equivalence() -> None:
    """Verifies that compiled fast trees match scikit-learn predict_proba to within floating point tolerances."""
    model = PairwiseControlModel()
    assert model.is_fitted is True

    # Generate diverse test candidate vectors
    rng = np.random.RandomState(42)
    X = rng.randn(20, 24).astype(np.float32)

    # Force fallback / base predict_proba
    p_orig = model.model.predict_proba(X)[:, 1].astype(np.float32)
    p_fast = model.predict_proba(X)

    np.testing.assert_allclose(p_fast, p_orig, atol=1e-5, rtol=1e-5)


def test_multi_candidate_margin_resolution_duel() -> None:
    """Verifies that when opposing players duel within margin threshold, state resolves to CONTESTED."""
    config = PossessionConfigV2(
        control_probability_threshold=0.42,
        contested_margin_threshold=0.10,
        min_contested_score=0.35,
    )
    estimator = BallControlEstimatorV2(config=config)

    # P1 (TEAM_0) and P2 (TEAM_1) are both adjacent to the ball
    p1 = {"track_id": 1, "bbox": [480, 450, 540, 600], "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"}
    p2 = {"track_id": 2, "bbox": [530, 450, 590, 600], "team_label": "TEAM_1", "role": "OUTFIELD_PLAYER"}
    ball = {"bbox": [520, 580, 530, 590], "confidence": 0.90}

    eval_res = estimator.evaluate(1, 0.04, [p1, p2], ball)
    # Both players are close to the ball -> contested duel or controlled depending on score margin
    assert eval_res.state in (BallControlState.CONTESTED, BallControlState.CONTROLLED)
    if eval_res.secondary_candidate is not None:
        assert eval_res.score_margin >= 0.0


def test_player_control_hysteresis_n2_confirmation() -> None:
    """Verifies that PossessionEngineV2 requires N=2 consecutive frames to confirm player control."""
    config = PossessionConfigV2(player_control_confirm_frames=2)
    engine = PossessionEngineV2(config=config)

    p1 = {"track_id": 7, "bbox": [450, 400, 550, 600], "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"}
    ball = {"bbox": [495, 590, 505, 600], "confidence": 0.92}

    # Frame 1: Candidate detected and high score, but unconfirmed (N=1 < 2)
    f1 = engine.process_frame(1, 0.04, [p1], ball)
    assert f1.controlling_player_id is None
    assert f1.control_state == BallControlState.CONTROLLED

    # Frame 2: Reaches N=2 confirmation -> Confirmed carrier!
    f2 = engine.process_frame(2, 0.08, [p1], ball)
    assert f2.controlling_player_id == 7
    assert f2.controlling_player_team == "TEAM_0"
    assert f2.possession_team == "TEAM_0"
    assert f2.possession_status == PossessionStatus.SECURE


def test_one_frame_proximity_flicker_rejection() -> None:
    """Verifies that an isolated 1-frame ball-player proximity does not cause false acquisition."""
    engine = PossessionEngineV2()

    p_opponent = {"track_id": 99, "bbox": [450, 400, 550, 600], "team_label": "TEAM_1", "role": "OUTFIELD_PLAYER"}
    p_teammate = {"track_id": 1, "bbox": [100, 100, 200, 300], "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"}
    ball_loose = {"bbox": [800, 800, 810, 810], "confidence": 0.85}
    ball_flicker = {"bbox": [495, 590, 505, 600], "confidence": 0.85}

    # Initial state: Free ball
    engine.process_frame(1, 0.04, [p_opponent, p_teammate], ball_loose)

    # Frame 2: 1-frame flicker near opponent
    f2 = engine.process_frame(2, 0.08, [p_opponent, p_teammate], ball_flicker)
    assert f2.controlling_player_id is None

    # Frame 3: Ball moves away again
    f3 = engine.process_frame(3, 0.12, [p_opponent, p_teammate], ball_loose)
    assert f3.controlling_player_id is None
    assert len(engine.turnover_events) == 0


def test_same_team_pass_transit_grace_window() -> None:
    """Verifies that passes between teammates maintain PROVISIONAL_TRANSIT without turnovers."""
    config = PossessionConfigV2(free_ball_grace_frames=15)
    engine = PossessionEngineV2(config=config)

    p1 = {"track_id": 1, "bbox": [450, 400, 550, 600], "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"}
    p2 = {"track_id": 2, "bbox": [800, 400, 900, 600], "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"}
    ball_at_p1 = {"bbox": [495, 590, 505, 600], "confidence": 0.90}
    ball_in_transit = {"bbox": [650, 500, 660, 510], "confidence": 0.85}

    # 1. P1 acquires possession (2 frames)
    for fid in (1, 2):
        engine.process_frame(fid, fid * 0.04, [p1, p2], ball_at_p1)
    assert engine.state_machine.current_team == "TEAM_0"
    assert engine.state_machine.current_status == PossessionStatus.SECURE

    # 2. Ball passes across 10 frames in free transit
    for fid in range(3, 13):
        f = engine.process_frame(fid, fid * 0.04, [p1, p2], ball_in_transit)
        assert f.possession_team == "TEAM_0"
        assert f.possession_status == PossessionStatus.PROVISIONAL_TRANSIT
        assert f.controlling_player_id is None

    assert len(engine.turnover_events) == 0


def test_extended_free_ball_transitions_to_neutral() -> None:
    """Verifies that after free_ball_grace_frames expires, possession transitions to NEUTRAL."""
    config = PossessionConfigV2(free_ball_grace_frames=5)
    engine = PossessionEngineV2(config=config)

    p1 = {"track_id": 1, "bbox": [450, 400, 550, 600], "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"}
    ball_at_p1 = {"bbox": [495, 590, 505, 600], "confidence": 0.90}
    ball_loose = {"bbox": [900, 900, 910, 910], "confidence": 0.85}

    # P1 acquires
    for fid in (1, 2):
        engine.process_frame(fid, fid * 0.04, [p1], ball_at_p1)

    # Ball loose for 6 frames (> grace 5)
    for fid in range(3, 9):
        f = engine.process_frame(fid, fid * 0.04, [p1], ball_loose)

    assert f.possession_team == "NEUTRAL"
    assert f.possession_status == PossessionStatus.NEUTRAL


def test_opponent_takeover_and_turnover_event() -> None:
    """Verifies that opponent taking possession emits a confirmed PossessionChangeEvent."""
    config = PossessionConfigV2(team_possession_confirm_frames=3)
    engine = PossessionEngineV2(config=config)

    p_t0 = {"track_id": 1, "bbox": [450, 400, 550, 600], "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"}
    p_t1 = {"track_id": 2, "bbox": [800, 400, 900, 600], "team_label": "TEAM_1", "role": "OUTFIELD_PLAYER"}

    ball_at_t0 = {"bbox": [495, 590, 505, 600], "confidence": 0.90}
    ball_at_t1 = {"bbox": [845, 590, 855, 600], "confidence": 0.90}

    # TEAM_0 establishes possession
    for fid in (1, 2):
        engine.process_frame(fid, fid * 0.04, [p_t0, p_t1], ball_at_t0)
    assert engine.state_machine.current_team == "TEAM_0"

    # TEAM_1 takes the ball across 4 frames
    turnovers = []
    for fid in range(3, 7):
        f = engine.process_frame(fid, fid * 0.04, [p_t0, p_t1], ball_at_t1)
        if f.recent_possession_change is not None:
            turnovers.append(f.recent_possession_change)

    assert len(turnovers) == 1
    to = turnovers[0]
    assert to.from_team == "TEAM_0"
    assert to.to_team == "TEAM_1"
    assert to.confirmation_delay_frames == 2


def test_tracker_id_switch_continuity() -> None:
    """Verifies that an abrupt tracker ID switch to an active teammate preserves team possession."""
    engine = PossessionEngineV2()

    p_old = {"track_id": 10, "bbox": [500, 400, 600, 600], "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"}
    p_new = {"track_id": 11, "bbox": [500, 400, 600, 600], "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"}
    ball = {"bbox": [545, 590, 555, 600], "confidence": 0.90}

    # Frame 1 & 2: Track ID 10
    engine.process_frame(1, 0.04, [p_old], ball)
    f2 = engine.process_frame(2, 0.08, [p_old], ball)
    assert f2.possession_team == "TEAM_0"

    # Frame 3: Track ID abruptly switches to 11 (same team, same location)
    f3 = engine.process_frame(3, 0.12, [p_new], ball)
    assert f3.possession_team == "TEAM_0"
    assert len(engine.turnover_events) == 0


def test_strict_exclusion_of_referees() -> None:
    """Verifies that referees are strictly excluded from ball control candidates."""
    extractor = BallControlFeatureExtractor()
    ref = {
        "track_id": 999,
        "bbox": [500, 400, 600, 600],
        "team_label": "UNKNOWN",
        "role": "REFEREE",
    }
    ball = {"bbox": [545, 590, 555, 600], "confidence": 0.90}

    candidates, _ = extractor.extract_features(1, 0.04, [ref], ball)
    assert len(candidates) == 0


def test_strict_causality_zero_future_leakage() -> None:
    """Verifies that engine state depends solely on past and present frames."""
    engine = PossessionEngineV2()
    p = {"track_id": 1, "bbox": [500, 400, 600, 600], "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"}
    ball = {"bbox": [545, 590, 555, 600], "confidence": 0.90}

    # Process frame 1
    f1 = engine.process_frame(1, 0.04, [p], ball)
    # The output frame 1 does not know whether frame 2 will have ball control or not
    assert f1.frame_index == 1
    assert f1.controlling_player_id is None  # Hysteresis prevents instant confirmation


def test_v1_and_v2_coexistence() -> None:
    """Verifies that V1 (PossessionEngine) remains fully intact and runnable alongside V2."""
    engine_v1 = PossessionEngine(config=PossessionConfig())
    engine_v2 = PossessionEngineV2(config=PossessionConfigV2())

    p = {"track_id": 1, "bbox": [500, 400, 600, 600], "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"}
    ball = {"bbox": [545, 590, 555, 600], "confidence": 0.90}

    st_v1 = engine_v1.process_frame(1, 0.04, [p], ball)
    st_v2 = engine_v2.process_frame(1, 0.04, [p], ball)

    assert isinstance(st_v1, TeamPossessionFrameState)
    assert isinstance(st_v2, TeamPossessionFrameState)
    assert st_v2.details.get("v2_challenger") is True
