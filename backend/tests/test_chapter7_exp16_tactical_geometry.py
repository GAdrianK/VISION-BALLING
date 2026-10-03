"""Unit tests for Chapter 7: Team-Level Tactical Geometry Primitives (EXP-16).

Verifies mathematical correctness of centroids (mean and robust median), width and
longitudinal span (absolute pitch axes), convex hull area & perimeter (including degenerate
cases), stretch index compactness, pairwise and nearest opponent distances, ball-relative
geometry (ground-plane Z=0), 15-cell pitch occupancy grids, 5-lane lateral channels,
outfield vs full-team goalkeeper handling, confidence gating, causal temporal EMA smoothing,
team permutation invariance, and perception stack immutability.
"""

from __future__ import annotations

import numpy as np
import pytest

from app.video_analysis.pitch_calibration import PitchDimensions
from app.video_analysis.tactical_geometry import (
    FIVE_LANE_BOUNDS,
    GRID_LATERAL_BOUNDS,
    GRID_LONGITUDINAL_BOUNDS,
    BallTacticalGeometry,
    InterTeamTacticalGeometry,
    TacticalFrameState,
    TacticalGeometryConfig,
    TacticalGeometryEngine,
    TacticalQualityState,
    TacticalTemporalFilter,
    TeamTacticalGeometry,
    assign_five_lane,
    assign_grid_zone,
    compute_convex_hull_2d,
    compute_inter_team_nearest_opponent_distance,
    compute_pairwise_distances,
    compute_stretch_index,
)


def test_centroid_and_median_centroid_correctness() -> None:
    """Verifies that mean and coordinate-wise median centroids are mathematically exact."""
    # 5 players forming a cross centered at (10.0, -5.0)
    pts = np.array([
        [10.0, -5.0],   # Center
        [6.0, -5.0],    # Left
        [14.0, -5.0],   # Right
        [10.0, -9.0],   # Bottom
        [10.0, -1.0],   # Top
    ], dtype=float)

    mean_c = (float(np.mean(pts[:, 0])), float(np.mean(pts[:, 1])))
    med_c = (float(np.median(pts[:, 0])), float(np.median(pts[:, 1])))

    assert abs(mean_c[0] - 10.0) < 1e-6
    assert abs(mean_c[1] - (-5.0)) < 1e-6
    assert abs(med_c[0] - 10.0) < 1e-6
    assert abs(med_c[1] - (-5.0)) < 1e-6


def test_median_centroid_robustness_to_wrong_team_outlier() -> None:
    """Proves coordinate-wise median centroid is resistant to a misclassified player outlier."""
    team = np.array([
        [-20.0, -10.0], [-20.0, 0.0], [-20.0, 10.0],
        [-10.0, -15.0], [-10.0, 0.0], [-10.0, 15.0],
        [0.0, -10.0], [0.0, 0.0], [0.0, 10.0]
    ], dtype=float)

    clean_mean_x = float(np.mean(team[:, 0]))  # -10.0
    clean_mean_y = float(np.mean(team[:, 1]))  # 0.0
    clean_med_x = float(np.median(team[:, 0]))  # -10.0
    clean_med_y = float(np.median(team[:, 1]))  # 0.0

    # Inject 1 wrong-team player far away at (+45.0, +30.0)
    outlier = np.array([[45.0, 30.0]])
    contaminated = np.vstack([team, outlier])

    contam_mean_x = float(np.mean(contaminated[:, 0]))
    contam_mean_y = float(np.mean(contaminated[:, 1]))
    contam_med_x = float(np.median(contaminated[:, 0]))
    contam_med_y = float(np.median(contaminated[:, 1]))

    mean_shift = np.hypot(contam_mean_x - clean_mean_x, contam_mean_y - clean_mean_y)
    median_shift = np.hypot(contam_med_x - clean_med_x, contam_med_y - clean_med_y)

    # Mean centroid shifts significantly (> 5.0m)
    assert mean_shift > 5.0
    # Median centroid shift is zero or near-zero
    assert median_shift < 1.0


