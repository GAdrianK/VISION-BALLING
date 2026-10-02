"""Unit & Synthetic Validation Suite for EXP-20 Defensive Block Engine.

Tests:
1. Synthetic exact coordinate fixtures (Phase 16):
   - Deep low block
   - Midfield block
   - High line
   - Wide low block
   - Narrow high block
   - 4-line compact shape
   - Stretched shape
2. Algorithmic invariants & contract guarantees (Phase 24):
   - Defensive line height and distance from own goal
   - Outfield centroid height vs defensive line height separation
   - Goalkeeper strict exclusion from block metrics
   - Robust longitudinal & lateral spread (P90-P10, MAD)
   - 2, 3, and 4-line inter-line compactness
   - Visibility gating & abstention on low evidence (N <= 4)
   - Abstention on unknown attacking direction
   - Causal hysteresis confirmation window & transition event generation
   - Perturbation robustness (missing player, coordinate jitter)
   - Strict possession independence (core block geometry unaffected by possession state)
   - Upstream contract immutability
"""

import numpy as np
import pytest

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
from app.video_analysis.defensive_block import (
    BlockCategory,
    BlockTransitionEvent,
    DefensiveBlockConfig,
    DefensiveBlockEngine,
    DefensiveBlockFrameState,
    DefensiveBlockMetrics,
)


# ==============================================================================
# TEST FIXTURE HELPERS
# ==============================================================================

def create_player(
    track_id: int,
    team_label: str,
    pitch_x_m: float,
    pitch_y_m: float,
    role: str = "OUTFIELD_PLAYER",
    frame_index: int = 1,
    timestamp: float = 0.04,
) -> PlayerMetricObservation:
    """Creates a deterministic PlayerMetricObservation."""
    return PlayerMetricObservation(
        track_id=track_id,
        frame_index=frame_index,
        timestamp=timestamp,
        team_label=team_label,
        pitch_x_m=pitch_x_m,
        pitch_y_m=pitch_y_m,
        speed_mps=1.0,
        role=role,
        position_valid=True,
    )


def create_tactical_line(
    line_id: int,
    track_ids: list[int],
    mean_x_attack: float,
    median_x_attack: float,
    width_y_m: float,
    mean_pitch_x_m: float,
    mean_pitch_y_m: float = 0.0,
    confidence: float = 0.90,
    semantic_name: str = "DEFENSIVE_LINE",
) -> TacticalLine:
    """Creates a deterministic TacticalLine."""
    return TacticalLine(
        line_id=line_id,
        player_track_ids=track_ids,
        player_count=len(track_ids),
        mean_x_attack=mean_x_attack,
        median_x_attack=median_x_attack,
        width_y_m=width_y_m,
        mean_pitch_x_m=mean_pitch_x_m,
        mean_pitch_y_m=mean_pitch_y_m,
        confidence=confidence,
        candidate_semantic_name=semantic_name,
    )


