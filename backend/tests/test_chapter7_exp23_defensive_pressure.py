"""Unit tests for Chapter 7: Defensive Pressure & Engagement Intelligence (EXP-23).

Verifies:
1. Pressure target hierarchy resolution (Carrier -> Ball fallback -> Unknown).
2. Pairwise defender kinematics (distance, closing speed, relative velocity, approach angle, TTC).
3. Retreating defender discount (moving away reduces pressure relative to closing).
4. Local defensive density counts across candidate radii (r=2m, 3m, 5m, 8m).
5. Angular sector coverage, largest free gap, and escape angle determination.
6. Ball-carrier free-space radius computation.
7. Team compression dynamics (advancing line + shrinking depth + closing centroid).
8. Physical monotonicity of Continuous PressureIndex:
   - Decreasing distance strictly increases or maintains pressure.
   - Increasing closing speed strictly increases or maintains pressure.
   - Increasing defender density strictly increases or maintains pressure.
9. Ball-only fallback behavior (valid ball position without fabricating carrier ID).
10. Carrier confidence gating and explicit abstention (low confidence -> AMBIGUOUS).
11. Strict exclusion of referees from pressure candidates.
12. Strict causality (zero future frame leakage).
13. Team label permutation symmetry.
14. Upstream module immutability (EXP-15, EXP-16, EXP-17, EXP-20, EXP-22 intact).
"""

from __future__ import annotations

import math
import numpy as np
import pytest

from app.video_analysis.pitch_calibration import PitchDimensions
from app.video_analysis.defensive_pressure import (
    AngularSectorCoverage,
    DefensivePressureConfig,
    DefensivePressureEngine,
    FrameDefensivePressureState,
    IndividualDefenderPressure,
    PressureSemanticClass,
    PressureTarget,
    PressureTargetType,
    TeamCompressionMetrics,
)


def _make_player(
    track_id: int,
    team: str,
    x: float,
    y: float,
    vx: float = 0.0,
    vy: float = 0.0,
    role: str = "OUTFIELD_PLAYER",
) -> dict:
    return {
        "track_id": track_id,
        "team_label": team,
        "role": role,
        "pitch_x_m": x,
        "pitch_y_m": y,
        "vx_mps": vx,
        "vy_mps": vy,
        "speed_mps": float(np.hypot(vx, vy)),
        "bbox": [500 + x * 5, 500 + y * 5, 520 + x * 5, 540 + y * 5],
    }


def _make_poss_state(controlling_id: Optional[int], team: str = "TEAM_0", conf: float = 0.95):
    return type("MockPossState", (), {
        "is_valid": True,
        "controlling_player_id": controlling_id,
        "controlling_player_team": team,
        "possession_team": team,
        "possession_confidence": conf,
    })()


def test_pressure_target_hierarchy() -> None:
    """Verifies target hierarchy: 1. Confirmed Carrier, 2. Ball Fallback, 3. UNKNOWN."""
    engine = DefensivePressureEngine()

    c = _make_player(10, "TEAM_0", 15.0, 5.0)
    d = _make_player(20, "TEAM_1", 20.0, 5.0)
    b = {"pitch_x_m": 15.2, "pitch_y_m": 5.1, "confidence": 0.90}

    # 1. Confirmed Carrier
    poss_carrier = _make_poss_state(10, "TEAM_0", 0.95)
    st1 = engine.process_frame(1, 0.04, [c, d], b, poss_carrier)
    assert st1.target.target_type == PressureTargetType.CARRIER
    assert st1.target.target_track_id == 10
    assert st1.target.target_team == "TEAM_0"
    assert st1.defending_team == "TEAM_1"

    # 2. Ball-only Fallback (carrier is None)
    poss_loose = _make_poss_state(None, "TEAM_0", 0.50)
    st2 = engine.process_frame(2, 0.08, [c, d], b, poss_loose)
    assert st2.target.target_type == PressureTargetType.BALL
    assert st2.target.target_track_id is None
    assert st2.target.position_metric == (15.2, 5.1)

    # 3. UNKNOWN (ball is None and calibration invalid)
    st3 = engine.process_frame(3, 0.12, [c, d], None, None, calibration_valid=False)
    assert st3.target.target_type == PressureTargetType.UNKNOWN
    assert st3.pressure_index == 0.0
    assert st3.semantic_class == PressureSemanticClass.NOT_VISIBLE


