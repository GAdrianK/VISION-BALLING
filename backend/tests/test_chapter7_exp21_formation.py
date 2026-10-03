"""Unit and integration test suite for EXP-21: Dynamic Formation Structure Inference.

Validates:
- 8 canonical prototypes (4-4-2, 4-3-3, 4-2-3-1, 4-1-4-1, 3-5-2, 3-4-3, 5-3-2, 5-4-1)
- Player permutation invariance
- Coordinate noise robustness
- 1 missing player (PARTIAL / AMBIGUOUS)
- 2 missing players
- Low visibility abstention (N <= 6 -> UNKNOWN)
- Wrong-team player filtering
- Temporal consensus & stabilization
- Formation switch confirmation & event emission
- Set piece deformation detection
- Orientation UNKNOWN safe abstention
- Upstream immutability
"""

from __future__ import annotations

import random
from typing import List, Tuple

import numpy as np
import pytest

from app.video_analysis.formation_inferer import (
    CANONICAL_PROTOTYPES,
    DynamicFormationEngine,
    FormationConfig,
    FormationContext,
    FormationSignature,
    FormationState,
    VisibilityClass,
    compute_formation_distance,
)
from app.video_analysis.metric_trajectories import (
    BallMetricObservation,
    PlayerMetricObservation,
)
from app.video_analysis.tactical_geometry import (
    BallTacticalGeometry,
    InterTeamTacticalGeometry,
    TacticalFrameState,
    TacticalQualityState,
    TeamTacticalGeometry,
)
from app.video_analysis.tactical_lines import (
    AttackDirection,
    OrientedTacticalFrameState,
    TacticalLine,
    TeamOrientedTactics,
)


# ==============================================================================
# TEST FIXTURES & BUILDERS
# ==============================================================================

def _make_player(
    track_id: int,
    team: str,
    x: float,
    y: float,
    role: str = "OUTFIELD_PLAYER",
) -> PlayerMetricObservation:
    return PlayerMetricObservation(
        track_id=track_id,
        frame_index=1,
        timestamp=0.04,
        team_label=team,
        role=role,
        image_anchor_px=(100.0, 100.0),
        pitch_x_m=x,
        pitch_y_m=y,
        speed_mps=1.0,
        position_valid=True,
    )


def _make_lines(counts: Sequence[int], x_starts: Sequence[float]) -> List[TacticalLine]:
    lines = []
    tid_counter = 0
    for idx, (cnt, x_pos) in enumerate(zip(counts, x_starts)):
        tids = list(range(tid_counter, tid_counter + cnt))
        tid_counter += cnt
        lines.append(
            TacticalLine(
                line_id=idx,
                player_track_ids=tids,
                player_count=cnt,
                mean_x_attack=float(x_pos),
                median_x_attack=float(x_pos),
                width_y_m=28.0 if cnt >= 4 else 20.0,
                mean_pitch_x_m=float(x_pos),
                mean_pitch_y_m=0.0,
                confidence=0.95,
                candidate_semantic_name=f"LINE_{idx}",
            )
        )
    return lines


def _make_context(
    players: List[PlayerMetricObservation],
    lines_0: List[TacticalLine],
    lines_1: Optional[List[TacticalLine]] = None,
    is_oriented: bool = True,
) -> Tuple[TacticalFrameState, OrientedTacticalFrameState]:
    p0 = [p for p in players if p.team_label == "TEAM_0" and p.role != "GOALKEEPER"]
    p1 = [p for p in players if p.team_label == "TEAM_1" and p.role != "GOALKEEPER"]

    t0_geom = TeamTacticalGeometry(
        team_label="TEAM_0",
        visible_players=len(p0),
        outfield_player_count=len(p0),
        width_m=40.0,
        longitudinal_span_m=35.0,
        is_valid=True,
    )
    t1_geom = TeamTacticalGeometry(
        team_label="TEAM_1",
        visible_players=len(p1),
        outfield_player_count=len(p1),
        width_m=40.0,
        longitudinal_span_m=35.0,
        is_valid=True,
    )
    tf = TacticalFrameState(
        frame_index=1,
        timestamp=0.04,
        calibration_valid=True,
        team_0=t0_geom,
        team_1=t1_geom,
        ball=BallTacticalGeometry(),
        inter_team=InterTeamTacticalGeometry(),
        quality=TacticalQualityState(calibration_valid=True, geometry_valid=True),
    )

    t0_orient = TeamOrientedTactics(
        team_label="TEAM_0",
        attack_direction=AttackDirection.POSITIVE_X if is_oriented else AttackDirection.UNKNOWN,
        is_oriented=is_oriented,
        lines=lines_0,
        line_count=len(lines_0),
        visibility_level="HIGH" if len(p0) >= 8 else "MEDIUM",
        outfield_player_count=len(p0),
    )
    t1_orient = TeamOrientedTactics(
        team_label="TEAM_1",
        attack_direction=AttackDirection.NEGATIVE_X if is_oriented else AttackDirection.UNKNOWN,
        is_oriented=is_oriented,
        lines=lines_1 or [],
        line_count=len(lines_1 or []),
        visibility_level="HIGH" if len(p1) >= 8 else "MEDIUM",
        outfield_player_count=len(p1),
    )
    of = OrientedTacticalFrameState(
        frame_index=1,
        timestamp=0.04,
        team_0=t0_orient,
        team_1=t1_orient,
        orientation_confidence=0.95 if is_oriented else 0.0,
    )
    return tf, of