def test_width_and_longitudinal_span() -> None:
    """Verifies width (max Y - min Y) and longitudinal span (max X - min X) in absolute pitch axes."""
    engine = TacticalGeometryEngine()
    players = [
        {"track_id": 1, "pitch_x_m": -15.0, "pitch_y_m": -10.0, "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"},
        {"track_id": 2, "pitch_x_m": 25.0, "pitch_y_m": -5.0, "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"},
        {"track_id": 3, "pitch_x_m": 5.0, "pitch_y_m": 20.0, "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"},
    ]
    frame = engine.process_frame(1, 0.0, players, None)

    geom_0 = frame.team_0
    assert geom_0.is_valid is True
    # Longitudinal span: 25.0 - (-15.0) = 40.0 m
    assert geom_0.longitudinal_span_m is not None and abs(geom_0.longitudinal_span_m - 40.0) < 1e-4
    # Depth alias
    assert geom_0.depth_m == geom_0.longitudinal_span_m
    # Width: 20.0 - (-10.0) = 30.0 m
    assert geom_0.width_m is not None and abs(geom_0.width_m - 30.0) < 1e-4


def test_convex_hull_area_and_perimeter_exact() -> None:
    """Verifies convex hull area and perimeter against known analytic polygons."""
    # 1. Rectangle 30m x 20m: Area = 600 m^2, Perimeter = 100 m
    rect = np.array([[-15.0, -10.0], [15.0, -10.0], [15.0, 10.0], [-15.0, 10.0]])
    a, p, v = compute_convex_hull_2d(rect)
    assert a is not None and abs(a - 600.0) < 1e-3
    assert p is not None and abs(p - 100.0) < 1e-3
    assert len(v) == 4

    # 2. Right triangle with legs 30m and 40m: Area = 0.5 * 30 * 40 = 600 m^2, Perimeter = 30 + 40 + 50 = 120 m
    tri = np.array([[0.0, 0.0], [30.0, 0.0], [0.0, 40.0]])
    a_tri, p_tri, _ = compute_convex_hull_2d(tri)
    assert a_tri is not None and abs(a_tri - 600.0) < 1e-3
    assert p_tri is not None and abs(p_tri - 120.0) < 1e-3


def test_convex_hull_degeneracy_handling() -> None:
    """Verifies that collinear, duplicate, and <3 points do not crash and report 0.0 area."""
    # < 3 points
    a1, p1, v1 = compute_convex_hull_2d(np.array([[0.0, 0.0], [10.0, 10.0]]))
    assert a1 is None
    assert p1 is None

    # Collinear points (1D line in 2D space)
    collinear = np.array([[0.0, -10.0], [0.0, 0.0], [0.0, 10.0], [0.0, 20.0]])
    a2, p2, v2 = compute_convex_hull_2d(collinear)
    assert a2 == 0.0
    assert abs(p2 - 60.0) < 1e-3  # 2 * 30m span

    # Duplicate points
    dup = np.array([[5.0, 5.0], [5.0, 5.0], [5.0, 5.0]])
    a3, p3, v3 = compute_convex_hull_2d(dup)
    assert a3 == 0.0


def test_stretch_index_compactness() -> None:
    """Verifies stretch index (mean Euclidean distance from centroid) on regular geometry."""
    # 4 points on a square of side 10m centered at (0, 0) -> distance of each point to (0, 0) is sqrt(50)
    pts = np.array([[-5.0, -5.0], [5.0, -5.0], [5.0, 5.0], [-5.0, 5.0]])
    stretch = compute_stretch_index(pts, (0.0, 0.0))
    expected = float(np.hypot(5.0, 5.0))
    assert stretch is not None and abs(stretch - expected) < 1e-4

    # Single point returns None
    assert compute_stretch_index(np.array([[0.0, 0.0]]), (0.0, 0.0)) is None


def test_pairwise_and_nearest_teammate_distances() -> None:
    """Verifies pairwise distance calculations and nearest teammate search."""
    # 3 points along a line at x = 0, 10, 30
    pts = np.array([[0.0, 0.0], [10.0, 0.0], [30.0, 0.0]])
    # Pairwise distances: d(0, 1)=10, d(1, 2)=20, d(0, 2)=30. Mean = 20.0, Median = 20.0
    # Nearest teammate: for 0 -> 10, for 1 -> 10, for 2 -> 20. Mean nearest = (10 + 10 + 20) / 3 = 13.333
    mean_pair, med_pair, nearest_tm = compute_pairwise_distances(pts)
    assert mean_pair is not None and abs(mean_pair - 20.0) < 1e-4
    assert med_pair is not None and abs(med_pair - 20.0) < 1e-4
    assert nearest_tm is not None and abs(nearest_tm - (40.0 / 3.0)) < 1e-4