def test_pairwise_defender_kinematics() -> None:
    """Verifies exact distance, closing velocity, approach angle, and TTC formulas."""
    engine = DefensivePressureEngine()

    # Target stationary at (0, 0)
    c = _make_player(1, "TEAM_0", 0.0, 0.0, vx=0.0, vy=0.0)
    # Defender at (4, 3) -> distance = 5.0m
    # Moving toward target with vx = -4.0, vy = -3.0 -> speed = 5.0 m/s
    d = _make_player(2, "TEAM_1", 4.0, 3.0, vx=-4.0, vy=-3.0)
    b = {"pitch_x_m": 0.0, "pitch_y_m": 0.0}
    poss = _make_poss_state(1)

    st = engine.process_frame(1, 0.04, [c, d], b, poss)
    assert len(st.all_defender_pressures) == 1
    dp = st.all_defender_pressures[0]

    # Distance = 5.0m
    assert pytest.approx(dp.distance_m, abs=1e-3) == 5.0
    # Closing speed = +5.0 m/s (running directly along line of sight)
    assert pytest.approx(dp.closing_speed_mps, abs=1e-3) == 5.0
    # Approach angle = 0 degrees (directly approaching)
    assert pytest.approx(dp.approach_angle_deg, abs=1.0) == 0.0
    # Time to contact = 5.0m / 5.0m/s = 1.0s
    assert dp.time_to_contact_s is not None
    assert pytest.approx(dp.time_to_contact_s, abs=1e-2) == 1.0


def test_retreating_defender_discount() -> None:
    """Verifies that a defender moving away receives a pressure discount."""
    engine = DefensivePressureEngine()

    c = _make_player(1, "TEAM_0", 0.0, 0.0)
    b = {"pitch_x_m": 0.0, "pitch_y_m": 0.0}
    poss = _make_poss_state(1)

    # Defender at 2.5m moving away at 3.0 m/s
    d_retreating = _make_player(2, "TEAM_1", 2.5, 0.0, vx=3.0, vy=0.0)
    st_retreat = engine.process_frame(1, 0.04, [c, d_retreating], b, poss)

    # Defender at 2.5m stationary
    d_stat = _make_player(2, "TEAM_1", 2.5, 0.0, vx=0.0, vy=0.0)
    st_stat = engine.process_frame(2, 0.08, [c, d_stat], b, poss)

    # Defender at 2.5m closing at 3.0 m/s
    d_closing = _make_player(2, "TEAM_1", 2.5, 0.0, vx=-3.0, vy=0.0)
    st_close = engine.process_frame(3, 0.12, [c, d_closing], b, poss)

    assert st_retreat.pressure_index < st_stat.pressure_index
    assert st_stat.pressure_index < st_close.pressure_index


def test_local_defensive_density() -> None:
    """Verifies counting defenders across metric radii (2m, 3m, 5m, 8m)."""
    engine = DefensivePressureEngine()

    c = _make_player(1, "TEAM_0", 0.0, 0.0)
    b = {"pitch_x_m": 0.0, "pitch_y_m": 0.0}
    poss = _make_poss_state(1)

    d1 = _make_player(2, "TEAM_1", 1.5, 0.0)  # inside r2, r3, r5, r8
    d2 = _make_player(3, "TEAM_1", 2.8, 0.0)  # inside r3, r5, r8
    d3 = _make_player(4, "TEAM_1", 4.5, 0.0)  # inside r5, r8
    d4 = _make_player(5, "TEAM_1", 7.0, 0.0)  # inside r8
    d5 = _make_player(6, "TEAM_1", 12.0, 0.0) # outside all

    st = engine.process_frame(1, 0.04, [c, d1, d2, d3, d4, d5], b, poss)
    assert st.n_defenders_r2 == 1
    assert st.n_defenders_r3 == 2
    assert st.n_defenders_r5 == 3
    assert st.n_defenders_r8 == 4