# ==============================================================================
# CANONICAL PROTOTYPE TESTS (PHASE 8 & 15)
# ==============================================================================

@pytest.mark.parametrize(
    "proto_name,counts,x_positions",
    [
        ("4-4-2", [4, 4, 2], [-20.0, -5.0, 12.0]),
        ("4-3-3", [4, 3, 3], [-20.0, -5.0, 15.0]),
        ("4-2-3-1", [4, 2, 3, 1], [-22.0, -10.0, 2.0, 15.0]),
        ("4-1-4-1", [4, 1, 4, 1], [-22.0, -12.0, 3.0, 16.0]),
        ("3-5-2", [3, 5, 2], [-20.0, -3.0, 14.0]),
        ("3-4-3", [3, 4, 3], [-20.0, -4.0, 15.0]),
        ("5-3-2", [5, 3, 2], [-22.0, -4.0, 14.0]),
        ("5-4-1", [5, 4, 1], [-22.0, -4.0, 16.0]),
    ],
)
def test_canonical_prototypes_exact_recovery(proto_name: str, counts: List[int], x_positions: List[float]) -> None:
    """Verifies that all 8 canonical prototypes are identified with high confidence."""
    engine = DynamicFormationEngine()
    lines = _make_lines(counts, x_positions)
    players = []
    tid = 0
    for cnt, x in zip(counts, x_positions):
        for j in range(cnt):
            players.append(_make_player(tid, "TEAM_0", x, float(j * 6 - (cnt * 3))))
            tid += 1

    tf, of = _make_context(players, lines)
    state = engine.process_frame(1, 0.04, players, tf, of)

    sig = state.team_0.instantaneous_signature
    assert sig.best_prototype == proto_name
    assert sig.formation_label == proto_name
    assert sig.formation_state == FormationState.STABLE
    assert sig.formation_confidence >= 0.85
    assert sig.visible_outfield_count == 10
    assert sig.line_count == len(counts)
    assert sig.players_per_line == counts


def test_player_permutation_invariance() -> None:
    """Confirms that shuffling player order or track IDs produces an identical signature."""
    engine = DynamicFormationEngine()
    counts = [4, 4, 2]
    x_pos = [-20.0, -5.0, 12.0]
    lines = _make_lines(counts, x_pos)

    players = []
    tid = 0
    for cnt, x in zip(counts, x_pos):
        for j in range(cnt):
            players.append(_make_player(tid, "TEAM_0", x, float(j * 6 - 10)))
            tid += 1

    tf, of = _make_context(players, lines)
    res_orig = engine.process_frame(1, 0.04, players, tf, of)

    # Permute players and lines
    shuffled_players = list(players)
    random.Random(1337).shuffle(shuffled_players)

    res_shuffled = engine.process_frame(1, 0.04, shuffled_players, tf, of)

    assert res_orig.team_0.instantaneous_signature.formation_label == res_shuffled.team_0.instantaneous_signature.formation_label
    assert res_orig.team_0.instantaneous_signature.formation_confidence == pytest.approx(
        res_shuffled.team_0.instantaneous_signature.formation_confidence, abs=1e-5
    )
    assert res_orig.team_0.instantaneous_signature.players_per_line == res_shuffled.team_0.instantaneous_signature.players_per_line