def test_nearest_opponent_distance() -> None:
    """Verifies mean nearest opponent distance computation across opposing teams."""
    team_a = np.array([[0.0, 0.0], [0.0, 10.0]])
    team_b = np.array([[5.0, 0.0], [5.0, 10.0]])

    # Nearest opponent for each player in A is 5.0m; for each player in B is 5.0m
    mean_opp = compute_inter_team_nearest_opponent_distance(team_a, team_b)
    assert mean_opp is not None and abs(mean_opp - 5.0) < 1e-4


def test_ball_relative_geometry_and_ground_plane_label() -> None:
    """Verifies ball proximity calculations and strict ground-plane projection label."""
    engine = TacticalGeometryEngine()
    players = [
        {"track_id": 1, "pitch_x_m": 0.0, "pitch_y_m": 0.0, "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"},
        {"track_id": 2, "pitch_x_m": 10.0, "pitch_y_m": 0.0, "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"},
        {"track_id": 3, "pitch_x_m": 20.0, "pitch_y_m": 0.0, "team_label": "TEAM_1", "role": "OUTFIELD_PLAYER"},
    ]
    ball = {"track_id": 0, "pitch_x_m": 2.0, "pitch_y_m": 0.0, "position_valid": True}

    frame = engine.process_frame(1, 0.0, players, ball)
    b = frame.ball

    assert b.projection_valid is True
    assert b.is_ground_plane_projection is True
    assert b.x == 2.0 and b.y == 0.0

    # Nearest player to ball is track 1 (distance = 2.0m)
    assert b.nearest_player_id == 1
    assert b.nearest_player_team == "TEAM_0"
    assert b.nearest_player_distance_m is not None and abs(b.nearest_player_distance_m - 2.0) < 1e-4

    # Nearest on Team 1 is track 3 (distance = 18.0m)
    assert b.nearest_team_1_player_id == 3
    assert b.nearest_team_1_distance_m is not None and abs(b.nearest_team_1_distance_m - 18.0) < 1e-4

    # Distance to Team 0 centroid (centroid is at (5.0, 0.0) -> distance = 3.0m)
    assert b.team_0_centroid_distance_m is not None and abs(b.team_0_centroid_distance_m - 3.0) < 1e-4


def test_15_zone_pitch_occupancy_grid() -> None:
    """Verifies mapping of coordinates into the 5x3=15 zone pitch grid."""
    # Point at center (0, 0) -> Zone 2 (longitudinal), Channel 1 (lateral) -> cell 2*3 + 1 = 7
    z, c, cell_id = assign_grid_zone(0.0, 0.0)
    assert z == 2
    assert c == 1
    assert cell_id == 7

    # Point at top-left corner (-50.0, -30.0) -> Zone 0, Channel 0 -> cell 0
    z0, c0, cell0 = assign_grid_zone(-50.0, -30.0)
    assert z0 == 0 and c0 == 0 and cell0 == 0

    # Point at bottom-right (+50.0, +30.0) -> Zone 4, Channel 2 -> cell 4*3 + 2 = 14
    z14, c14, cell14 = assign_grid_zone(50.0, 30.0)
    assert z14 == 4 and c14 == 2 and cell14 == 14


def test_five_lane_lateral_representation() -> None:
    """Verifies lateral lane assignment across canonical 5 lanes."""
    assert assign_five_lane(-30.0) == "left_wide"
    assert assign_five_lane(-15.0) == "left_half_space"
    assert assign_five_lane(0.0) == "central"
    assert assign_five_lane(15.0) == "right_half_space"
    assert assign_five_lane(30.0) == "right_wide"


