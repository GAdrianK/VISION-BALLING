"""Tactical Geometry Primitives Engine (EXP-16 / Chapter 7).

Computes deterministic, confidence-aware team-level spatial primitives from frozen
metric trajectories. Includes mean & coordinate-wise median centroids, width and
longitudinal span (in absolute pitch coordinates), convex hull area & perimeter,
stretch index (compactness), pairwise & nearest-opponent distances, ball proximity,
canonical 15-cell pitch occupancy grids, 5-lane lateral channel representations,
and causal temporal smoothing (EMA).
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
from scipy.spatial import ConvexHull, QhullError

try:
    from app.video_analysis.pitch_calibration import PitchDimensions
    from app.video_analysis.metric_trajectories import (
        PlayerMetricObservation,
        BallMetricObservation,
    )
except ImportError:
    from backend.app.video_analysis.pitch_calibration import PitchDimensions
    from backend.app.video_analysis.metric_trajectories import (
        PlayerMetricObservation,
        BallMetricObservation,
    )

logger = logging.getLogger(__name__)

# ==============================================================================
# CANONICAL PITCH GRIDS & LANE BOUNDARIES (Nominal FIFA 105.0m x 68.0m)
# ==============================================================================

# 15-zone Pitch Grid (5 longitudinal zones x 3 lateral channels)
# Longitudinal X in [-52.5, +52.5] -> 5 zones of 21.0m
GRID_LONGITUDINAL_BOUNDS: List[float] = [-52.5, -31.5, -10.5, 10.5, 31.5, 52.5]

# Lateral Y in [-34.0, +34.0] -> 3 channels of 22.667m
GRID_LATERAL_BOUNDS: List[float] = [-34.0, -34.0 / 3.0, 34.0 / 3.0, 34.0]

# Canonical Five-Lane Lateral Divisions (Guardiola / Positional Play standard)
# 5 equal lanes of 13.6m across width Y in [-34.0, +34.0]
FIVE_LANE_BOUNDS: Dict[str, Tuple[float, float]] = {
    "left_wide": (-34.0, -20.4),
    "left_half_space": (-20.4, -6.8),
    "central": (-6.8, 6.8),
    "right_half_space": (6.8, 20.4),
    "right_wide": (20.4, 34.0),
}


def assign_grid_zone(x: float, y: float) -> Tuple[int, int, int]:
    """Maps pitch metric coordinates (x, y) into a 15-zone cell index.

    Returns:
        (zone_idx, channel_idx, cell_id) where zone_idx in [0, 4],
        channel_idx in [0, 2], and cell_id in [0, 14].
    """
    # Longitudinal zone (0 to 4)
    z_idx = 0
    if x >= GRID_LONGITUDINAL_BOUNDS[4]:
        z_idx = 4
    elif x <= GRID_LONGITUDINAL_BOUNDS[1]:
        z_idx = 0
    else:
        for i in range(1, 5):
            if GRID_LONGITUDINAL_BOUNDS[i] <= x < GRID_LONGITUDINAL_BOUNDS[i + 1]:
                z_idx = i
                break

    # Lateral channel (0 to 2)
    c_idx = 0
    if y >= GRID_LATERAL_BOUNDS[2]:
        c_idx = 2
    elif y <= GRID_LATERAL_BOUNDS[1]:
        c_idx = 0
    else:
        c_idx = 1

    cell_id = z_idx * 3 + c_idx
    return z_idx, c_idx, cell_id


def assign_five_lane(y: float) -> str:
    """Maps lateral coordinate y (meters) into one of the canonical 5 lateral lanes."""
    for lane_name, (y_min, y_max) in FIVE_LANE_BOUNDS.items():
        if y_min <= y <= y_max:
            return lane_name
    if y < -34.0:
        return "left_wide"
    return "right_wide"


def compute_convex_hull_2d(points: np.ndarray) -> Tuple[Optional[float], Optional[float], List[Tuple[float, float]]]:
    """Computes 2D convex hull area (m^2), perimeter (m), and vertices list.

    Handles degeneracy (< 3 points, collinearity, duplicate points) robustly.
    """
    if len(points) < 3:
        return None, None, []

    unique_pts = np.unique(points, axis=0)
    if len(unique_pts) < 3:
        return 0.0, 0.0, []

    # Check collinearity via rank of centered coordinates
    centered = unique_pts - unique_pts.mean(axis=0)
    if np.linalg.matrix_rank(centered, tol=1e-5) < 2:
        diff = unique_pts.max(axis=0) - unique_pts.min(axis=0)
        length = float(np.hypot(diff[0], diff[1]))
        return 0.0, 2.0 * length, [(float(p[0]), float(p[1])) for p in unique_pts]

    try:
        hull = ConvexHull(unique_pts)
        # Note: In SciPy ConvexHull in 2D, hull.volume is area (m^2) and hull.area is perimeter (m)
        area_m2 = float(hull.volume)
        perimeter_m = float(hull.area)
        vertices = [(float(unique_pts[v, 0]), float(unique_pts[v, 1])) for v in hull.vertices]
        return area_m2, perimeter_m, vertices
    except QhullError:
        return 0.0, 0.0, []


def compute_stretch_index(points: np.ndarray, centroid: Tuple[float, float]) -> Optional[float]:
    """Computes stretch index: mean Euclidean distance of players from team centroid.

    Formula: stretch_index = (1/N) * sum(||p_i - C||_2)
    """
    if len(points) < 2:
        return None
    dists = np.hypot(points[:, 0] - centroid[0], points[:, 1] - centroid[1])
    return float(np.mean(dists))


def compute_pairwise_distances(points: np.ndarray) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """Computes mean pairwise, median pairwise, and mean nearest teammate distance."""
    n = len(points)
    if n < 2:
        return None, None, None

    # Compute Euclidean distance matrix
    diff = points[:, np.newaxis, :] - points[np.newaxis, :, :]
    dist_matrix = np.hypot(diff[:, :, 0], diff[:, :, 1])

    # Extract upper triangle for pairwise distances
    triu_indices = np.triu_indices(n, k=1)
    pairwise_dists = dist_matrix[triu_indices]

    mean_pairwise = float(np.mean(pairwise_dists))
    median_pairwise = float(np.median(pairwise_dists))

    # Nearest teammate distance per player (masking diagonal)
    np.fill_diagonal(dist_matrix, np.inf)
    nearest_teammate_dists = np.min(dist_matrix, axis=1)
    mean_nearest = float(np.mean(nearest_teammate_dists))

    return mean_pairwise, median_pairwise, mean_nearest


def compute_inter_team_nearest_opponent_distance(points_a: np.ndarray, points_b: np.ndarray) -> Optional[float]:
    """Computes mean distance to the nearest opponent across both teams."""
    if len(points_a) == 0 or len(points_b) == 0:
        return None

    # Distance matrix between team A and team B
    diff = points_a[:, np.newaxis, :] - points_b[np.newaxis, :, :]
    dists = np.hypot(diff[:, :, 0], diff[:, :, 1])

    nearest_a_to_b = np.min(dists, axis=1)
    nearest_b_to_a = np.min(dists, axis=0)

    all_nearest = np.concatenate([nearest_a_to_b, nearest_b_to_a])
    return float(np.mean(all_nearest))


# ==============================================================================
# SCHEMAS & DATA STRUCTURES
# ==============================================================================

@dataclass
class TeamTacticalGeometry:
    """Tactical geometric properties for a single team at a single time step."""

    team_label: str
    visible_players: int = 0
    outfield_player_count: int = 0
    goalkeeper_present: bool = False
    goalkeeper_track_id: Optional[int] = None

    # Centroids
    centroid_x: Optional[float] = None
    centroid_y: Optional[float] = None
    median_centroid_x: Optional[float] = None
    median_centroid_y: Optional[float] = None

    # Spatial Extents (absolute pitch axes)
    width_m: Optional[float] = None              # max(Y) - min(Y)
    longitudinal_span_m: Optional[float] = None  # max(X) - min(X)
    depth_m: Optional[float] = None              # Explicit alias for longitudinal_span_m

    # Convex Hull
    convex_hull_area_m2: Optional[float] = None
    convex_hull_perimeter_m: Optional[float] = None
    convex_hull_vertices: List[Tuple[float, float]] = field(default_factory=list)

    # Compactness / Spread Primitives
    stretch_index_m: Optional[float] = None
    mean_pairwise_distance_m: Optional[float] = None
    median_pairwise_distance_m: Optional[float] = None
    nearest_teammate_distance_mean_m: Optional[float] = None

    # Field Occupancy Distributions
    occupancy_grid_15: List[int] = field(default_factory=lambda: [0] * 15)
    lane_occupancy_counts: Dict[str, int] = field(default_factory=dict)

    # Provenance & Quality
    is_valid: bool = False
    invalidation_reason: Optional[str] = None
    included_track_ids: List[int] = field(default_factory=list)


@dataclass
class BallTacticalGeometry:
    """Tactical proximity and geometric relations relative to the ball.

    CRITICAL: Projection is on ground-plane (Z=0). Proximity does NOT infer possession.
    """

    x: Optional[float] = None
    y: Optional[float] = None
    projection_valid: bool = False
    is_ground_plane_projection: bool = True

    # Distance to team centroids
    team_0_centroid_distance_m: Optional[float] = None
    team_1_centroid_distance_m: Optional[float] = None

    # Proximity to nearest players
    nearest_player_id: Optional[int] = None
    nearest_player_team: Optional[str] = None
    nearest_player_distance_m: Optional[float] = None

    nearest_team_0_player_id: Optional[int] = None
    nearest_team_0_distance_m: Optional[float] = None

    nearest_team_1_player_id: Optional[int] = None
    nearest_team_1_distance_m: Optional[float] = None


@dataclass
class InterTeamTacticalGeometry:
    """Spatial relationship between the two competing teams."""

    centroid_distance_m: Optional[float] = None
    median_centroid_distance_m: Optional[float] = None
    nearest_opponent_distance_mean_m: Optional[float] = None


@dataclass
class TacticalQualityState:
    """Metadata regarding observation sufficiency, calibration, and team confidence."""

    team_0_confidence: float = 0.0
    team_1_confidence: float = 0.0
    team_0_visible: int = 0
    team_1_visible: int = 0
    geometry_valid: bool = False
    calibration_valid: bool = True
    invalidation_reason: Optional[str] = None


@dataclass
class TacticalFrameState:
    """Comprehensive frame-level tactical state combining teams, ball, and inter-team geometry."""

    frame_index: int
    timestamp: float
    calibration_valid: bool
    team_0: TeamTacticalGeometry
    team_1: TeamTacticalGeometry
    ball: BallTacticalGeometry
    inter_team: InterTeamTacticalGeometry
    quality: TacticalQualityState

    # Full team geometry (including GK) if requested
    team_0_full: Optional[TeamTacticalGeometry] = None
    team_1_full: Optional[TeamTacticalGeometry] = None

    # Causal EMA smoothed counterparts
    smoothed_team_0: Optional[TeamTacticalGeometry] = None
    smoothed_team_1: Optional[TeamTacticalGeometry] = None


@dataclass
class TacticalGeometryConfig:
    """Configuration for tactical geometry extraction, thresholds, and smoothing."""

    min_players_for_centroid: int = 1
    min_players_for_shape: int = 2     # For width, span, stretch index, pairwise
    min_players_for_hull: int = 3      # For convex hull area
    min_team_confidence: float = 0.40  # Minimum confidence to trust team attribution
    include_goalkeeper_in_shape: bool = False  # False = outfield only (Phase 17 decision)
    ema_alpha: float = 0.25            # Causal exponential moving average weight
    pitch_dimensions: PitchDimensions = field(default_factory=PitchDimensions)
    pitch_margin_m: float = 8.0


# ==============================================================================
# CAUSAL EXPONENTIAL MOVING AVERAGE (EMA) FILTER
# ==============================================================================

class TacticalTemporalFilter:
    """Maintains causal exponential moving average (EMA) signals for team geometry."""

    def __init__(self, alpha: float = 0.25) -> None:
        self.alpha = alpha
        self.state: Dict[str, Dict[str, float]] = {}

    def reset(self) -> None:
        self.state.clear()

    def update(self, team_key: str, geom: TeamTacticalGeometry) -> TeamTacticalGeometry:
        """Applies causal exponential smoothing to continuous geometric scalar signals."""
        if not geom.is_valid:
            return geom

        if team_key not in self.state:
            # Initialize filter with current observations
            self.state[team_key] = {
                "centroid_x": geom.centroid_x or 0.0,
                "centroid_y": geom.centroid_y or 0.0,
                "width_m": geom.width_m or 0.0,
                "longitudinal_span_m": geom.longitudinal_span_m or 0.0,
                "stretch_index_m": geom.stretch_index_m or 0.0,
                "convex_hull_area_m2": geom.convex_hull_area_m2 or 0.0,
            }
            return geom

        cur_state = self.state[team_key]
        smoothed = TeamTacticalGeometry(
            team_label=geom.team_label,
            visible_players=geom.visible_players,
            outfield_player_count=geom.outfield_player_count,
            goalkeeper_present=geom.goalkeeper_present,
            goalkeeper_track_id=geom.goalkeeper_track_id,
            is_valid=True,
            included_track_ids=list(geom.included_track_ids),
            occupancy_grid_15=list(geom.occupancy_grid_15),
            lane_occupancy_counts=dict(geom.lane_occupancy_counts),
        )

        def _smooth_val(key: str, val: Optional[float]) -> Optional[float]:
            if val is None:
                return None
            prev = cur_state.get(key, val)
            new_val = self.alpha * val + (1.0 - self.alpha) * prev
            cur_state[key] = new_val
            return float(new_val)

        smoothed.centroid_x = _smooth_val("centroid_x", geom.centroid_x)
        smoothed.centroid_y = _smooth_val("centroid_y", geom.centroid_y)
        smoothed.median_centroid_x = geom.median_centroid_x
        smoothed.median_centroid_y = geom.median_centroid_y
        smoothed.width_m = _smooth_val("width_m", geom.width_m)
        smoothed.longitudinal_span_m = _smooth_val("longitudinal_span_m", geom.longitudinal_span_m)
        smoothed.depth_m = smoothed.longitudinal_span_m
        smoothed.stretch_index_m = _smooth_val("stretch_index_m", geom.stretch_index_m)
        smoothed.convex_hull_area_m2 = _smooth_val("convex_hull_area_m2", geom.convex_hull_area_m2)
        smoothed.convex_hull_perimeter_m = geom.convex_hull_perimeter_m
        smoothed.convex_hull_vertices = geom.convex_hull_vertices
        smoothed.mean_pairwise_distance_m = geom.mean_pairwise_distance_m
        smoothed.median_pairwise_distance_m = geom.median_pairwise_distance_m
        smoothed.nearest_teammate_distance_mean_m = geom.nearest_teammate_distance_mean_m

        return smoothed


# ==============================================================================
# TACTICAL GEOMETRY ENGINE
# ==============================================================================

class TacticalGeometryEngine:
    """Orchestrates team-level tactical geometry extraction, quality gating, and export."""

    def __init__(self, config: Optional[TacticalGeometryConfig] = None) -> None:
        self.config = config or TacticalGeometryConfig()
        self.temporal_filter = TacticalTemporalFilter(alpha=self.config.ema_alpha)
        self.frames_history: List[TacticalFrameState] = []

    def reset(self) -> None:
        """Resets all internal filters and frame histories."""
        self.temporal_filter.reset()
        self.frames_history.clear()

    def process_frame(
        self,
        frame_index: int,
        timestamp: float,
        player_observations: Sequence[Union[PlayerMetricObservation, Dict[str, Any]]],
        ball_observation: Optional[Union[BallMetricObservation, Dict[str, Any]]],
        calibration_valid: bool = True,
        team_confidence_map: Optional[Dict[int, float]] = None,
        role_map: Optional[Dict[int, str]] = None,
    ) -> TacticalFrameState:
        """Processes a single frame and computes full tactical geometry state."""
        team_conf_map = team_confidence_map or {}
        roles = role_map or {}

        # 1. Filter and group valid player coordinates by team
        team_players: Dict[str, List[Dict[str, Any]]] = {"TEAM_0": [], "TEAM_1": []}

        for p in player_observations:
            # Extract attributes regardless of dict or dataclass
            if isinstance(p, dict):
                tid = int(p.get("track_id", -1))
                x = p.get("smoothed_x_m") if p.get("smoothed_x_m") is not None else p.get("pitch_x_m")
                y = p.get("smoothed_y_m") if p.get("smoothed_y_m") is not None else p.get("pitch_y_m")
                t_label = p.get("team_label")
                pos_valid = p.get("position_valid", True)
                is_inside = p.get("is_inside_pitch", True)
                role = p.get("role") or roles.get(tid, "OUTFIELD_PLAYER")
                conf = p.get("team_confidence", team_conf_map.get(tid, 1.0))
            else:
                tid = p.track_id
                x = p.smoothed_x_m if p.smoothed_x_m is not None else p.pitch_x_m
                y = p.smoothed_y_m if p.smoothed_y_m is not None else p.pitch_y_m
                t_label = p.team_label
                pos_valid = p.position_valid
                is_inside = p.is_inside_pitch
                role = p.role or roles.get(tid, "OUTFIELD_PLAYER")
                conf = team_conf_map.get(tid, 1.0)

            # Strict evidence gating: position must be valid and within pitch margin
            if not pos_valid or x is None or y is None or not is_inside:
                continue

            # Standardize team label
            t_upper = str(t_label).strip().upper() if t_label else ""
            if t_upper in ("TEAM_0", "TEAM 0", "0", "A", "TEAM_A", "LEFT", "TEAM_LEFT") or ("0" in t_upper) or ("LEFT" in t_upper):
                assigned_team = "TEAM_0"
            elif t_upper in ("TEAM_1", "TEAM 1", "1", "B", "TEAM_B", "RIGHT", "TEAM_RIGHT") or ("1" in t_upper) or ("RIGHT" in t_upper):
                assigned_team = "TEAM_1"
            else:
                continue

            # Confidence check
            if conf < self.config.min_team_confidence:
                continue

            team_players[assigned_team].append({
                "track_id": tid,
                "x": float(x),
                "y": float(y),
                "role": role,
                "confidence": float(conf),
            })

        # 2. Compute Team Geometry (Outfield default + Full optional)
        geom_0, geom_0_full = self._compute_single_team_geometry(
            team_label="TEAM_0",
            players=team_players["TEAM_0"],
            calibration_valid=calibration_valid,
        )
        geom_1, geom_1_full = self._compute_single_team_geometry(
            team_label="TEAM_1",
            players=team_players["TEAM_1"],
            calibration_valid=calibration_valid,
        )

        # 3. Apply Temporal Smoothing (EMA)
        smoothed_0 = self.temporal_filter.update("TEAM_0", geom_0)
        smoothed_1 = self.temporal_filter.update("TEAM_1", geom_1)

        # 4. Inter-team Relational Geometry
        inter_team = self._compute_inter_team_geometry(geom_0, geom_1)

        # 5. Ball Tactical Geometry
        ball_geom = self._compute_ball_geometry(
            ball_observation=ball_observation,
            geom_0=geom_0,
            geom_1=geom_1,
            team_0_players=team_players["TEAM_0"],
            team_1_players=team_players["TEAM_1"],
        )

        # 6. Quality Metadata
        conf_0 = float(np.mean([p["confidence"] for p in team_players["TEAM_0"]])) if team_players["TEAM_0"] else 0.0
        conf_1 = float(np.mean([p["confidence"] for p in team_players["TEAM_1"]])) if team_players["TEAM_1"] else 0.0
        geom_valid = calibration_valid and geom_0.is_valid and geom_1.is_valid
        invalid_reason = None
        if not calibration_valid:
            invalid_reason = "INVALID_CALIBRATION"
        elif not geom_0.is_valid:
            invalid_reason = f"TEAM_0_{geom_0.invalidation_reason}"
        elif not geom_1.is_valid:
            invalid_reason = f"TEAM_1_{geom_1.invalidation_reason}"

        quality = TacticalQualityState(
            team_0_confidence=conf_0,
            team_1_confidence=conf_1,
            team_0_visible=len(team_players["TEAM_0"]),
            team_1_visible=len(team_players["TEAM_1"]),
            geometry_valid=geom_valid,
            calibration_valid=calibration_valid,
            invalidation_reason=invalid_reason,
        )

        frame_state = TacticalFrameState(
            frame_index=frame_index,
            timestamp=timestamp,
            calibration_valid=calibration_valid,
            team_0=geom_0,
            team_1=geom_1,
            ball=ball_geom,
            inter_team=inter_team,
            quality=quality,
            team_0_full=geom_0_full,
            team_1_full=geom_1_full,
            smoothed_team_0=smoothed_0,
            smoothed_team_1=smoothed_1,
        )

        self.frames_history.append(frame_state)
        return frame_state

    def _compute_single_team_geometry(
        self,
        team_label: str,
        players: List[Dict[str, Any]],
        calibration_valid: bool,
    ) -> Tuple[TeamTacticalGeometry, Optional[TeamTacticalGeometry]]:
        """Computes both outfield-only (default) and full-team tactical shapes."""
        total_visible = len(players)
        if not calibration_valid:
            g = TeamTacticalGeometry(
                team_label=team_label,
                visible_players=total_visible,
                is_valid=False,
                invalidation_reason="INVALID_CALIBRATION",
            )
            return g, None

        if total_visible == 0:
            g = TeamTacticalGeometry(
                team_label=team_label,
                visible_players=0,
                is_valid=False,
                invalidation_reason="NO_VISIBLE_PLAYERS",
            )
            return g, None

        # Identify goalkeeper
        gk_player = next((p for p in players if "GOALKEEPER" in str(p.get("role", "")).upper()), None)
        gk_present = gk_player is not None
        gk_tid = gk_player["track_id"] if gk_player else None

        # Separate outfield vs full
        outfield_players = [p for p in players if p != gk_player] if (gk_present and not self.config.include_goalkeeper_in_shape) else players
        outfield_count = len(outfield_players)

        # 1. Outfield Shape Geometry
        outfield_geom = self._build_team_geometry_object(
            team_label=team_label,
            players_subset=outfield_players,
            total_visible=total_visible,
            outfield_count=outfield_count,
            gk_present=gk_present,
            gk_tid=gk_tid,
        )

        # 2. Full Team Shape Geometry (including GK)
        full_geom: Optional[TeamTacticalGeometry] = None
        if gk_present:
            full_geom = self._build_team_geometry_object(
                team_label=team_label,
                players_subset=players,
                total_visible=total_visible,
                outfield_count=outfield_count,
                gk_present=gk_present,
                gk_tid=gk_tid,
            )

        return outfield_geom, full_geom

    def _build_team_geometry_object(
        self,
        team_label: str,
        players_subset: List[Dict[str, Any]],
        total_visible: int,
        outfield_count: int,
        gk_present: bool,
        gk_tid: Optional[int],
    ) -> TeamTacticalGeometry:
        """Builds TeamTacticalGeometry from a specific subset of players (e.g. outfield or full)."""
        n = len(players_subset)
        track_ids = [p["track_id"] for p in players_subset]

        if n < self.config.min_players_for_centroid:
            return TeamTacticalGeometry(
                team_label=team_label,
                visible_players=total_visible,
                outfield_player_count=outfield_count,
                goalkeeper_present=gk_present,
                goalkeeper_track_id=gk_tid,
                is_valid=False,
                invalidation_reason="INSUFFICIENT_PLAYERS_FOR_CENTROID",
            )

        pts = np.array([[p["x"], p["y"]] for p in players_subset], dtype=np.float64)

        # Phase 3: Centroid & Coordinate-wise Median Centroid
        mean_c_x = float(np.mean(pts[:, 0]))
        mean_c_y = float(np.mean(pts[:, 1]))
        med_c_x = float(np.median(pts[:, 0]))
        med_c_y = float(np.median(pts[:, 1]))

        # Phase 4: Width and Longitudinal Span (in absolute pitch axes)
        if n >= self.config.min_players_for_shape:
            width_m = float(np.max(pts[:, 1]) - np.min(pts[:, 1]))
            span_m = float(np.max(pts[:, 0]) - np.min(pts[:, 0]))
        else:
            width_m, span_m = None, None

        # Phase 5: Convex Hull (Area & Perimeter)
        if n >= self.config.min_players_for_hull:
            hull_area, hull_perim, hull_verts = compute_convex_hull_2d(pts)
        else:
            hull_area, hull_perim, hull_verts = None, None, []

        # Phase 6: Stretch Index (Compactness)
        stretch_idx = compute_stretch_index(pts, (mean_c_x, mean_c_y)) if n >= self.config.min_players_for_shape else None

        # Phase 7: Pairwise Structure
        mean_pair, med_pair, nearest_tm = compute_pairwise_distances(pts) if n >= self.config.min_players_for_shape else (None, None, None)

        # Phase 9: 15-zone Pitch Occupancy Grid
        grid_15 = [0] * 15
        for p in pts:
            _, _, cell_id = assign_grid_zone(p[0], p[1])
            grid_15[cell_id] += 1

        # Phase 10: Five-Lane Lateral Channel Counts
        lane_counts = {k: 0 for k in FIVE_LANE_BOUNDS.keys()}
        for p in pts:
            lane = assign_five_lane(p[1])
            lane_counts[lane] = lane_counts.get(lane, 0) + 1

        return TeamTacticalGeometry(
            team_label=team_label,
            visible_players=total_visible,
            outfield_player_count=outfield_count,
            goalkeeper_present=gk_present,
            goalkeeper_track_id=gk_tid,
            centroid_x=mean_c_x,
            centroid_y=mean_c_y,
            median_centroid_x=med_c_x,
            median_centroid_y=med_c_y,
            width_m=width_m,
            longitudinal_span_m=span_m,
            depth_m=span_m,
            convex_hull_area_m2=hull_area,
            convex_hull_perimeter_m=hull_perim,
            convex_hull_vertices=hull_verts,
            stretch_index_m=stretch_idx,
            mean_pairwise_distance_m=mean_pair,
            median_pairwise_distance_m=med_pair,
            nearest_teammate_distance_mean_m=nearest_tm,
            occupancy_grid_15=grid_15,
            lane_occupancy_counts=lane_counts,
            is_valid=True,
            included_track_ids=track_ids,
        )

    def _compute_inter_team_geometry(
        self,
        geom_0: TeamTacticalGeometry,
        geom_1: TeamTacticalGeometry,
    ) -> InterTeamTacticalGeometry:
        """Computes centroid distances and pairwise nearest opponent proximity."""
        inter = InterTeamTacticalGeometry()
        if geom_0.is_valid and geom_1.is_valid:
            if geom_0.centroid_x is not None and geom_1.centroid_x is not None:
                inter.centroid_distance_m = float(np.hypot(
                    geom_0.centroid_x - geom_1.centroid_x,
                    geom_0.centroid_y - geom_1.centroid_y,
                ))
            if geom_0.median_centroid_x is not None and geom_1.median_centroid_x is not None:
                inter.median_centroid_distance_m = float(np.hypot(
                    geom_0.median_centroid_x - geom_1.median_centroid_x,
                    geom_0.median_centroid_y - geom_1.median_centroid_y,
                ))

        return inter

    def _compute_ball_geometry(
        self,
        ball_observation: Optional[Union[BallMetricObservation, Dict[str, Any]]],
        geom_0: TeamTacticalGeometry,
        geom_1: TeamTacticalGeometry,
        team_0_players: List[Dict[str, Any]],
        team_1_players: List[Dict[str, Any]],
    ) -> BallTacticalGeometry:
        """Computes ball-relative tactical geometric proximities. Strict ground-plane projection."""
        if ball_observation is None:
            return BallTacticalGeometry(projection_valid=False)

        if isinstance(ball_observation, dict):
            bx = ball_observation.get("smoothed_x_m") if ball_observation.get("smoothed_x_m") is not None else ball_observation.get("pitch_x_m")
            by = ball_observation.get("smoothed_y_m") if ball_observation.get("smoothed_y_m") is not None else ball_observation.get("pitch_y_m")
            valid = ball_observation.get("position_valid", True) and (bx is not None and by is not None)
        else:
            bx = ball_observation.smoothed_x_m if ball_observation.smoothed_x_m is not None else ball_observation.pitch_x_m
            by = ball_observation.smoothed_y_m if ball_observation.smoothed_y_m is not None else ball_observation.pitch_y_m
            valid = ball_observation.position_valid and (bx is not None and by is not None)

        if not valid or bx is None or by is None:
            return BallTacticalGeometry(projection_valid=False)

        bx, by = float(bx), float(by)
        bg = BallTacticalGeometry(x=bx, y=by, projection_valid=True, is_ground_plane_projection=True)

        # Distance to Team Centroids
        if geom_0.is_valid and geom_0.centroid_x is not None and geom_0.centroid_y is not None:
            bg.team_0_centroid_distance_m = float(np.hypot(bx - geom_0.centroid_x, by - geom_0.centroid_y))
        if geom_1.is_valid and geom_1.centroid_x is not None and geom_1.centroid_y is not None:
            bg.team_1_centroid_distance_m = float(np.hypot(bx - geom_1.centroid_x, by - geom_1.centroid_y))

        # Nearest player on Team 0
        if team_0_players:
            t0_dists = [np.hypot(bx - p["x"], by - p["y"]) for p in team_0_players]
            min_idx_0 = int(np.argmin(t0_dists))
            bg.nearest_team_0_player_id = team_0_players[min_idx_0]["track_id"]
            bg.nearest_team_0_distance_m = float(t0_dists[min_idx_0])

        # Nearest player on Team 1
        if team_1_players:
            t1_dists = [np.hypot(bx - p["x"], by - p["y"]) for p in team_1_players]
            min_idx_1 = int(np.argmin(t1_dists))
            bg.nearest_team_1_player_id = team_1_players[min_idx_1]["track_id"]
            bg.nearest_team_1_distance_m = float(t1_dists[min_idx_1])

        # Overall nearest player
        candidates = []
        if bg.nearest_team_0_distance_m is not None:
            candidates.append((bg.nearest_team_0_distance_m, bg.nearest_team_0_player_id, "TEAM_0"))
        if bg.nearest_team_1_distance_m is not None:
            candidates.append((bg.nearest_team_1_distance_m, bg.nearest_team_1_player_id, "TEAM_1"))

        if candidates:
            candidates.sort(key=lambda c: c[0])
            bg.nearest_player_distance_m = candidates[0][0]
            bg.nearest_player_id = candidates[0][1]
            bg.nearest_player_team = candidates[0][2]

        return bg

    def export_to_jsonl(self, output_path: Union[str, Path], sequence_id: str = "") -> int:
        """Exports tactical frame time series into structured JSONL format."""
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        import json

        count = 0
        with open(out_p, "w") as f:
            for frame in self.frames_history:
                rec = asdict(frame)
                rec["sequence_id"] = sequence_id
                f.write(json.dumps(rec) + "\n")
                count += 1

        logger.info("Exported %d tactical frame states to %s", count, out_p)
        return count