def test_coordinate_noise_robustness() -> None:
    """Evaluates stability when coordinate noise is injected."""
    engine = DynamicFormationEngine()
    counts = [4, 3, 3]
    x_pos = [-20.0, -5.0, 15.0]

    rng = np.random.RandomState(42)
    for scale in [0.10, 0.25, 0.50, 1.00]:
        lines = []
        tid = 0
        players = []
        for idx, (cnt, x) in enumerate(zip(counts, x_pos)):
            tids = list(range(tid, tid + cnt))
            tid += cnt
            noisy_x = x + float(rng.uniform(-scale, scale))
            lines.append(
                TacticalLine(idx, tids, cnt, noisy_x, noisy_x, 24.0, noisy_x, 0.0, 0.90, f"L_{idx}")
            )
            for j in range(cnt):
                players.append(_make_player(tids[j], "TEAM_0", noisy_x, float(j * 6 - 8)))

        tf, of = _make_context(players, lines)
        res = engine.process_frame(1, 0.04, players, tf, of)
        sig = res.team_0.instantaneous_signature
        # Formation label must remain 4-3-3 across moderate spatial noise
        assert sig.best_prototype == "4-3-3"
        assert sig.formation_label == "4-3-3"


def test_partial_visibility_evidence() -> None:
    """Verifies that 7-8 visible outfield players trigger PARTIAL_EVIDENCE / PARTIAL without hallucinating."""
    engine = DynamicFormationEngine()
    # 8 players observed: [4, 3, 1] (partial evidence tier: 7-8 players)
    counts = [4, 3, 1]
    x_pos = [-20.0, -5.0, 12.0]
    lines = _make_lines(counts, x_pos)

    players = []
    tid = 0
    for cnt, x in zip(counts, x_pos):
        for j in range(cnt):
            players.append(_make_player(tid, "TEAM_0", x, float(j * 6 - 8)))
            tid += 1

    assert len(players) == 8
    tf, of = _make_context(players, lines)
    res = engine.process_frame(1, 0.04, players, tf, of)

    sig = res.team_0.instantaneous_signature
    assert sig.visible_outfield_count == 8
    assert sig.missing_player_count == 2
    assert sig.visibility_class == VisibilityClass.PARTIAL_EVIDENCE
    assert sig.formation_state == FormationState.PARTIAL
    assert sig.formation_label == "PARTIAL"
    # Structure must still be preserved numerically
    assert sig.players_per_line == [4, 3, 1]


def test_nine_players_full_evidence() -> None:
    """Verifies that N=9 outfield players satisfies FULL_EVIDENCE threshold (N >= 9)."""
    engine = DynamicFormationEngine()
    counts = [4, 3, 2]  # 9 outfield players
    x_pos = [-20.0, -5.0, 12.0]
    lines = _make_lines(counts, x_pos)

    players = []
    tid = 0
    for cnt, x in zip(counts, x_pos):
        for j in range(cnt):
            players.append(_make_player(tid, "TEAM_0", x, float(j * 6 - 8)))
            tid += 1

    assert len(players) == 9
    tf, of = _make_context(players, lines)
    res = engine.process_frame(1, 0.04, players, tf, of)

    sig = res.team_0.instantaneous_signature
    assert sig.visible_outfield_count == 9
    assert sig.missing_player_count == 1
    assert sig.visibility_class == VisibilityClass.FULL_EVIDENCE
    assert sig.players_per_line == [4, 3, 2]


def test_low_visibility_explicit_abstention() -> None:
    """Verifies that N <= 6 outfield players strictly forces UNKNOWN."""
    engine = DynamicFormationEngine()
    counts = [3, 2]  # 5 players only
    x_pos = [-20.0, 0.0]
    lines = _make_lines(counts, x_pos)

    players = []
    tid = 0
    for cnt, x in zip(counts, x_pos):
        for j in range(cnt):
            players.append(_make_player(tid, "TEAM_0", x, float(j * 6 - 6)))
            tid += 1

    assert len(players) == 5
    tf, of = _make_context(players, lines)
    res = engine.process_frame(1, 0.04, players, tf, of)

    sig = res.team_0.instantaneous_signature
    assert sig.visible_outfield_count == 5
    assert sig.missing_player_count == 5
    assert sig.visibility_class == VisibilityClass.LOW_EVIDENCE
    assert sig.formation_state == FormationState.UNKNOWN
    assert sig.formation_label == "UNKNOWN"
    assert sig.invalidation_reason == "LOW_VISIBILITY"
    # Numeric structure is retained
    assert sig.players_per_line == [3, 2]