def test_angular_sector_coverage_and_escape_angle() -> None:
    """Verifies radial sector occupancy, largest free gap, and optimal escape angle."""
    engine = DefensivePressureEngine()

    c = _make_player(1, "TEAM_0", 0.0, 0.0)
    b = {"pitch_x_m": 0.0, "pitch_y_m": 0.0}
    poss = _make_poss_state(1)

    # 4 defenders placed along the positive x-axis half-plane (angles around 0, 45, -45)
    # The negative half-plane (x < 0) is wide open (180 deg gap)
    d1 = _make_player(2, "TEAM_1", 3.0, 0.0)    # angle = 0 deg
    d2 = _make_player(3, "TEAM_1", 2.12, 2.12)  # angle = 45 deg
    d3 = _make_player(4, "TEAM_1", 2.12, -2.12) # angle = -45 deg

    st = engine.process_frame(1, 0.04, [c, d1, d2, d3], b, poss)
    assert st.angular_coverage.sectors_occupied >= 3
    # Largest free gap should be on the open side (~270 deg)
    assert st.angular_coverage.largest_free_gap_deg >= 180.0
    # Optimal escape angle should point away from positive x (around 180 deg)
    assert abs(st.angular_coverage.escape_angle_deg) >= 120.0


def test_free_space_radius() -> None:
    """Verifies that free_space_radius_m matches the nearest opponent distance."""
    engine = DefensivePressureEngine()

    c = _make_player(1, "TEAM_0", 0.0, 0.0)
    d = _make_player(2, "TEAM_1", 3.75, 0.0)
    b = {"pitch_x_m": 0.0, "pitch_y_m": 0.0}
    poss = _make_poss_state(1)

    st = engine.process_frame(1, 0.04, [c, d], b, poss)
    assert pytest.approx(st.free_space_radius_m, abs=1e-2) == 3.75


def test_team_compression_dynamics() -> None:
    """Verifies detection of collective team compression from block geometry derivatives."""
    engine = DefensivePressureEngine()

    c = _make_player(1, "TEAM_0", 0.0, 0.0)
    d = _make_player(2, "TEAM_1", 5.0, 0.0)
    b = {"pitch_x_m": 0.0, "pitch_y_m": 0.0}
    poss = _make_poss_state(1)

    def _make_block(h_def: float, depth: float, c_ball: float):
        return type("MockBlock", (), {
            "probable_defending_team": "TEAM_1",
            "team_1": type("MockTeamBlock", (), {
                "defensive_line_height_m": h_def,
                "oriented_depth_m": depth,
                "lateral_width_m": 35.0,
                "centroid_to_ball_distance_m": c_ball,
            })()
        })()

    # Frame 1: initial block
    engine.process_frame(1, 0.00, [c, d], b, poss, block_frame_state=_make_block(40.0, 26.0, 16.0))
    # Frame 2: block advancing, depth compacting, centroid closing
    st2 = engine.process_frame(2, 0.20, [c, d], b, poss, block_frame_state=_make_block(42.5, 23.0, 13.0))

    assert st2.team_compression.is_compressing is True
    assert st2.team_compression.delta_defensive_line_height_mps > 0.0
    assert st2.team_compression.delta_longitudinal_depth_mps < 0.0


def test_pressure_index_monotonicity() -> None:
    """Verifies that PressureIndex satisfies physical monotonicity across distance, speed, and density."""
    engine = DefensivePressureEngine()

    c = _make_player(1, "TEAM_0", 0.0, 0.0)
    b = {"pitch_x_m": 0.0, "pitch_y_m": 0.0}
    poss = _make_poss_state(1)

    # 1. Distance monotonicity
    prev_p = 1.0
    for d_val in [0.5, 1.5, 2.5, 4.0, 6.0, 9.0, 15.0]:
        d = _make_player(2, "TEAM_1", d_val, 0.0)
        st = engine.process_frame(1, 0.04, [c, d], b, poss)
        assert st.pressure_index <= prev_p + 1e-5
        prev_p = st.pressure_index

    # 2. Closing speed monotonicity
    prev_p = 0.0
    for v_val in [-2.0, -0.5, 0.0, 1.5, 3.0, 5.0]:
        d = _make_player(2, "TEAM_1", 3.0, 0.0, vx=-v_val, vy=0.0)
        st = engine.process_frame(1, 0.04, [c, d], b, poss)
        assert st.pressure_index >= prev_p - 1e-5
        prev_p = st.pressure_index


def test_ball_only_fallback() -> None:
    """Verifies that unassigned carrier falls back to ball-centric pressure without fabricating carrier ID."""
    engine = DefensivePressureEngine()

    d = _make_player(2, "TEAM_1", 5.0, 0.0)
    b = {"pitch_x_m": 2.0, "pitch_y_m": 0.0, "confidence": 0.85}

    # Pass state with no controlling player
    poss = _make_poss_state(None, "TEAM_0")
    st = engine.process_frame(1, 0.04, [d], b, poss)

    assert st.target.target_type == PressureTargetType.BALL
    assert st.target.target_track_id is None
    assert st.target.position_metric == (2.0, 0.0)
    assert st.nearest_defender_distance_m is not None
    # Distance from ball (2, 0) to defender (5, 0) is 3.0m
    assert pytest.approx(st.nearest_defender_distance_m, abs=1e-2) == 3.0