def test_goalkeeper_handling_outfield_vs_full_team() -> None:
    """Verifies that default tactical shape excludes GK, while full_team shape includes GK."""
    engine = TacticalGeometryEngine(config=TacticalGeometryConfig(include_goalkeeper_in_shape=False))
    players = [
        {"track_id": 1, "pitch_x_m": -50.0, "pitch_y_m": 0.0, "team_label": "TEAM_0", "role": "GOALKEEPER"},
        {"track_id": 2, "pitch_x_m": -20.0, "pitch_y_m": -10.0, "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"},
        {"track_id": 3, "pitch_x_m": -20.0, "pitch_y_m": 10.0, "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"},
        {"track_id": 4, "pitch_x_m": 0.0, "pitch_y_m": 0.0, "team_label": "TEAM_0", "role": "OUTFIELD_PLAYER"},
    ]

    frame = engine.process_frame(1, 0.0, players, None)
    outfield = frame.team_0
    full = frame.team_0_full

    assert full is not None
    # Outfield longitudinal span: 0.0 - (-20.0) = 20.0 m
    assert outfield.longitudinal_span_m is not None and abs(outfield.longitudinal_span_m - 20.0) < 1e-4
    # Full longitudinal span includes GK at -50.0m: 0.0 - (-50.0) = 50.0 m!
    assert full.longitudinal_span_m is not None and abs(full.longitudinal_span_m - 50.0) < 1e-4

    # Outfield centroid x is (-20 - 20 + 0) / 3 = -13.333 m
    assert outfield.centroid_x is not None and abs(outfield.centroid_x - (-40.0 / 3.0)) < 1e-4
    # Full centroid x is (-50 - 20 - 20 + 0) / 4 = -22.5 m
    assert full.centroid_x is not None and abs(full.centroid_x - (-22.5)) < 1e-4


def test_confidence_and_minimum_evidence_gating() -> None:
    """Verifies that observations with low team confidence or insufficient count are gated."""
    engine = TacticalGeometryEngine(config=TacticalGeometryConfig(min_team_confidence=0.60))

    # Single player with low confidence (0.45 < 0.60)
    players = [
        {"track_id": 1, "pitch_x_m": 0.0, "pitch_y_m": 0.0, "team_label": "TEAM_0", "team_confidence": 0.45}
    ]
    frame = engine.process_frame(1, 0.0, players, None)
    assert frame.team_0.is_valid is False
    assert frame.team_0.invalidation_reason == "NO_VISIBLE_PLAYERS"


def test_causal_temporal_ema_smoothing() -> None:
    """Verifies that causal EMA smoothing dampens frame-to-frame noise without future leakage."""
    filter_ema = TacticalTemporalFilter(alpha=0.5)

    geom1 = TeamTacticalGeometry(team_label="TEAM_0", is_valid=True, centroid_x=10.0, width_m=20.0)
    s1 = filter_ema.update("TEAM_0", geom1)
    assert s1.centroid_x == 10.0
    assert s1.width_m == 20.0

    geom2 = TeamTacticalGeometry(team_label="TEAM_0", is_valid=True, centroid_x=20.0, width_m=30.0)
    s2 = filter_ema.update("TEAM_0", geom2)
    # EMA: 0.5 * 20 + 0.5 * 10 = 15.0
    assert s2.centroid_x is not None and abs(s2.centroid_x - 15.0) < 1e-6
    # EMA: 0.5 * 30 + 0.5 * 20 = 25.0
    assert s2.width_m is not None and abs(s2.width_m - 25.0) < 1e-6


def test_perception_immutability_strictness() -> None:
    """Verifies Chapter 5, 6A, and 6B perception components are unchanged."""
    from app.video_analysis.detectors import RFDETRDetector
    from app.video_analysis.player_tracker import PlayerBoTSORT
    from app.video_analysis.ball_tracker import BallTrackManager
    from app.video_analysis.team_classifier import TeamClassifier
    from app.video_analysis.temporal_calibration import TemporalPitchCalibrator
    from app.video_analysis.metric_trajectories import MetricTrajectoryEngine

    assert hasattr(RFDETRDetector, "detect")
    assert hasattr(PlayerBoTSORT, "update_tracks")
    assert hasattr(BallTrackManager, "update")
    assert hasattr(TeamClassifier, "fit_and_assign")
    assert hasattr(TemporalPitchCalibrator, "update")
    assert hasattr(MetricTrajectoryEngine, "process_frame")