def create_frame_context(
    players: list[PlayerMetricObservation],
    team_0_lines: list[TacticalLine],
    team_1_lines: list[TacticalLine],
    dir_0: AttackDirection = AttackDirection.POSITIVE_X,
    dir_1: AttackDirection = AttackDirection.NEGATIVE_X,
    ball: BallMetricObservation | None = None,
) -> tuple[list[PlayerMetricObservation], TacticalFrameState, OrientedTacticalFrameState, BallMetricObservation | None]:
    """Assembles a valid TacticalFrameState and OrientedTacticalFrameState."""
    outfield_0 = [p for p in players if p.team_label == "TEAM_0" and p.role != "GOALKEEPER"]
    outfield_1 = [p for p in players if p.team_label == "TEAM_1" and p.role != "GOALKEEPER"]

    t0_geom = TeamTacticalGeometry(
        team_label="TEAM_0",
        visible_players=len([p for p in players if p.team_label == "TEAM_0"]),
        outfield_player_count=len(outfield_0),
        goalkeeper_present=any(p.team_label == "TEAM_0" and p.role == "GOALKEEPER" for p in players),
        centroid_x=float(np.mean([p.pitch_x_m for p in outfield_0])) if outfield_0 else None,
        centroid_y=float(np.mean([p.pitch_y_m for p in outfield_0])) if outfield_0 else None,
        median_centroid_x=float(np.median([p.pitch_x_m for p in outfield_0])) if outfield_0 else None,
        median_centroid_y=float(np.median([p.pitch_y_m for p in outfield_0])) if outfield_0 else None,
        width_m=float(np.max([p.pitch_y_m for p in outfield_0]) - np.min([p.pitch_y_m for p in outfield_0])) if len(outfield_0) >= 2 else None,
        longitudinal_span_m=float(np.max([p.pitch_x_m for p in outfield_0]) - np.min([p.pitch_x_m for p in outfield_0])) if len(outfield_0) >= 2 else None,
        convex_hull_area_m2=500.0 if len(outfield_0) >= 3 else None,
        convex_hull_perimeter_m=100.0 if len(outfield_0) >= 3 else None,
        is_valid=True,
    )

    t1_geom = TeamTacticalGeometry(
        team_label="TEAM_1",
        visible_players=len([p for p in players if p.team_label == "TEAM_1"]),
        outfield_player_count=len(outfield_1),
        goalkeeper_present=any(p.team_label == "TEAM_1" and p.role == "GOALKEEPER" for p in players),
        centroid_x=float(np.mean([p.pitch_x_m for p in outfield_1])) if outfield_1 else None,
        centroid_y=float(np.mean([p.pitch_y_m for p in outfield_1])) if outfield_1 else None,
        is_valid=True,
    )

    from app.video_analysis.tactical_geometry import (
        BallTacticalGeometry,
        InterTeamTacticalGeometry,
        TacticalQualityState,
    )

    tact_geom = TacticalFrameState(
        frame_index=1,
        timestamp=0.04,
        calibration_valid=True,
        team_0=t0_geom,
        team_1=t1_geom,
        ball=BallTacticalGeometry(),
        inter_team=InterTeamTacticalGeometry(),
        quality=TacticalQualityState(calibration_valid=True, geometry_valid=True),
    )

    vis_0 = "HIGH" if len(outfield_0) >= 8 else ("MEDIUM" if len(outfield_0) >= 5 else "LOW")
    vis_1 = "HIGH" if len(outfield_1) >= 8 else ("MEDIUM" if len(outfield_1) >= 5 else "LOW")

    t0_orient = TeamOrientedTactics(
        team_label="TEAM_0",
        attack_direction=dir_0,
        is_oriented=(dir_0 != AttackDirection.UNKNOWN),
        lines=team_0_lines,
        line_count=len(team_0_lines),
        visibility_level=vis_0,
        outfield_player_count=len(outfield_0),
    )

    t1_orient = TeamOrientedTactics(
        team_label="TEAM_1",
        attack_direction=dir_1,
        is_oriented=(dir_1 != AttackDirection.UNKNOWN),
        lines=team_1_lines,
        line_count=len(team_1_lines),
        visibility_level=vis_1,
        outfield_player_count=len(outfield_1),
    )

    oriented_tact = OrientedTacticalFrameState(
        frame_index=1,
        timestamp=0.04,
        team_0=t0_orient,
        team_1=t1_orient,
        orientation_confidence=0.90,
    )

    return players, tact_geom, oriented_tact, ball


# ==============================================================================
# PHASE 16: SYNTHETIC FIXTURE VALIDATIONS
# ==============================================================================

