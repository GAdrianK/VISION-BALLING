"""Defensive Block Height, Compactness & Team Shape Semantics Engine (EXP-20 / Chapter 7).

Transforms frozen metric player trajectories (EXP-15) and oriented tactical lines (EXP-17)
into rigorous, interpretable defensive-block geometry:
- Defensive line height relative to own goal (robust median and mean)
- Outfield team block centroid height relative to own goal
- Longitudinal compactness: oriented depth, robust P90-P10 spread, longitudinal MAD, inter-line separations
- Lateral compactness: width, robust P90-P10 lateral spread, lateral MAD
- Area compactness: outfield convex hull area and area per player
- Opponent-relative distances: defense <-> opponent attack line, defense <-> ball, centroid <-> ball
- Visibility gating: high (>=8), medium (5-7), low (<=4 -> abstain from global block semantics)
- Explicit pitch-geometric categories: LOW_BLOCK, MID_BLOCK, HIGH_BLOCK
- Causal temporal hysteresis (K-frame confirmation) and block height transition event logging
- Strict possession independence with optional high-confidence possession diagnostic
"""

from __future__ import annotations

import logging
import math
from collections import deque
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

try:
    from app.video_analysis.pitch_calibration import PitchDimensions
    from app.video_analysis.metric_trajectories import (
        PlayerMetricObservation,
        BallMetricObservation,
    )
    from app.video_analysis.tactical_geometry import (
        TacticalFrameState,
        TeamTacticalGeometry,
        compute_convex_hull_2d,
    )
    from app.video_analysis.tactical_lines import (
        AttackDirection,
        OrientedTacticalFrameState,
        TeamOrientedTactics,
        TacticalLine,
    )
except ImportError:
    from backend.app.video_analysis.pitch_calibration import PitchDimensions
    from backend.app.video_analysis.metric_trajectories import (
        PlayerMetricObservation,
        BallMetricObservation,
    )
    from backend.app.video_analysis.tactical_geometry import (
        TacticalFrameState,
        TeamTacticalGeometry,
        compute_convex_hull_2d,
    )
    from backend.app.video_analysis.tactical_lines import (
        AttackDirection,
        OrientedTacticalFrameState,
        TeamOrientedTactics,
        TacticalLine,
    )

logger = logging.getLogger(__name__)


# ==============================================================================
# ENUMS & CONSTANTS
# ==============================================================================

class BlockCategory(str, Enum):
    """Categorical semantic classification of team defensive block height."""

    LOW_BLOCK = "LOW_BLOCK"      # Defensive line sits deep inside defensive third (<35.0m from own goal)
    MID_BLOCK = "MID_BLOCK"      # Defensive line sits between defensive third and midfield line [35.0m, 52.5m)
    HIGH_BLOCK = "HIGH_BLOCK"    # Defensive line pushed up to or past midfield (>=52.5m from own goal)
    UNKNOWN = "UNKNOWN"          # Unresolvable due to low visibility, unknown orientation, or ambiguity


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class BlockTransitionEvent:
    """Event emitted when a team's confirmed defensive block category changes."""

    frame_index: int
    timestamp: float
    team_label: str
    from_category: BlockCategory
    to_category: BlockCategory
    defensive_line_height_m: Optional[float]
    team_centroid_height_m: Optional[float]
    confidence: float
    event_name: str = "BLOCK_HEIGHT_CHANGE"