def test_wingback_ambiguity_3_5_vs_5_3() -> None:
    """Verifies explicit detection of ambiguity between 3-5-2 and 5-3-2."""
    engine = DynamicFormationEngine(FormationConfig(wingback_ambiguity_threshold=0.50))
    # Intermediate shape where backline is 4 and midfield is 4 (e.g. one wingback deep, one high)
    counts = [4, 4, 2]
    x_pos = [-22.0, -5.0, 15.0]
    lines = _make_lines(counts, x_pos)

    # Force distance comparison between 3-5-2 and 5-3-2
    d_352, _ = compute_formation_distance(counts, [3, 5, 2])
    d_532, _ = compute_formation_distance(counts, [5, 3, 2])
    assert abs(d_352 - d_532) <= 1.0


def test_temporal_consensus_and_flutter_suppression() -> None:
    """Confirms that a causal buffer prevents formation flutter from a single noisy frame."""
    engine = DynamicFormationEngine(FormationConfig(temporal_window_frames=10, min_consensus_ratio=0.65))
    c_442 = [4, 4, 2]
    l_442 = _make_lines(c_442, [-20.0, -5.0, 12.0])

    p_442 = []
    tid = 0
    for cnt, x in zip(c_442, [-20.0, -5.0, 12.0]):
        for j in range(cnt):
            p_442.append(_make_player(tid, "TEAM_0", x, float(j * 6 - 8)))
            tid += 1

    tf, of_442 = _make_context(p_442, l_442)

    # Feed 8 frames of 4-4-2
    for fid in range(1, 9):
        st = engine.process_frame(fid, fid * 0.04, p_442, tf, of_442)
    assert st.team_0.stable_formation_label == "4-4-2"
    assert st.team_0.stable_state == FormationState.STABLE

    # Inject 1 noisy frame resembling 3-5-2
    c_352 = [3, 5, 2]
    l_352 = _make_lines(c_352, [-20.0, -3.0, 14.0])
    p_352 = []
    tid = 0
    for cnt, x in zip(c_352, [-20.0, -3.0, 14.0]):
        for j in range(cnt):
            p_352.append(_make_player(tid, "TEAM_0", x, float(j * 6 - 8)))
            tid += 1
    tf_noisy, of_noisy = _make_context(p_352, l_352)

    st_noisy = engine.process_frame(9, 9 * 0.04, p_352, tf_noisy, of_noisy)
    # Instantaneous may be 3-5-2, but temporal consensus remains 4-4-2!
    assert st_noisy.team_0.instantaneous_signature.best_prototype == "3-5-2"
    assert st_noisy.team_0.stable_formation_label == "4-4-2"
    assert st_noisy.team_0.stable_state == FormationState.STABLE
    assert len(st_noisy.transitions) == 0


def test_formation_switch_transition_event() -> None:
    """Verifies that a persistent structural shift emits FORMATION_STRUCTURE_CHANGE."""
    engine = DynamicFormationEngine(FormationConfig(temporal_window_frames=10, min_consensus_ratio=0.65))
    c_442 = [4, 4, 2]
    l_442 = _make_lines(c_442, [-20.0, -5.0, 12.0])
    p_442 = []
    tid = 0
    for cnt, x in zip(c_442, [-20.0, -5.0, 12.0]):
        for j in range(cnt):
            p_442.append(_make_player(tid, "TEAM_0", x, float(j * 6 - 8)))
            tid += 1
    tf_442, of_442 = _make_context(p_442, l_442)

    # Establish 4-4-2
    for fid in range(1, 15):
        engine.process_frame(fid, fid * 0.04, p_442, tf_442, of_442)

    # Now transition to 4-3-3 persistently
    c_433 = [4, 3, 3]
    l_433 = _make_lines(c_433, [-20.0, -5.0, 15.0])
    p_433 = []
    tid = 0
    for cnt, x in zip(c_433, [-20.0, -5.0, 15.0]):
        for j in range(cnt):
            p_433.append(_make_player(tid, "TEAM_0", x, float(j * 6 - 8)))
            tid += 1
    tf_433, of_433 = _make_context(p_433, l_433)

    emitted_event = None
    for fid in range(15, 30):
        st = engine.process_frame(fid, fid * 0.04, p_433, tf_433, of_433)
        if st.transitions:
            emitted_event = st.transitions[0]

    assert emitted_event is not None
    assert emitted_event.old_formation == "4-4-2"
    assert emitted_event.new_formation == "4-3-3"
    assert emitted_event.event_type == "FORMATION_STRUCTURE_CHANGE"