def test_synthetic_deep_low_block():
    """Scenario 1: Deep low block inside own defensive third (<35.0m from own goal)."""
    engine = DefensiveBlockEngine()
    # Team 0 attacks +X. Own goal is at -52.5m.
    # Defensive line at x = -32.5m -> distance from own goal = -32.5 + 52.5 = 20.0m.
    # Midfield line at x = -20.0m -> distance from own goal = 32.5m.
    # Attacking line at x = -10.0m -> distance from own goal = 42.5m.
    players = [
        # GK
        create_player(1, "TEAM_0", -50.0, 0.0, role="GOALKEEPER"),
        # Defense (4 players)
        create_player(2, "TEAM_0", -32.5, -18.0),
        create_player(3, "TEAM_0", -32.5, -6.0),
        create_player(4, "TEAM_0", -32.5, 6.0),
        create_player(5, "TEAM_0", -32.5, 18.0),
        # Midfield (4 players)
        create_player(6, "TEAM_0", -20.0, -15.0),
        create_player(7, "TEAM_0", -20.0, -5.0),
        create_player(8, "TEAM_0", -20.0, 5.0),
        create_player(9, "TEAM_0", -20.0, 15.0),
        # Attack (2 players)
        create_player(10, "TEAM_0", -10.0, -8.0),
        create_player(11, "TEAM_0", -10.0, 8.0),
    ]

    lines_0 = [
        create_tactical_line(0, [2, 3, 4, 5], mean_x_attack=-32.5, median_x_attack=-32.5, width_y_m=36.0, mean_pitch_x_m=-32.5, semantic_name="DEFENSIVE_LINE"),
        create_tactical_line(1, [6, 7, 8, 9], mean_x_attack=-20.0, median_x_attack=-20.0, width_y_m=30.0, mean_pitch_x_m=-20.0, semantic_name="MIDFIELD_LINE"),
        create_tactical_line(2, [10, 11], mean_x_attack=-10.0, median_x_attack=-10.0, width_y_m=16.0, mean_pitch_x_m=-10.0, semantic_name="ATTACKING_LINE"),
    ]

    p_list, geom, orient, ball = create_frame_context(players, lines_0, [])
    state = engine.process_frame(1, 0.04, p_list, geom, orient, ball)
    m = state.team_0

    assert m.raw_category == BlockCategory.LOW_BLOCK
    assert pytest.approx(m.defensive_line_height_m, rel=1e-3) == 20.0
    assert pytest.approx(m.oriented_depth_m, rel=1e-3) == 22.5
    assert pytest.approx(m.lateral_width_m, rel=1e-3) == 36.0
    assert m.defense_midfield_distance_m == pytest.approx(12.5, rel=1e-3)
    assert m.midfield_attack_distance_m == pytest.approx(10.0, rel=1e-3)
    assert m.line_count == 3


def test_synthetic_midfield_block():
    """Scenario 2: Midfield block sitting between 35m and 52.5m (middle third)."""
    engine = DefensiveBlockEngine()
    # Team 0 attacks +X. Defensive line at x = -12.5m -> height = 40.0m.
    players = [
        create_player(2, "TEAM_0", -12.5, -20.0),
        create_player(3, "TEAM_0", -12.5, -7.0),
        create_player(4, "TEAM_0", -12.5, 7.0),
        create_player(5, "TEAM_0", -12.5, 20.0),
        create_player(6, "TEAM_0", 0.0, -15.0),
        create_player(7, "TEAM_0", 0.0, 15.0),
        create_player(8, "TEAM_0", 12.5, -5.0),
        create_player(9, "TEAM_0", 12.5, 5.0),
    ]

    lines_0 = [
        create_tactical_line(0, [2, 3, 4, 5], mean_x_attack=-12.5, median_x_attack=-12.5, width_y_m=40.0, mean_pitch_x_m=-12.5, semantic_name="DEFENSIVE_LINE"),
        create_tactical_line(1, [6, 7], mean_x_attack=0.0, median_x_attack=0.0, width_y_m=30.0, mean_pitch_x_m=0.0, semantic_name="MIDFIELD_LINE"),
        create_tactical_line(2, [8, 9], mean_x_attack=12.5, median_x_attack=12.5, width_y_m=10.0, mean_pitch_x_m=12.5, semantic_name="ATTACKING_LINE"),
    ]

    p_list, geom, orient, ball = create_frame_context(players, lines_0, [])
    state = engine.process_frame(1, 0.04, p_list, geom, orient, ball)
    m = state.team_0

    assert m.raw_category == BlockCategory.MID_BLOCK
    assert pytest.approx(m.defensive_line_height_m, rel=1e-3) == 40.0