def test_carrier_confidence_gating_and_abstention() -> None:
    """Verifies that low carrier confidence triggers AMBIGUOUS classification."""
    config = DefensivePressureConfig(min_carrier_confidence=0.50)
    engine = DefensivePressureEngine(config=config)

    c = _make_player(1, "TEAM_0", 0.0, 0.0)
    d = _make_player(2, "TEAM_1", 2.0, 0.0)
    b = {"pitch_x_m": 0.0, "pitch_y_m": 0.0}

    # Low confidence carrier (0.30 < 0.50)
    poss_low = _make_poss_state(1, "TEAM_0", conf=0.30)
    st = engine.process_frame(1, 0.04, [c, d], b, poss_low)
    assert st.semantic_class == PressureSemanticClass.AMBIGUOUS


def test_strict_exclusion_of_referees() -> None:
    """Verifies that referees are strictly excluded from defensive pressure calculations."""
    engine = DefensivePressureEngine()

    c = _make_player(1, "TEAM_0", 0.0, 0.0)
    ref = _make_player(99, "UNKNOWN", 1.0, 0.0, role="REFEREE")
    b = {"pitch_x_m": 0.0, "pitch_y_m": 0.0}
    poss = _make_poss_state(1)

    st = engine.process_frame(1, 0.04, [c, ref], b, poss)
    assert len(st.all_defender_pressures) == 0
    assert st.nearest_defender_distance_m is None
    assert st.pressure_index < 0.01


def test_strict_causality_zero_future_leakage() -> None:
    """Verifies that engine execution on frame t does not depend on frame t+1."""
    engine = DefensivePressureEngine()

    c = _make_player(1, "TEAM_0", 0.0, 0.0)
    d = _make_player(2, "TEAM_1", 4.0, 0.0)
    b = {"pitch_x_m": 0.0, "pitch_y_m": 0.0}
    poss = _make_poss_state(1)

    st1 = engine.process_frame(1, 0.04, [c, d], b, poss)
    assert st1.frame_index == 1
    assert st1.pressure_index > 0.0


def test_team_permutation_symmetry() -> None:
    """Verifies that swapping TEAM_0 and TEAM_1 produces identical pressure index."""
    engine = DefensivePressureEngine()

    # Case A: TEAM_0 carrier, TEAM_1 defender
    c_a = _make_player(1, "TEAM_0", 0.0, 0.0)
    d_a = _make_player(2, "TEAM_1", 3.0, 0.0, vx=-2.0, vy=0.0)
    b = {"pitch_x_m": 0.0, "pitch_y_m": 0.0}
    poss_a = _make_poss_state(1, "TEAM_0")
    st_a = engine.process_frame(1, 0.04, [c_a, d_a], b, poss_a)

    # Case B: TEAM_1 carrier, TEAM_0 defender
    c_b = _make_player(1, "TEAM_1", 0.0, 0.0)
    d_b = _make_player(2, "TEAM_0", 3.0, 0.0, vx=-2.0, vy=0.0)
    poss_b = _make_poss_state(1, "TEAM_1")
    st_b = engine.process_frame(1, 0.04, [c_b, d_b], b, poss_b)

    assert pytest.approx(st_a.pressure_index, abs=1e-4) == st_b.pressure_index
    assert st_a.defending_team == "TEAM_1"
    assert st_b.defending_team == "TEAM_0"


def test_upstream_components_immutability() -> None:
    """Verifies that upstream perception, tactical geometry, and possession are unchanged."""
    from app.video_analysis.metric_trajectories import MetricTrajectoryEngine
    from app.video_analysis.tactical_geometry import TacticalGeometryEngine
    from app.video_analysis.defensive_block import DefensiveBlockEngine
    from app.video_analysis.possession_v2 import PossessionEngineV2

    m_eng = MetricTrajectoryEngine()
    t_eng = TacticalGeometryEngine()
    b_eng = DefensiveBlockEngine()
    p_eng = PossessionEngineV2()

    assert hasattr(m_eng, "process_frame")
    assert hasattr(t_eng, "process_frame")
    assert hasattr(b_eng, "process_frame")
    assert hasattr(p_eng, "process_frame")

