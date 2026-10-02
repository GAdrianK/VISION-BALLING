"""Unit tests for Chapter 7: Attacking Direction & Oriented Tactical Lines (EXP-17).

Verifies:
1. Attacking direction resolution (+X / -X goalkeeper anchors, team spatial ordering fallback,
   ambiguous midfield abstention, side-switch reversal hysteresis, complementary inference).
2. Team-oriented longitudinal coordinate transformation (x_attack = attack_direction * x_pitch).
3. Interpretable 1D gap-based tactical line clustering (2, 3, and 4-line structures, intra-line dispersion).
4. Inter-line distance and oriented team depth calculations.
5. Outfield player isolation (goalkeeper exclusion from lines and team depth).
6. Low-visibility and minimum-player gating (outfield count < 4).
7. Causal temporal line persistence tracking across frames.
8. Integrated OrientedTacticsEngine execution and inter-team defensive gap.
9. Immutability of Chapter 5, Chapter 6, and EXP-16 components.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.video_analysis.pitch_calibration import PitchDimensions
from app.video_analysis.tactical_lines import (
    AttackDirection,
    AttackingDirectionResolver,
    OrientedTacticalFrameState,
    OrientedTacticsEngine,
    TacticalLine,
    TacticalLineConfig,
    TacticalLineDiscoverer,
    TeamAttackingOrientation,
    TeamOrientedTactics,
    TemporalLineTracker,
)


def test_attacking_direction_goalkeeper_anchor_positive_x() -> None:
    """Verifies that a goalkeeper located near the negative goal line (-X) resolves attack toward +X."""
    resolver = AttackingDirectionResolver()
    # GK at -48.0m (past threshold of -30.5m)
    team_0 = [
        {"track_id": 1, "x": -48.0, "y": 0.0, "role": "GOALKEEPER"},
        {"track_id": 2, "x": -20.0, "y": -10.0, "role": "OUTFIELD_PLAYER"},
    ]
    team_1 = [
        {"track_id": 3, "x": 20.0, "y": 10.0, "role": "OUTFIELD_PLAYER"},
    ]

    o0, o1 = resolver.resolve(team_0, team_1)

    assert o0.attack_direction == AttackDirection.POSITIVE_X
    assert o0.confidence >= 0.90
    assert o0.primary_source == "GOALKEEPER_ANCHOR"
    assert o0.is_confirmed is True

    # Complementary inference should assign Team 1 to NEGATIVE_X
    assert o1.attack_direction == AttackDirection.NEGATIVE_X
    assert o1.confidence >= 0.80
    assert o1.primary_source == "COMPLEMENTARY_INFERENCE"


def test_attacking_direction_goalkeeper_anchor_negative_x() -> None:
    """Verifies that a goalkeeper located near the positive goal line (+X) resolves attack toward -X."""
    resolver = AttackingDirectionResolver()
    team_0 = [
        {"track_id": 1, "x": 48.0, "y": 0.0, "role": "GOALKEEPER"},
        {"track_id": 2, "x": 20.0, "y": -10.0, "role": "OUTFIELD_PLAYER"},
    ]
    team_1 = [
        {"track_id": 3, "x": -20.0, "y": 10.0, "role": "OUTFIELD_PLAYER"},
    ]

    o0, o1 = resolver.resolve(team_0, team_1)

    assert o0.attack_direction == AttackDirection.NEGATIVE_X
    assert o0.confidence >= 0.90
    assert o0.primary_source == "GOALKEEPER_ANCHOR"

    # Complementary inference
    assert o1.attack_direction == AttackDirection.POSITIVE_X


def test_attacking_direction_fallback_to_team_spatial_ordering() -> None:
    """Verifies fallback to persistent team spatial ordering when no GK is in goal area."""
    config = TacticalLineConfig(team_ordering_min_frames=5, team_ordering_min_separation_m=4.0)
    resolver = AttackingDirectionResolver(config=config)

    # Team 0 centered at -15.0m, Team 1 centered at +15.0m (separation = 30m > 4m)
    team_0 = [{"track_id": 1, "x": -15.0, "y": 0.0, "role": "OUTFIELD_PLAYER"}]
    team_1 = [{"track_id": 2, "x": 15.0, "y": 0.0, "role": "OUTFIELD_PLAYER"}]

    # Feed 4 frames (not yet minimum frames -> UNKNOWN)
    for _ in range(4):
        o0, o1 = resolver.resolve(team_0, team_1)
        assert o0.attack_direction == AttackDirection.UNKNOWN

    # 5th frame reaches minimum frames -> resolves
    o0, o1 = resolver.resolve(team_0, team_1)
    assert o0.attack_direction == AttackDirection.POSITIVE_X
    assert o1.attack_direction == AttackDirection.NEGATIVE_X
    assert o0.primary_source == "TEAM_SPATIAL_ORDERING"
    assert o0.confidence == pytest.approx(0.70)


def test_attacking_direction_ambiguous_midfield_abstention() -> None:
    """Verifies that when teams are intermingled in midfield and no GK is present, resolver abstains."""
    config = TacticalLineConfig(team_ordering_min_frames=3, team_ordering_min_separation_m=4.0)
    resolver = AttackingDirectionResolver(config=config)

    # Both teams centered near 0.0m (difference = 1.0m < 4.0m)
    team_0 = [{"track_id": 1, "x": -0.5, "y": 0.0, "role": "OUTFIELD_PLAYER"}]
    team_1 = [{"track_id": 2, "x": 0.5, "y": 0.0, "role": "OUTFIELD_PLAYER"}]

    for _ in range(5):
        o0, o1 = resolver.resolve(team_0, team_1)

    assert o0.attack_direction == AttackDirection.UNKNOWN
    assert o1.attack_direction == AttackDirection.UNKNOWN
    assert o0.confidence == 0.0
    assert o1.confidence == 0.0


def test_attacking_direction_side_switch_reversal_hysteresis() -> None:
    """Verifies that reversing confirmed direction requires consecutive confirmation frames."""
    config = TacticalLineConfig(side_switch_confirmation_frames=5)
    resolver = AttackingDirectionResolver(config=config)

    # Establish initial orientation: Team 0 GK at -45.0m -> POSITIVE_X
    team_0_init = [{"track_id": 1, "x": -45.0, "y": 0.0, "role": "GOALKEEPER"}]
    team_1_init = [{"track_id": 2, "x": 45.0, "y": 0.0, "role": "GOALKEEPER"}]
    o0, _ = resolver.resolve(team_0_init, team_1_init)
    assert o0.attack_direction == AttackDirection.POSITIVE_X
    assert o0.side_switch_count == 0

    # Simulate halftime: Team 0 GK suddenly observed at +45.0m (should attack NEGATIVE_X)
    team_0_switched = [{"track_id": 1, "x": 45.0, "y": 0.0, "role": "GOALKEEPER"}]
    team_1_switched = [{"track_id": 2, "x": -45.0, "y": 0.0, "role": "GOALKEEPER"}]

    # For frames 1 to 4 (< 5 confirmation frames), orientation remains POSITIVE_X
    for _ in range(4):
        o0, _ = resolver.resolve(team_0_switched, team_1_switched)
        assert o0.attack_direction == AttackDirection.POSITIVE_X
        assert o0.side_switch_count == 0

    # At 5th consecutive frame, orientation switches to NEGATIVE_X
    o0, _ = resolver.resolve(team_0_switched, team_1_switched)
    assert o0.attack_direction == AttackDirection.NEGATIVE_X
    assert o0.side_switch_count == 1


def test_oriented_coordinate_transformation() -> None:
    """Verifies that x_attack = attack_direction * x_pitch correctly maps own goal to min and opp goal to max."""
    discoverer = TacticalLineDiscoverer(config=TacticalLineConfig(min_line_gap_m=6.0))

    # Case A: Attacking +X (Pitch X = -30m is defensive, +20m is offensive)
    players_pos = [
        {"track_id": 1, "x": -30.0, "y": 0.0, "role": "OUTFIELD_PLAYER"},
        {"track_id": 2, "x": -30.0, "y": 10.0, "role": "OUTFIELD_PLAYER"},
        {"track_id": 3, "x": 20.0, "y": 0.0, "role": "OUTFIELD_PLAYER"},
        {"track_id": 4, "x": 20.0, "y": 10.0, "role": "OUTFIELD_PLAYER"},
    ]
    lines_pos = discoverer.discover_lines(players_pos, AttackDirection.POSITIVE_X)
    assert len(lines_pos) == 2
    # Line 0 is defensive (x_attack = -30.0), Line 1 is offensive (x_attack = +20.0)
    assert lines_pos[0].candidate_semantic_name == "DEFENSIVE_LINE"
    assert lines_pos[0].mean_x_attack == pytest.approx(-30.0)
    assert lines_pos[1].candidate_semantic_name == "ATTACKING_LINE"
    assert lines_pos[1].mean_x_attack == pytest.approx(20.0)

    # Case B: Attacking -X (Pitch X = +30m is defensive, -20m is offensive)
    players_neg = [
        {"track_id": 1, "x": 30.0, "y": 0.0, "role": "OUTFIELD_PLAYER"},
        {"track_id": 2, "x": 30.0, "y": 10.0, "role": "OUTFIELD_PLAYER"},
        {"track_id": 3, "x": -20.0, "y": 0.0, "role": "OUTFIELD_PLAYER"},
        {"track_id": 4, "x": -20.0, "y": 10.0, "role": "OUTFIELD_PLAYER"},
    ]
    lines_neg = discoverer.discover_lines(players_neg, AttackDirection.NEGATIVE_X)
    assert len(lines_neg) == 2
    # Pitch X = +30.0 -> x_attack = -1 * (+30.0) = -30.0 (defensive)
    # Pitch X = -20.0 -> x_attack = -1 * (-20.0) = +20.0 (attacking)
    assert lines_neg[0].candidate_semantic_name == "DEFENSIVE_LINE"
    assert lines_neg[0].mean_x_attack == pytest.approx(-30.0)
    assert lines_neg[1].candidate_semantic_name == "ATTACKING_LINE"
    assert lines_neg[1].mean_x_attack == pytest.approx(20.0)


def test_1d_gap_clustering_synthetic_442() -> None:
    """Verifies that 1D gap clustering cleanly discovers 3 tactical lines for a 4-4-2 formation."""
    discoverer = TacticalLineDiscoverer(config=TacticalLineConfig(min_line_gap_m=6.0))

    # 4 defenders at x = -20m, 4 midfielders at x = 0m, 2 forwards at x = +20m (gaps = 20m > 6m)
    players = [
        # Defense
        {"track_id": 1, "x": -20.0, "y": -25.0, "role": "OUTFIELD_PLAYER"},
        {"track_id": 2, "x": -20.0, "y": -8.0, "role": "OUTFIELD_PLAYER"},
        {"track_id": 3, "x": -20.0, "y": 8.0, "role": "OUTFIELD_PLAYER"},
        {"track_id": 4, "x": -20.0, "y": 25.0, "role": "OUTFIELD_PLAYER"},
        # Midfield
        {"track_id": 5, "x": 0.0, "y": -22.0, "role": "OUTFIELD_PLAYER"},
        {"track_id": 6, "x": 0.0, "y": -7.0, "role": "OUTFIELD_PLAYER"},
        {"track_id": 7, "x": 0.0, "y": 7.0, "role": "OUTFIELD_PLAYER"},
        {"track_id": 8, "x": 0.0, "y": 22.0, "role": "OUTFIELD_PLAYER"},
        # Forwards
        {"track_id": 9, "x": 20.0, "y": -10.0, "role": "OUTFIELD_PLAYER"},
        {"track_id": 10, "x": 20.0, "y": 10.0, "role": "OUTFIELD_PLAYER"},
    ]

    lines = discoverer.discover_lines(players, AttackDirection.POSITIVE_X)

    assert len(lines) == 3
    assert [l.player_count for l in lines] == [4, 4, 2]
    assert [l.candidate_semantic_name for l in lines] == [
        "DEFENSIVE_LINE",
        "MIDFIELD_LINE",
        "ATTACKING_LINE",
    ]
    assert lines[0].mean_x_attack == pytest.approx(-20.0)
    assert lines[1].mean_x_attack == pytest.approx(0.0)
    assert lines[2].mean_x_attack == pytest.approx(20.0)
    assert lines[0].width_y_m == pytest.approx(50.0)


def test_1d_gap_clustering_synthetic_4231() -> None:
    """Verifies that 1D gap clustering cleanly discovers 4 tactical lines for a 4-2-3-1 formation."""
    discoverer = TacticalLineDiscoverer(config=TacticalLineConfig(min_line_gap_m=6.0))

    # Gaps: (-25 to -15: 10m), (-15 to 0: 15m), (0 to +18: 18m) -> all > 6m
    players = [
        # Defense (4)
        {"track_id": 1, "x": -25.0, "y": -20.0, "role": "OUTFIELD_PLAYER"},
        {"track_id": 2, "x": -25.0, "y": -7.0, "role": "OUTFIELD_PLAYER"},
        {"track_id": 3, "x": -25.0, "y": 7.0, "role": "OUTFIELD_PLAYER"},
        {"track_id": 4, "x": -25.0, "y": 20.0, "role": "OUTFIELD_PLAYER"},
        # Defensive Midfield (2)
        {"track_id": 5, "x": -15.0, "y": -8.0, "role": "OUTFIELD_PLAYER"},
        {"track_id": 6, "x": -15.0, "y": 8.0, "role": "OUTFIELD_PLAYER"},
        # Attacking Midfield (3)
        {"track_id": 7, "x": 0.0, "y": -18.0, "role": "OUTFIELD_PLAYER"},
        {"track_id": 8, "x": 0.0, "y": 0.0, "role": "OUTFIELD_PLAYER"},
        {"track_id": 9, "x": 0.0, "y": 18.0, "role": "OUTFIELD_PLAYER"},
        # Striker (1)
        {"track_id": 10, "x": 18.0, "y": 0.0, "role": "OUTFIELD_PLAYER"},
    ]

    lines = discoverer.discover_lines(players, AttackDirection.POSITIVE_X)

    assert len(lines) == 4
    assert [l.player_count for l in lines] == [4, 2, 3, 1]
    assert [l.candidate_semantic_name for l in lines] == [
        "DEFENSIVE_LINE",
        "MIDFIELD_DEFENSIVE",
        "MIDFIELD_OFFENSIVE",
        "ATTACKING_LINE",
    ]


def test_1d_gap_clustering_intra_line_dispersion_tolerance() -> None:
    """Verifies that realistic intra-line player dispersion (e.g. 2-3m stagger) does NOT fragment a line."""
    discoverer = TacticalLineDiscoverer(config=TacticalLineConfig(min_line_gap_m=6.0))

    # Defensive line staggered between -22m and -20m (intra-line gaps <= 2.0m < 6.0m)
    # Midfield line staggered between 5m and 7m (gap from defense is 25m > 6m)
    players = [
        {"track_id": 1, "x": -22.0, "y": -20.0, "role": "OUTFIELD_PLAYER"},
        {"track_id": 2, "x": -21.0, "y": -5.0, "role": "OUTFIELD_PLAYER"},
        {"track_id": 3, "x": -20.0, "y": 5.0, "role": "OUTFIELD_PLAYER"},
        {"track_id": 4, "x": -21.5, "y": 20.0, "role": "OUTFIELD_PLAYER"},
        {"track_id": 5, "x": 5.0, "y": -10.0, "role": "OUTFIELD_PLAYER"},
        {"track_id": 6, "x": 7.0, "y": 10.0, "role": "OUTFIELD_PLAYER"},
    ]

    lines = discoverer.discover_lines(players, AttackDirection.POSITIVE_X)

    assert len(lines) == 2
    assert lines[0].player_count == 4
    assert lines[1].player_count == 2
    assert lines[0].mean_x_attack == pytest.approx(-21.125)


def test_goalkeeper_exclusion_from_lines_and_depth() -> None:
    """Verifies that goalkeeper is strictly excluded from tactical line formation and oriented team depth."""
    engine = OrientedTacticsEngine()
    players = [
        # GK far back at -50m
        {"track_id": 1, "pitch_x_m": -50.0, "pitch_y_m": 0.0, "team_label": "TEAM_0", "role": "GOALKEEPER"},
        # 4 outfield defenders at -20m
        {"track_id": 2, "pitch_x_m": -20.0, "pitch_y_m": -15.0, "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"},
        {"track_id": 3, "pitch_x_m": -20.0, "pitch_y_m": -5.0, "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"},
        {"track_id": 4, "pitch_x_m": -20.0, "pitch_y_m": 5.0, "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"},
        {"track_id": 5, "pitch_x_m": -20.0, "pitch_y_m": 15.0, "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"},
        # 2 forwards at +15m
        {"track_id": 6, "pitch_x_m": 15.0, "pitch_y_m": -5.0, "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"},
        {"track_id": 7, "pitch_x_m": 15.0, "pitch_y_m": 5.0, "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"},
    ]

    frame = engine.process_frame(1, 0.0, players, None)
    tact = frame.team_0

    assert tact.is_valid is True
    assert tact.goalkeeper_present is True
    assert tact.outfield_player_count == 6

    # Oriented depth must span only outfield: 15.0 - (-20.0) = 35.0m (NOT 65.0m!)
    assert tact.oriented_depth_m == pytest.approx(35.0)
    assert tact.team_back_x_attack == pytest.approx(-20.0)
    assert tact.team_front_x_attack == pytest.approx(15.0)

    # GK (track_id 1) must NOT be present in any tactical line
    all_line_track_ids = [tid for line in tact.lines for tid in line.player_track_ids]
    assert 1 not in all_line_track_ids


def test_inter_line_distances_and_goal_proximities() -> None:
    """Verifies calculation of inter-line distances and distances to opponent and own goals."""
    engine = OrientedTacticsEngine()
    players = [
        {"track_id": 1, "pitch_x_m": -45.0, "pitch_y_m": 0.0, "team_label": "TEAM_0", "role": "GOALKEEPER"},
        {"track_id": 2, "pitch_x_m": -20.0, "pitch_y_m": -10.0, "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"},
        {"track_id": 3, "pitch_x_m": -20.0, "pitch_y_m": 10.0, "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"},
        {"track_id": 4, "pitch_x_m": 0.0, "pitch_y_m": -10.0, "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"},
        {"track_id": 5, "pitch_x_m": 0.0, "pitch_y_m": 10.0, "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"},
        {"track_id": 6, "pitch_x_m": 25.0, "pitch_y_m": 0.0, "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"},
    ]

    frame = engine.process_frame(1, 0.0, players, None)
    tact = frame.team_0

    assert tact.line_count == 3
    # Distance between line 0 (-20m) and line 1 (0m) = 20.0m
    # Distance between line 1 (0m) and line 2 (25m) = 25.0m
    assert len(tact.inter_line_distances_m) == 2
    assert tact.inter_line_distances_m[0] == pytest.approx(20.0)
    assert tact.inter_line_distances_m[1] == pytest.approx(25.0)
    assert tact.total_inter_line_span_m == pytest.approx(45.0)

    # Goal line is at +/-52.5m. Distance to opponent goal (+52.5): 52.5 - 25.0 = 27.5m
    assert tact.distance_to_opponent_goal_m == pytest.approx(27.5)
    # Distance to own goal (-52.5): -20.0 - (-52.5) = 32.5m
    assert tact.distance_to_own_goal_m == pytest.approx(32.5)


def test_low_visibility_and_abstention_gating() -> None:
    """Verifies that frames with fewer than 4 visible outfield players abstain from line discovery."""
    engine = OrientedTacticsEngine(config=TacticalLineConfig(min_players_for_tactics=4))
    players = [
        {"track_id": 1, "pitch_x_m": -45.0, "pitch_y_m": 0.0, "team_label": "TEAM_0", "role": "GOALKEEPER"},
        {"track_id": 2, "pitch_x_m": -20.0, "pitch_y_m": -10.0, "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"},
        {"track_id": 3, "pitch_x_m": -20.0, "pitch_y_m": 10.0, "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"},
        {"track_id": 4, "pitch_x_m": 0.0, "pitch_y_m": 0.0, "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"},
    ]  # 3 outfield players < 4

    frame = engine.process_frame(1, 0.0, players, None)
    tact = frame.team_0

    assert tact.is_valid is True
    assert tact.visibility_level == "LOW"
    assert tact.line_count == 0
    assert len(tact.lines) == 0


def test_temporal_line_persistence_tracking() -> None:
    """Verifies that line tracker increments persistence frames on matching lines across consecutive calls."""
    tracker = TemporalLineTracker(max_matching_dist_m=4.5)

    line_f1 = TacticalLine(
        line_id=0,
        player_track_ids=[1, 2, 3, 4],
        player_count=4,
        mean_x_attack=-20.0,
        median_x_attack=-20.0,
        width_y_m=40.0,
        mean_pitch_x_m=-20.0,
        mean_pitch_y_m=0.0,
        confidence=0.9,
        candidate_semantic_name="DEFENSIVE_LINE",
        persistence_frames=1,
    )
    tracked_f1 = tracker.update("TEAM_0", [line_f1])
    assert tracked_f1[0].persistence_frames == 1

    # Frame 2: line moves slightly from -20.0m to -18.5m (drift = 1.5m <= 4.5m)
    line_f2 = TacticalLine(
        line_id=0,
        player_track_ids=[1, 2, 3, 4],
        player_count=4,
        mean_x_attack=-18.5,
        median_x_attack=-18.5,
        width_y_m=40.0,
        mean_pitch_x_m=-18.5,
        mean_pitch_y_m=0.0,
        confidence=0.9,
        candidate_semantic_name="DEFENSIVE_LINE",
        persistence_frames=1,
    )
    tracked_f2 = tracker.update("TEAM_0", [line_f2])
    assert tracked_f2[0].persistence_frames == 2

    # Frame 3: line teleports to 0.0m (drift = 18.5m > 4.5m) -> resets persistence
    line_f3 = TacticalLine(
        line_id=0,
        player_track_ids=[1, 2, 3, 4],
        player_count=4,
        mean_x_attack=0.0,
        median_x_attack=0.0,
        width_y_m=40.0,
        mean_pitch_x_m=0.0,
        mean_pitch_y_m=0.0,
        confidence=0.9,
        candidate_semantic_name="DEFENSIVE_LINE",
        persistence_frames=1,
    )
    tracked_f3 = tracker.update("TEAM_0", [line_f3])
    assert tracked_f3[0].persistence_frames == 1


def test_inter_team_defensive_gap() -> None:
    """Verifies calculation of longitudinal distance between opposing teams' defensive lines."""
    engine = OrientedTacticsEngine()
    # Team 0: GK at -45m (attacks +X), Defense at -20m
    # Team 1: GK at +45m (attacks -X), Defense at +25m
    players = [
        {"track_id": 1, "pitch_x_m": -45.0, "pitch_y_m": 0.0, "team_label": "TEAM_0", "role": "GOALKEEPER"},
        {"track_id": 2, "pitch_x_m": -20.0, "pitch_y_m": -10.0, "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"},
        {"track_id": 3, "pitch_x_m": -20.0, "pitch_y_m": 0.0, "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"},
        {"track_id": 4, "pitch_x_m": -20.0, "pitch_y_m": 10.0, "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"},
        {"track_id": 5, "pitch_x_m": -18.0, "pitch_y_m": 5.0, "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"},
        {"track_id": 11, "pitch_x_m": 45.0, "pitch_y_m": 0.0, "team_label": "TEAM_1", "role": "GOALKEEPER"},
        {"track_id": 12, "pitch_x_m": 25.0, "pitch_y_m": -10.0, "team_label": "TEAM_1", "role": "OUTFIELD_PLAYER"},
        {"track_id": 13, "pitch_x_m": 25.0, "pitch_y_m": 0.0, "team_label": "TEAM_1", "role": "OUTFIELD_PLAYER"},
        {"track_id": 14, "pitch_x_m": 25.0, "pitch_y_m": 10.0, "team_label": "TEAM_1", "role": "OUTFIELD_PLAYER"},
        {"track_id": 15, "pitch_x_m": 24.0, "pitch_y_m": 5.0, "team_label": "TEAM_1", "role": "OUTFIELD_PLAYER"},
    ]

    frame = engine.process_frame(1, 0.0, players, None)

    assert frame.inter_team_defensive_gap_m is not None
    # Team 0 defensive line mean pitch X ~ -19.5m, Team 1 defensive line mean pitch X ~ +24.75m
    # Gap ~ 24.75 - (-19.5) = 44.25m
    assert frame.inter_team_defensive_gap_m == pytest.approx(44.25, abs=0.1)


def test_perception_and_geometry_immutability_strictness() -> None:
    """Verifies that upstream perception (Ch 5, 6) and tactical geometry (EXP-16) remain intact."""
    from app.video_analysis.detectors import RFDETRDetector
    from app.video_analysis.player_tracker import PlayerBoTSORT
    from app.video_analysis.ball_tracker import BallTrackManager
    from app.video_analysis.team_classifier import TeamClassifier
    from app.video_analysis.temporal_calibration import TemporalPitchCalibrator
    from app.video_analysis.metric_trajectories import MetricTrajectoryEngine
    from app.video_analysis.tactical_geometry import TacticalGeometryEngine, TeamTacticalGeometry

    assert hasattr(RFDETRDetector, "detect")
    assert hasattr(PlayerBoTSORT, "update_tracks")
    assert hasattr(BallTrackManager, "update")
    assert hasattr(TeamClassifier, "fit_and_assign")
    assert hasattr(TemporalPitchCalibrator, "update")
    assert hasattr(MetricTrajectoryEngine, "process_frame")
    assert hasattr(TacticalGeometryEngine, "process_frame")
    assert hasattr(TeamTacticalGeometry, "centroid_x")