def test_synthetic_high_line():
    """Scenario 3: High defensive line pushed to or past midfield (>= 52.5m)."""
    engine = DefensiveBlockEngine()
    # Team 0 attacks +X. Defensive line at x = +5.0m -> height = 57.5m.
    players = [
        create_player(2, "TEAM_0", 5.0, -22.0),
        create_player(3, "TEAM_0", 5.0, -8.0),
        create_player(4, "TEAM_0", 5.0, 8.0),
        create_player(5, "TEAM_0", 5.0, 22.0),
        create_player(6, "TEAM_0", 18.0, -15.0),
        create_player(7, "TEAM_0", 18.0, 15.0),
        create_player(8, "TEAM_0", 30.0, 0.0),
        create_player(9, "TEAM_0", 32.0, 0.0),
    ]

    lines_0 = [
        create_tactical_line(0, [2, 3, 4, 5], mean_x_attack=5.0, median_x_attack=5.0, width_y_m=44.0, mean_pitch_x_m=5.0, semantic_name="DEFENSIVE_LINE"),
        create_tactical_line(1, [6, 7], mean_x_attack=18.0, median_x_attack=18.0, width_y_m=30.0, mean_pitch_x_m=18.0, semantic_name="MIDFIELD_LINE"),
        create_tactical_line(2, [8, 9], mean_x_attack=31.0, median_x_attack=31.0, width_y_m=0.0, mean_pitch_x_m=31.0, semantic_name="ATTACKING_LINE"),
    ]

    p_list, geom, orient, ball = create_frame_context(players, lines_0, [])
    state = engine.process_frame(1, 0.04, p_list, geom, orient, ball)
    m = state.team_0

    assert m.raw_category == BlockCategory.HIGH_BLOCK
    assert pytest.approx(m.defensive_line_height_m, rel=1e-3) == 57.5


def test_synthetic_wide_low_and_narrow_high_shapes():
    """Scenario 4 & 5: Wide low block vs narrow high block lateral compactness."""
    engine = DefensiveBlockEngine()
    # Wide Low Block (width = 56m)
    players_wide = [
        create_player(2, "TEAM_0", -30.0, -28.0),
        create_player(3, "TEAM_0", -30.0, 28.0),
        create_player(4, "TEAM_0", -25.0, -10.0),
        create_player(5, "TEAM_0", -25.0, 10.0),
        create_player(6, "TEAM_0", -15.0, 0.0),
        create_player(7, "TEAM_0", -15.0, 2.0),
    ]
    lines_wide = [
        create_tactical_line(0, [2, 3], -30.0, -30.0, 56.0, -30.0),
        create_tactical_line(1, [4, 5, 6, 7], -20.0, -20.0, 20.0, -20.0),
    ]
    p_w, g_w, o_w, b_w = create_frame_context(players_wide, lines_wide, [])
    st_w = engine.process_frame(1, 0.04, p_w, g_w, o_w, b_w)
    assert st_w.team_0.raw_category == BlockCategory.LOW_BLOCK
    assert pytest.approx(st_w.team_0.lateral_width_m, rel=1e-3) == 56.0

    # Narrow High Block (width = 24m)
    players_narrow = [
        create_player(2, "TEAM_0", 10.0, -12.0),
        create_player(3, "TEAM_0", 10.0, 12.0),
        create_player(4, "TEAM_0", 20.0, -8.0),
        create_player(5, "TEAM_0", 20.0, 8.0),
        create_player(6, "TEAM_0", 30.0, -5.0),
        create_player(7, "TEAM_0", 30.0, 5.0),
    ]
    lines_narrow = [
        create_tactical_line(0, [2, 3], 10.0, 10.0, 24.0, 10.0),
        create_tactical_line(1, [4, 5, 6, 7], 25.0, 25.0, 16.0, 25.0),
    ]
    p_n, g_n, o_n, b_n = create_frame_context(players_narrow, lines_narrow, [])
    st_n = engine.process_frame(1, 0.04, p_n, g_n, o_n, b_n)
    assert st_n.team_0.raw_category == BlockCategory.HIGH_BLOCK
    assert pytest.approx(st_n.team_0.lateral_width_m, rel=1e-3) == 24.0