@dataclass
class DefensiveBlockMetrics:
    """Comprehensive numeric and semantic defensive block geometry for a single team."""

    team_label: str
    attack_direction: AttackDirection = AttackDirection.UNKNOWN
    is_oriented: bool = False
    visibility_level: str = "LOW"             # "HIGH" (>=8), "MEDIUM" (5-7), "LOW" (<=4)
    outfield_player_count: int = 0
    goalkeeper_present: bool = False
    goalkeeper_distance_from_own_goal_m: Optional[float] = None
    goalkeeper_x_attack_m: Optional[float] = None

    # Heights relative to own goal (meters in [0.0, 105.0])
    defensive_line_height_m: Optional[float] = None          # Robust median x_attack + L/2
    defensive_line_x_attack_m: Optional[float] = None
    defensive_line_mean_height_m: Optional[float] = None     # Mean x_attack + L/2
    defensive_line_player_count: int = 0
    defensive_line_track_ids: List[int] = field(default_factory=list)
    team_backmost_player_height_m: Optional[float] = None    # Min x_attack + L/2 (lowest outfield player)
    team_frontmost_player_height_m: Optional[float] = None   # Max x_attack + L/2 (highest outfield player)
    team_centroid_height_m: Optional[float] = None           # Outfield median centroid x_attack + L/2
    team_mean_centroid_height_m: Optional[float] = None      # Outfield mean centroid x_attack + L/2

    # Longitudinal Compactness
    oriented_depth_m: Optional[float] = None                 # Classical span: max - min
    longitudinal_p90_p10_spread_m: Optional[float] = None    # Robust spread: P90 - P10
    longitudinal_mad_m: Optional[float] = None               # Median Absolute Deviation from median
    line_count: int = 0
    inter_line_distances_m: List[float] = field(default_factory=list)
    mean_inter_line_distance_m: Optional[float] = None
    max_inter_line_distance_m: Optional[float] = None
    defense_midfield_distance_m: Optional[float] = None      # Inter-line distance 0 -> 1
    midfield_attack_distance_m: Optional[float] = None       # Inter-line distance 1 -> 2 (if >= 3 lines)

    # Lateral Compactness
    lateral_width_m: Optional[float] = None                  # Classical span: max - min lateral Y
    lateral_p90_p10_spread_m: Optional[float] = None         # Robust spread: P90 - P10
    lateral_mad_m: Optional[float] = None                    # Lateral MAD

    # Area Compactness
    hull_area_m2: Optional[float] = None                     # Outfield convex hull area (m^2)
    hull_perimeter_m: Optional[float] = None                 # Outfield convex hull perimeter (m)
    hull_per_player_m2: Optional[float] = None               # Area per visible outfield player

    # Opponent & Ball Relative Geometry
    def_to_opp_attack_line_m: Optional[float] = None          # Longitudinal pitch distance between def and opp att lines
    def_to_opp_attack_line_euclidean_m: Optional[float] = None
    def_line_to_ball_distance_m: Optional[float] = None      # Euclidean distance from def line center to ball
    def_line_to_ball_longitudinal_m: Optional[float] = None  # Longitudinal distance along attack axis
    centroid_to_ball_distance_m: Optional[float] = None      # Euclidean distance from team centroid to ball

    # Semantic Block Category
    raw_category: BlockCategory = BlockCategory.UNKNOWN
    confirmed_category: BlockCategory = BlockCategory.UNKNOWN
    category_confidence: float = 0.0
    invalidation_reason: Optional[str] = None


@dataclass
class DefensiveBlockFrameState:
    """Frame-level state container for both teams' defensive block properties and events."""

    frame_index: int
    timestamp: float
    team_0: DefensiveBlockMetrics
    team_1: DefensiveBlockMetrics
    probable_defending_team: str = "UNKNOWN"  # "TEAM_0", "TEAM_1", "UNKNOWN"
    probable_attacking_team: str = "UNKNOWN"  # "TEAM_0", "TEAM_1", "UNKNOWN"
    possession_source: str = "NONE"           # "EXP18_CAUSAL", "ORACLE", "NONE"
    transitions: List[BlockTransitionEvent] = field(default_factory=list)