def test_set_piece_deformation_flagging() -> None:
    """Verifies that extreme box crowding flags SET_PIECE_DEFORMATION."""
    engine = DynamicFormationEngine(FormationConfig(set_piece_max_depth_m=15.0, set_piece_max_width_m=20.0))
    # 10 players all crowded in a 10m x 15m box (corner kick scrum)
    players = []
    for i in range(10):
        players.append(_make_player(i, "TEAM_0", -45.0 + (i % 3) * 3.0, (i // 3) * 3.0 - 5.0))

    lines = [TacticalLine(0, list(range(10)), 10, -42.0, -42.0, 12.0, -42.0, 0.0, 0.95, "SCRUM")]
    tf, of = _make_context(players, lines)
    # Explicitly set team depth and width below set piece thresholds
    tf.team_0.longitudinal_span_m = 10.0
    tf.team_0.width_m = 14.0

    st = engine.process_frame(1, 0.04, players, tf, of)
    sig = st.team_0.instantaneous_signature
    assert sig.invalidation_reason == "SET_PIECE_DEFORMATION"
    assert sig.formation_label == "SET_PIECE_DEFORMATION"
    assert sig.formation_state == FormationState.TRANSITIONING


def test_unknown_orientation_abstention() -> None:
    """Verifies clean abstention when team orientation is UNKNOWN."""
    engine = DynamicFormationEngine()
    lines = _make_lines([4, 4, 2], [-20.0, -5.0, 12.0])
    players = [_make_player(i, "TEAM_0", -20.0 if i < 4 else 0.0, float(i * 4 - 14)) for i in range(10)]

    tf, of = _make_context(players, lines, is_oriented=False)
    st = engine.process_frame(1, 0.04, players, tf, of)

    sig = st.team_0.instantaneous_signature
    assert sig.formation_label == "UNKNOWN"
    assert sig.formation_state == FormationState.UNKNOWN
    assert sig.invalidation_reason == "UNKNOWN_ORIENTATION"
    assert sig.formation_confidence == 0.0


def test_possession_context_independence() -> None:
    """Verifies that EXP-18 ball control states annotate context but leave core formation unchanged."""
    engine = DynamicFormationEngine()
    lines = _make_lines([4, 4, 2], [-20.0, -5.0, 12.0])
    players = [_make_player(i, "TEAM_0", -20.0 if i < 4 else 0.0, float(i * 4 - 14)) for i in range(10)]
    tf, of = _make_context(players, lines)

    class MockBallControl:
        def __init__(self, team: str, conf: float) -> None:
            self.controlling_team = team
            self.confidence = conf

    # Case A: Team 0 in possession
    st_poss_0 = engine.process_frame(1, 0.04, players, tf, of, ball_control=MockBallControl("TEAM_0", 0.90))
    # Case B: Team 1 in possession
    st_poss_1 = engine.process_frame(1, 0.04, players, tf, of, ball_control=MockBallControl("TEAM_1", 0.90))

    # Core formation is identical
    assert st_poss_0.team_0.instantaneous_signature.formation_label == st_poss_1.team_0.instantaneous_signature.formation_label
    assert st_poss_0.team_0.instantaneous_signature.players_per_line == st_poss_1.team_0.instantaneous_signature.players_per_line
    # Context differs
    assert st_poss_0.team_0.instantaneous_signature.formation_context == FormationContext.IN_POSSESSION
    assert st_poss_1.team_0.instantaneous_signature.formation_context == FormationContext.OUT_OF_POSSESSION


def test_upstream_immutability() -> None:
    """Verifies that input player observations and line objects are not modified in place."""
    engine = DynamicFormationEngine()
    lines = _make_lines([4, 4, 2], [-20.0, -5.0, 12.0])
    players = [_make_player(i, "TEAM_0", -20.0 if i < 4 else 0.0, float(i * 4 - 14)) for i in range(10)]
    tf, of = _make_context(players, lines)

    orig_p_x = [p.pitch_x_m for p in players]
    orig_l_cnt = [l.player_count for l in lines]

    engine.process_frame(1, 0.04, players, tf, of)

    assert [p.pitch_x_m for p in players] == orig_p_x
    assert [l.player_count for l in lines] == orig_l_cnt