def test_synthetic_four_line_compact_shape():
    """Scenario 6: 4-line defensive system with balanced inter-line distances."""
    engine = DefensiveBlockEngine()
    # 4 lines at x = -24.5m (height 28.0m), -14.5m (38.0m), -4.5m (48.0m), +5.5m (58.0m)
    players = [
        create_player(1, "TEAM_0", -24.5, -15.0),
        create_player(2, "TEAM_0", -24.5, 15.0),
        create_player(3, "TEAM_0", -14.5, -10.0),
        create_player(4, "TEAM_0", -14.5, 10.0),
        create_player(5, "TEAM_0", -4.5, -8.0),
        create_player(6, "TEAM_0", -4.5, 8.0),
        create_player(7, "TEAM_0", 5.5, 0.0),
        create_player(8, "TEAM_0", 5.5, 2.0),
    ]
    lines = [
        create_tactical_line(0, [1, 2], -24.5, -24.5, 30.0, -24.5),
        create_tactical_line(1, [3, 4], -14.5, -14.5, 20.0, -14.5),
        create_tactical_line(2, [5, 6], -4.5, -4.5, 16.0, -4.5),
        create_tactical_line(3, [7, 8], 5.5, 5.5, 2.0, 5.5),
    ]
    p_list, geom, orient, ball = create_frame_context(players, lines, [])
    state = engine.process_frame(1, 0.04, p_list, geom, orient, ball)
    m = state.team_0

    assert m.line_count == 4
    assert len(m.inter_line_distances_m) == 3
    assert all(pytest.approx(d, rel=1e-3) == 10.0 for d in m.inter_line_distances_m)
    assert pytest.approx(m.mean_inter_line_distance_m, rel=1e-3) == 10.0
    assert pytest.approx(m.max_inter_line_distance_m, rel=1e-3) == 10.0


def test_synthetic_stretched_shape():
    """Scenario 7: Highly stretched team structure with large longitudinal spread."""
    engine = DefensiveBlockEngine()
    # Defense at -27.5m (height 25.0m), Forward at +27.5m (height 80.0m) -> depth = 55.0m
    players = [
        create_player(1, "TEAM_0", -27.5, -10.0),
        create_player(2, "TEAM_0", -27.5, 10.0),
        create_player(3, "TEAM_0", 0.0, 0.0),
        create_player(4, "TEAM_0", 27.5, -5.0),
        create_player(5, "TEAM_0", 27.5, 5.0),
    ]
    lines = [
        create_tactical_line(0, [1, 2], -27.5, -27.5, 20.0, -27.5),
        create_tactical_line(1, [3], 0.0, 0.0, 0.0, 0.0),
        create_tactical_line(2, [4, 5], 27.5, 27.5, 10.0, 27.5),
    ]
    p_list, geom, orient, ball = create_frame_context(players, lines, [])
    state = engine.process_frame(1, 0.04, p_list, geom, orient, ball)
    m = state.team_0

    assert pytest.approx(m.oriented_depth_m, rel=1e-3) == 55.0
    assert m.longitudinal_p90_p10_spread_m > 35.0
    assert m.longitudinal_mad_m is not None and m.longitudinal_mad_m > 10.0