@dataclass
class DefensiveBlockConfig:
    """Operational parameters for defensive block geometry and semantic classification."""

    pitch_dimensions: PitchDimensions = field(default_factory=PitchDimensions)
    # Block height thresholds (distance from own goal, pitch length = 105.0m)
    # Defensive third: [0.0, 35.0m), Middle third: [35.0m, 70.0m), Attacking third: [70.0m, 105.0m]
    low_block_ceiling_m: float = 35.0        # Upper bound of defensive third
    high_block_floor_m: float = 52.5         # Halfway line
    # Centroid fallback thresholds (when defensive line is unclustered)
    centroid_low_ceiling_m: float = 42.0     # Centroid < 42m -> LOW_BLOCK
    centroid_high_floor_m: float = 58.0      # Centroid >= 58m -> HIGH_BLOCK
    # Visibility gating
    min_players_for_block_semantics: int = 5 # N <= 4 forces UNKNOWN category (Phase 15)
    # Temporal hysteresis
    hysteresis_frames: int = 10              # Consecutive frames to confirm a category change
    min_line_confidence: float = 0.35        # Minimum line confidence to trust defensive line
    # Possession diagnostic
    enable_possession_diagnostic: bool = True
    possession_confidence_threshold: float = 0.65


def _fast_quantiles_1d(vals: Sequence[float], quantiles: Sequence[float]) -> List[float]:
    """Fast linear interpolation quantiles for small 1D collections (matches np.percentile)."""
    s = sorted(vals)
    n = len(s)
    if n == 0:
        return [0.0 for _ in quantiles]
    if n == 1:
        return [float(s[0]) for _ in quantiles]
    res: List[float] = []
    for q in quantiles:
        idx = q * (n - 1)
        lo = int(idx)
        hi = min(lo + 1, n - 1)
        frac = idx - lo
        res.append(float(s[lo] * (1.0 - frac) + s[hi] * frac))
    return res


# ==============================================================================
# DEFENSIVE BLOCK ENGINE
# ==============================================================================