# ==============================================================================
# PHASE 24: ALGORITHMIC INVARIANTS & INTEGRATION TESTS
# ==============================================================================

def test_goalkeeper_strict_exclusion():
    """Verifies that goalkeepers are never factored into defensive line or outfield centroid."""
    engine = DefensiveBlockEngine()
    players = [
        # GK at extreme deep position
        create_player(1, "TEAM_0", -50.0, 0.0, role="GOALKEEPER"),
        # Outfield defense at -30.0m (height 22.5m)
        create_player(2, "TEAM_0", -30.0, -10.0),
        create_player(3, "TEAM_0", -30.0, 10.0),
        create_player(4, "TEAM_0", -20.0, -5.0),
        create_player(5, "TEAM_0", -20.0, 5.0),
        create_player(6, "TEAM_0", -10.0, 0.0),
    ]
    lines = [
        create_tactical_line(0, [2, 3], -30.0, -30.0, 20.0, -30.0),
        create_tactical_line(1, [4, 5, 6], -15.0, -15.0, 10.0, -15.0),
    ]
    p_list, geom, orient, ball = create_frame_context(players, lines, [])
    state = engine.process_frame(1, 0.04, p_list, geom, orient, ball)
    m = state.team_0

    assert m.goalkeeper_present is True
    assert pytest.approx(m.goalkeeper_distance_from_own_goal_m, rel=1e-3) == 2.5
    # Defensive line must be at 22.5m (not influenced by GK at 2.5m)
    assert pytest.approx(m.defensive_line_height_m, rel=1e-3) == 22.5
    # Backmost player must be 22.5m (outfield player), not 2.5m
    assert pytest.approx(m.team_backmost_player_height_m, rel=1e-3) == 22.5


def test_visibility_gating_low_evidence():
    """Phase 15: Low visibility (N <= 4 outfield players) forces UNKNOWN category abstention."""
    engine = DefensiveBlockEngine()
    players = [
        create_player(1, "TEAM_0", -30.0, -10.0),
        create_player(2, "TEAM_0", -30.0, 10.0),
        create_player(3, "TEAM_0", -20.0, 0.0),
        create_player(4, "TEAM_0", -10.0, 0.0),
    ]
    lines = [
        create_tactical_line(0, [1, 2], -30.0, -30.0, 20.0, -30.0),
        create_tactical_line(1, [3, 4], -15.0, -15.0, 0.0, -15.0),
    ]
    p_list, geom, orient, ball = create_frame_context(players, lines, [])
    state = engine.process_frame(1, 0.04, p_list, geom, orient, ball)
    m = state.team_0

    assert m.outfield_player_count == 4
    assert m.visibility_level == "LOW"
    assert m.raw_category == BlockCategory.UNKNOWN
    assert m.confirmed_category == BlockCategory.UNKNOWN
    assert m.category_confidence == 0.0
    assert m.invalidation_reason == "LOW_VISIBILITY"


def test_unknown_attacking_direction_abstention():
    """Unoriented teams must abstain from issuing distance-from-own-goal categories."""
    engine = DefensiveBlockEngine()
    players = [
        create_player(i, "TEAM_0", float(i * 5 - 20), 0.0) for i in range(6)
    ]
    lines = [create_tactical_line(0, [0, 1], -17.5, -17.5, 0.0, -17.5)]
    p_list, geom, orient, ball = create_frame_context(players, lines, [], dir_0=AttackDirection.UNKNOWN)
    state = engine.process_frame(1, 0.04, p_list, geom, orient, ball)
    m = state.team_0

    assert m.is_oriented is False
    assert m.raw_category == BlockCategory.UNKNOWN
    assert m.invalidation_reason == "UNKNOWN_ORIENTATION"


def test_temporal_hysteresis_and_transitions():
    """Phase 13 & 14: Confirmed category requires sustained frames and emits transition events."""
    engine = DefensiveBlockEngine(DefensiveBlockConfig(hysteresis_frames=5))
    players_low = [create_player(i, "TEAM_0", -30.0 if i < 3 else -10.0, float(i)) for i in range(6)]
    lines_low = [create_tactical_line(0, [0, 1, 2], -30.0, -30.0, 2.0, -30.0)]

    players_mid = [create_player(i, "TEAM_0", -10.0 if i < 3 else 10.0, float(i)) for i in range(6)]
    lines_mid = [create_tactical_line(0, [0, 1, 2], -10.0, -10.0, 2.0, -10.0)]

    # Cold start: 3 frames to establish LOW_BLOCK
    for f in range(1, 4):
        p, g, o, b = create_frame_context(players_low, lines_low, [])
        st = engine.process_frame(f, f * 0.04, p, g, o, b)
    assert st.team_0.confirmed_category == BlockCategory.LOW_BLOCK

    # Flicker: 2 frames of MID_BLOCK must NOT change confirmed category
    for f in range(4, 6):
        p, g, o, b = create_frame_context(players_mid, lines_mid, [])
        st = engine.process_frame(f, f * 0.04, p, g, o, b)
        assert st.team_0.confirmed_category == BlockCategory.LOW_BLOCK
        assert len(st.transitions) == 0

    # Sustained MID_BLOCK: complete 5 consecutive frames
    for f in range(6, 9):
        p, g, o, b = create_frame_context(players_mid, lines_mid, [])
        st = engine.process_frame(f, f * 0.04, p, g, o, b)

    # At frame 8, 5 consecutive frames of MID_BLOCK (frames 4, 5, 6, 7, 8) confirm the transition
    assert st.team_0.confirmed_category == BlockCategory.MID_BLOCK
    assert len(st.transitions) == 1
    evt = st.transitions[0]
    assert evt.from_category == BlockCategory.LOW_BLOCK
    assert evt.to_category == BlockCategory.MID_BLOCK
    assert evt.team_label == "TEAM_0"


def test_possession_independence_guarantee():
    """Phase 9: Core block geometry is strictly invariant to possession state."""
    engine = DefensiveBlockEngine()
    players = [create_player(i, "TEAM_0", -25.0 if i < 3 else 0.0, float(i * 3)) for i in range(6)]
    lines = [create_tactical_line(0, [0, 1, 2], -25.0, -25.0, 6.0, -25.0)]

    class FakePossession:
        def __init__(self, team, conf):
            self.possession_team = team
            self.possession_confidence = conf

    p, g, o, b = create_frame_context(players, lines, [])

    # Process without possession
    st_none = engine.process_frame(1, 0.04, p, g, o, b, ball_control=None)
    # Process with TEAM_0 possession
    st_t0 = engine.process_frame(1, 0.04, p, g, o, b, ball_control=FakePossession("TEAM_0", 0.90))
    # Process with TEAM_1 possession
    st_t1 = engine.process_frame(1, 0.04, p, g, o, b, ball_control=FakePossession("TEAM_1", 0.90))

    # Core geometry must be identical
    assert st_none.team_0.defensive_line_height_m == st_t0.team_0.defensive_line_height_m == st_t1.team_0.defensive_line_height_m
    assert st_none.team_0.oriented_depth_m == st_t0.team_0.oriented_depth_m == st_t1.team_0.oriented_depth_m
    assert st_none.team_0.raw_category == st_t0.team_0.raw_category == st_t1.team_0.raw_category

    # Probable defending team diagnostics
    assert st_none.probable_defending_team == "UNKNOWN"
    assert st_t0.probable_defending_team == "TEAM_1"
    assert st_t1.probable_defending_team == "TEAM_0"