class DefensiveBlockEngine:
    """Causal, possession-independent defensive block height and compactness engine.

    Computes deterministic geometric properties and temporal state machines for
    defensive block monitoring without future-frame lookahead.
    """

    def __init__(self, config: Optional[DefensiveBlockConfig] = None) -> None:
        self.config = config or DefensiveBlockConfig()
        self._history_0: deque[BlockCategory] = deque(maxlen=self.config.hysteresis_frames)
        self._history_1: deque[BlockCategory] = deque(maxlen=self.config.hysteresis_frames)
        self._confirmed_cat_0: BlockCategory = BlockCategory.UNKNOWN
        self._confirmed_cat_1: BlockCategory = BlockCategory.UNKNOWN

    def reset(self) -> None:
        """Resets temporal hysteresis buffers."""
        self._history_0.clear()
        self._history_1.clear()
        self._confirmed_cat_0 = BlockCategory.UNKNOWN
        self._confirmed_cat_1 = BlockCategory.UNKNOWN

    def process_frame(
        self,
        frame_index: int,
        timestamp: float,
        players: Sequence[PlayerMetricObservation],
        tactical_geom: TacticalFrameState,
        oriented_tactics: OrientedTacticalFrameState,
        ball: Optional[BallMetricObservation] = None,
        ball_control: Optional[Any] = None,
    ) -> DefensiveBlockFrameState:
        """Processes a single frame and outputs complete defensive block geometry for both teams."""
        # 1. Compute per-team metrics
        metrics_0 = self._compute_team_metrics(
            team_label="TEAM_0",
            players=players,
            team_geom=tactical_geom.team_0,
            team_oriented=oriented_tactics.team_0,
            opp_oriented=oriented_tactics.team_1,
            ball=ball,
        )
        metrics_1 = self._compute_team_metrics(
            team_label="TEAM_1",
            players=players,
            team_geom=tactical_geom.team_1,
            team_oriented=oriented_tactics.team_1,
            opp_oriented=oriented_tactics.team_0,
            ball=ball,
        )

        # 2. Update temporal hysteresis & emit transition events
        transitions: List[BlockTransitionEvent] = []
        confirmed_0, evt_0 = self._update_hysteresis(
            frame_index=frame_index,
            timestamp=timestamp,
            team_label="TEAM_0",
            metrics=metrics_0,
            history_buf=self._history_0,
            current_confirmed=self._confirmed_cat_0,
        )
        self._confirmed_cat_0 = confirmed_0
        metrics_0.confirmed_category = confirmed_0
        if evt_0 is not None:
            transitions.append(evt_0)

        confirmed_1, evt_1 = self._update_hysteresis(
            frame_index=frame_index,
            timestamp=timestamp,
            team_label="TEAM_1",
            metrics=metrics_1,
            history_buf=self._history_1,
            current_confirmed=self._confirmed_cat_1,
        )
        self._confirmed_cat_1 = confirmed_1
        metrics_1.confirmed_category = confirmed_1
        if evt_1 is not None:
            transitions.append(evt_1)

        # 3. Optional Possession Diagnostic (Phase 9)
        defending_team, attacking_team, poss_src = self._resolve_probable_defending_team(ball_control)

        return DefensiveBlockFrameState(
            frame_index=frame_index,
            timestamp=timestamp,
            team_0=metrics_0,
            team_1=metrics_1,
            probable_defending_team=defending_team,
            probable_attacking_team=attacking_team,
            possession_source=poss_src,
            transitions=transitions,
        )

    def _compute_team_metrics(
        self,
        team_label: str,
        players: Sequence[PlayerMetricObservation],
        team_geom: TeamTacticalGeometry,
        team_oriented: TeamOrientedTactics,
        opp_oriented: TeamOrientedTactics,
        ball: Optional[BallMetricObservation] = None,
    ) -> DefensiveBlockMetrics:
        """Calculates defensive block geometry for a given team."""
        pitch_length = self.config.pitch_dimensions.length_m
        half_length = pitch_length / 2.0  # 52.5m for standard FIFA pitch

        # Filter team players
        team_players = [p for p in players if p.team_label == team_label]
        outfield_players = [p for p in team_players if p.role != "GOALKEEPER"]
        gk_players = [p for p in team_players if p.role == "GOALKEEPER"]

        outfield_count = len(outfield_players)
        gk_present = len(gk_players) > 0
        visibility_level = "HIGH" if outfield_count >= 8 else ("MEDIUM" if outfield_count >= 5 else "LOW")

        metrics = DefensiveBlockMetrics(
            team_label=team_label,
            attack_direction=team_oriented.attack_direction,
            is_oriented=team_oriented.is_oriented,
            visibility_level=visibility_level,
            outfield_player_count=outfield_count,
            goalkeeper_present=gk_present,
        )

        direction_sign = 1 if team_oriented.attack_direction == AttackDirection.POSITIVE_X else (
            -1 if team_oriented.attack_direction == AttackDirection.NEGATIVE_X else 0
        )

        # Goalkeeper metrics (if present)
        if gk_present and direction_sign != 0:
            gk_x = gk_players[0].pitch_x_m
            gk_x_attack = float(direction_sign * gk_x)
            metrics.goalkeeper_x_attack_m = gk_x_attack
            metrics.goalkeeper_distance_from_own_goal_m = float(gk_x_attack + half_length)

        # Early exit if unoriented or low visibility
        if not team_oriented.is_oriented or direction_sign == 0:
            metrics.raw_category = BlockCategory.UNKNOWN
            metrics.invalidation_reason = "UNKNOWN_ORIENTATION"
            return metrics

        # Outfield coordinates in attack reference frame
        outfield_x_attack = [direction_sign * p.pitch_x_m for p in outfield_players if p.pitch_x_m is not None]
        outfield_y = [p.pitch_y_m for p in outfield_players if p.pitch_y_m is not None]

        if outfield_count >= 1:
            metrics.team_backmost_player_height_m = float(min(outfield_x_attack) + half_length)
            metrics.team_frontmost_player_height_m = float(max(outfield_x_attack) + half_length)

        # ----------------------------------------------------------------------
        # Phase 3: Team Block Height (Centroid)
        # ----------------------------------------------------------------------
        if outfield_count >= 1:
            median_cent_x_attack = _fast_quantiles_1d(outfield_x_attack, [0.5])[0]
            mean_cent_x_attack = float(sum(outfield_x_attack) / len(outfield_x_attack))
            metrics.team_centroid_height_m = float(median_cent_x_attack + half_length)
            metrics.team_mean_centroid_height_m = float(mean_cent_x_attack + half_length)

        # ----------------------------------------------------------------------
        # Phase 4 & 5: Longitudinal & Lateral Compactness (Outfield)
        # ----------------------------------------------------------------------
        if outfield_count >= 2:
            # Longitudinal
            metrics.oriented_depth_m = float(max(outfield_x_attack) - min(outfield_x_attack))
            p10_x, med_x, p90_x = _fast_quantiles_1d(outfield_x_attack, [0.1, 0.5, 0.9])
            metrics.longitudinal_p90_p10_spread_m = float(p90_x - p10_x)
            devs_x = [abs(x - med_x) for x in outfield_x_attack]
            metrics.longitudinal_mad_m = _fast_quantiles_1d(devs_x, [0.5])[0]

            # Lateral
            metrics.lateral_width_m = float(max(outfield_y) - min(outfield_y))
            p10_y, med_y, p90_y = _fast_quantiles_1d(outfield_y, [0.1, 0.5, 0.9])
            metrics.lateral_p90_p10_spread_m = float(p90_y - p10_y)
            devs_y = [abs(y - med_y) for y in outfield_y]
            metrics.lateral_mad_m = _fast_quantiles_1d(devs_y, [0.5])[0]

        # ----------------------------------------------------------------------
        # Phase 6: Area Compactness (Outfield Convex Hull)
        # ----------------------------------------------------------------------
        hull_area = getattr(team_geom, "convex_hull_area_m2", None)
        hull_perim = getattr(team_geom, "convex_hull_perimeter_m", None)
        if hull_area is not None:
            metrics.hull_area_m2 = hull_area
            metrics.hull_perimeter_m = hull_perim
            if outfield_count >= 3 and hull_area > 0:
                metrics.hull_per_player_m2 = float(hull_area / outfield_count)
        elif outfield_count >= 3:
            pts = np.column_stack([
                [p.pitch_x_m for p in outfield_players],
                [p.pitch_y_m for p in outfield_players]
            ])
            area, perim, _ = compute_convex_hull_2d(pts)
            metrics.hull_area_m2 = area
            metrics.hull_perimeter_m = perim
            if area is not None and area > 0:
                metrics.hull_per_player_m2 = float(area / outfield_count)

        # ----------------------------------------------------------------------
        # Phase 2 & 7: Defensive Line & Inter-line Compactness
        # ----------------------------------------------------------------------
        lines = team_oriented.lines
        metrics.line_count = len(lines)
        if len(lines) >= 1:
            # Defensive line is lines[0] (backmost outfield line closest to own goal)
            def_line = lines[0]
            metrics.defensive_line_x_attack_m = def_line.median_x_attack
            metrics.defensive_line_height_m = float(def_line.median_x_attack + half_length)
            metrics.defensive_line_mean_height_m = float(def_line.mean_x_attack + half_length)
            metrics.defensive_line_player_count = def_line.player_count
            metrics.defensive_line_track_ids = list(def_line.player_track_ids)

        if len(lines) >= 2:
            inter_dists = [float(lines[i + 1].median_x_attack - lines[i].median_x_attack) for i in range(len(lines) - 1)]
            metrics.inter_line_distances_m = inter_dists
            metrics.mean_inter_line_distance_m = float(np.mean(inter_dists))
            metrics.max_inter_line_distance_m = float(np.max(inter_dists))
            metrics.defense_midfield_distance_m = inter_dists[0]
            if len(lines) >= 3:
                metrics.midfield_attack_distance_m = inter_dists[1]

        # ----------------------------------------------------------------------
        # Phase 8: Opponent-Relative Defensive Geometry
        # ----------------------------------------------------------------------
        if len(lines) >= 1 and len(opp_oriented.lines) >= 1:
            def_line = lines[0]
            opp_att_line = opp_oriented.lines[-1]  # Opponent frontmost line
            # Longitudinal distance along pitch X
            metrics.def_to_opp_attack_line_m = float(abs(def_line.mean_pitch_x_m - opp_att_line.mean_pitch_x_m))
            metrics.def_to_opp_attack_line_euclidean_m = float(math.hypot(
                def_line.mean_pitch_x_m - opp_att_line.mean_pitch_x_m,
                def_line.mean_pitch_y_m - opp_att_line.mean_pitch_y_m,
            ))

        has_ball_pos = (
            ball is not None
            and getattr(ball, "pitch_x_m", None) is not None
            and getattr(ball, "pitch_y_m", None) is not None
        )

        if has_ball_pos and len(lines) >= 1:
            def_line = lines[0]
            # Euclidean distance to ball
            metrics.def_line_to_ball_distance_m = float(math.hypot(
                def_line.mean_pitch_x_m - ball.pitch_x_m,
                def_line.mean_pitch_y_m - ball.pitch_y_m,
            ))
            # Longitudinal distance along attack axis
            ball_x_attack = direction_sign * ball.pitch_x_m
            metrics.def_line_to_ball_longitudinal_m = float(abs(def_line.median_x_attack - ball_x_attack))

        if has_ball_pos and outfield_count >= 1:
            # Euclidean distance from team centroid to ball
            cent_pitch_x = float(sum(p.pitch_x_m for p in outfield_players if p.pitch_x_m is not None) / outfield_count)
            cent_pitch_y = float(sum(p.pitch_y_m for p in outfield_players if p.pitch_y_m is not None) / outfield_count)
            metrics.centroid_to_ball_distance_m = float(math.hypot(
                cent_pitch_x - ball.pitch_x_m,
                cent_pitch_y - ball.pitch_y_m,
            ))

        # ----------------------------------------------------------------------
        # Phase 10 & 15: Geometric Block Categorization & Visibility Gating
        # ----------------------------------------------------------------------
        if outfield_count < self.config.min_players_for_block_semantics:
            # N <= 4: abstain from issuing global block semantics
            metrics.raw_category = BlockCategory.UNKNOWN
            metrics.category_confidence = 0.0
            metrics.invalidation_reason = "LOW_VISIBILITY"
        else:
            cat, conf, reason = self._classify_block_category(metrics)
            metrics.raw_category = cat
            metrics.category_confidence = conf
            metrics.invalidation_reason = reason

        return metrics

    def _classify_block_category(
        self,
        metrics: DefensiveBlockMetrics,
    ) -> Tuple[BlockCategory, float, Optional[str]]:
        """Determines the instantaneous geometric block category from line height or centroid height."""
        # Preference 1: Explicit defensive line height
        if metrics.defensive_line_height_m is not None:
            d_line = metrics.defensive_line_height_m
            low_thresh = self.config.low_block_ceiling_m   # 35.0m
            high_thresh = self.config.high_block_floor_m   # 52.5m

            if d_line < low_thresh:
                cat = BlockCategory.LOW_BLOCK
                # Margin confidence
                margin = (low_thresh - d_line) / low_thresh
                conf = float(np.clip(0.65 + 0.30 * margin, 0.60, 0.95))
            elif d_line < high_thresh:
                cat = BlockCategory.MID_BLOCK
                mid_center = (low_thresh + high_thresh) / 2.0
                margin = 1.0 - abs(d_line - mid_center) / (high_thresh - mid_center)
                conf = float(np.clip(0.60 + 0.35 * margin, 0.55, 0.95))
            else:
                cat = BlockCategory.HIGH_BLOCK
                margin = (d_line - high_thresh) / (self.config.pitch_dimensions.length_m - high_thresh)
                conf = float(np.clip(0.65 + 0.30 * margin, 0.60, 0.95))

            if metrics.visibility_level == "MEDIUM":
                conf *= 0.80

            return cat, conf, "OK"

        # Preference 2: Fallback to team centroid height
        if metrics.team_centroid_height_m is not None:
            d_cent = metrics.team_centroid_height_m
            if d_cent < self.config.centroid_low_ceiling_m:
                cat = BlockCategory.LOW_BLOCK
            elif d_cent < self.config.centroid_high_floor_m:
                cat = BlockCategory.MID_BLOCK
            else:
                cat = BlockCategory.HIGH_BLOCK

            conf = 0.55 if metrics.visibility_level == "HIGH" else 0.45
            return cat, conf, "FALLBACK_CENTROID_HEIGHT"

        return BlockCategory.UNKNOWN, 0.0, "NO_HEIGHT_ESTIMATE"

    def _update_hysteresis(
        self,
        frame_index: int,
        timestamp: float,
        team_label: str,
        metrics: DefensiveBlockMetrics,
        history_buf: deque[BlockCategory],
        current_confirmed: BlockCategory,
    ) -> Tuple[BlockCategory, Optional[BlockTransitionEvent]]:
        """Applies causal hysteresis confirmation window and emits transition events."""
        raw_cat = metrics.raw_category

        # If visibility is LOW, immediate fallback to UNKNOWN (no false persistence)
        if metrics.visibility_level == "LOW" or raw_cat == BlockCategory.UNKNOWN:
            history_buf.append(raw_cat)
            if current_confirmed != BlockCategory.UNKNOWN:
                evt = BlockTransitionEvent(
                    frame_index=frame_index,
                    timestamp=timestamp,
                    team_label=team_label,
                    from_category=current_confirmed,
                    to_category=BlockCategory.UNKNOWN,
                    defensive_line_height_m=metrics.defensive_line_height_m,
                    team_centroid_height_m=metrics.team_centroid_height_m,
                    confidence=0.0,
                )
                return BlockCategory.UNKNOWN, evt
            return BlockCategory.UNKNOWN, None

        history_buf.append(raw_cat)

        # Cold start: initialize with first valid raw category
        if current_confirmed == BlockCategory.UNKNOWN:
            if len(history_buf) >= 3 and all(c == raw_cat for c in list(history_buf)[-3:]):
                evt = BlockTransitionEvent(
                    frame_index=frame_index,
                    timestamp=timestamp,
                    team_label=team_label,
                    from_category=BlockCategory.UNKNOWN,
                    to_category=raw_cat,
                    defensive_line_height_m=metrics.defensive_line_height_m,
                    team_centroid_height_m=metrics.team_centroid_height_m,
                    confidence=metrics.category_confidence,
                )
                return raw_cat, evt
            return BlockCategory.UNKNOWN, None

        # Check if full window agrees with a new category
        if len(history_buf) == history_buf.maxlen and all(c == raw_cat for c in history_buf):
            if raw_cat != current_confirmed:
                evt = BlockTransitionEvent(
                    frame_index=frame_index,
                    timestamp=timestamp,
                    team_label=team_label,
                    from_category=current_confirmed,
                    to_category=raw_cat,
                    defensive_line_height_m=metrics.defensive_line_height_m,
                    team_centroid_height_m=metrics.team_centroid_height_m,
                    confidence=metrics.category_confidence,
                )
                return raw_cat, evt

        # Hold current confirmed category
        return current_confirmed, None

    def _resolve_probable_defending_team(
        self,
        ball_control: Optional[Any],
    ) -> Tuple[str, str, str]:
        """Resolves optional probable defending/attacking team assignment (Phase 9)."""
        if not self.config.enable_possession_diagnostic or ball_control is None:
            return "UNKNOWN", "UNKNOWN", "NONE"

        poss_team = getattr(ball_control, "possession_team", None)
        conf = getattr(ball_control, "possession_confidence", 0.0)

        if conf >= self.config.possession_confidence_threshold:
            if poss_team == "TEAM_0":
                return "TEAM_1", "TEAM_0", "EXP18_CAUSAL"
            elif poss_team == "TEAM_1":
                return "TEAM_0", "TEAM_1", "EXP18_CAUSAL"

        return "UNKNOWN", "UNKNOWN", "NONE"