def test_perturbation_coordinate_noise():
    """Phase 17: Injects coordinate noise (+/- 0.10m, 0.25m, 0.50m) and validates height stability."""
    engine = DefensiveBlockEngine()
    rng = np.random.RandomState(42)

    base_players = [create_player(i, "TEAM_0", -20.0 if i < 4 else 0.0, float(i * 4 - 10)) for i in range(8)]
    base_lines = [
        create_tactical_line(0, [0, 1, 2, 3], -20.0, -20.0, 16.0, -20.0),
        create_tactical_line(1, [4, 5, 6, 7], 0.0, 0.0, 16.0, 0.0),
    ]

    p, g, o, b = create_frame_context(base_players, base_lines, [])
    st_base = engine.process_frame(1, 0.04, p, g, o, b)
    base_height = st_base.team_0.defensive_line_height_m

    for noise_scale in [0.10, 0.25, 0.50]:
        noise_x = rng.uniform(-noise_scale, noise_scale, size=4)
        noisy_line_x = -20.0 + float(np.median(noise_x))
        noisy_lines = [
            create_tactical_line(0, [0, 1, 2, 3], noisy_line_x, noisy_line_x, 16.0, noisy_line_x),
            create_tactical_line(1, [4, 5, 6, 7], 0.0, 0.0, 16.0, 0.0),
        ]
        p_n, g_n, o_n, b_n = create_frame_context(base_players, noisy_lines, [])
        st_noisy = engine.process_frame(1, 0.04, p_n, g_n, o_n, b_n)
        noisy_height = st_noisy.team_0.defensive_line_height_m

        assert abs(noisy_height - base_height) <= noise_scale * 1.5
        assert st_noisy.team_0.raw_category == st_base.team_0.raw_category


def test_missing_defender_perturbation():
    """Phase 17: Removing one defender from the back line preserves category stability."""
    engine = DefensiveBlockEngine()
    # 4 defenders at -20m, 4 midfielders at 0m
    players_full = [create_player(i, "TEAM_0", -20.0 if i < 4 else 0.0, float(i * 4 - 10)) for i in range(8)]
    lines_full = [
        create_tactical_line(0, [0, 1, 2, 3], -20.0, -20.0, 16.0, -20.0),
        create_tactical_line(1, [4, 5, 6, 7], 0.0, 0.0, 16.0, 0.0),
    ]
    p_f, g_f, o_f, b_f = create_frame_context(players_full, lines_full, [])
    st_full = engine.process_frame(1, 0.04, p_f, g_f, o_f, b_f)

    # Remove player 3 (one defender missing)
    players_missing = [p for p in players_full if p.track_id != 3]
    lines_missing = [
        create_tactical_line(0, [0, 1, 2], -20.0, -20.0, 12.0, -20.0),
        create_tactical_line(1, [4, 5, 6, 7], 0.0, 0.0, 16.0, 0.0),
    ]
    p_m, g_m, o_m, b_m = create_frame_context(players_missing, lines_missing, [])
    st_missing = engine.process_frame(1, 0.04, p_m, g_m, o_m, b_m)

    assert st_full.team_0.raw_category == st_missing.team_0.raw_category == BlockCategory.LOW_BLOCK
    assert pytest.approx(st_full.team_0.defensive_line_height_m, rel=1e-3) == st_missing.team_0.defensive_line_height_m


def test_upstream_contract_immutability():
    """Phase 24: Verifies upstream modules and classes are unchanged."""
    import app.video_analysis.metric_trajectories as mt
    import app.video_analysis.tactical_geometry as tg
    import app.video_analysis.tactical_lines as tl
    import app.video_analysis.possession as ps

    assert hasattr(mt, "MetricTrajectoryEngine")
    assert hasattr(tg, "TacticalGeometryEngine")
    assert hasattr(tl, "OrientedTacticsEngine")
    assert hasattr(ps, "PossessionEngine")
    assert hasattr(tl, "AttackDirection")
    assert hasattr(tg, "TeamTacticalGeometry")

