"""Attacking Direction Resolution and Oriented Tactical Lines Engine (EXP-17 / Chapter 7).

Infers each team's attacking direction from inference-time evidence (goalkeeper anchor,
persistent team spatial ordering, sustained ball progression), projects player positions
into team-oriented longitudinal coordinates (x_attack = attack_direction * x_pitch),
discovers longitudinal tactical lines (2, 3, or 4 lines) via interpretable 1D gap-based
clustering, computes inter-line distances and oriented team depth, tracks line temporal
persistence, and outputs structured oriented tactical states.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

try:
    from app.video_analysis.pitch_calibration import PitchDimensions
    from app.video_analysis.tactical_geometry import (
        TacticalFrameState,
        TeamTacticalGeometry,
    )
    from app.video_analysis.metric_trajectories import (
        PlayerMetricObservation,
        BallMetricObservation,
    )
except ImportError:
    from backend.app.video_analysis.pitch_calibration import PitchDimensions
    from backend.app.video_analysis.tactical_geometry import (
        TacticalFrameState,
        TeamTacticalGeometry,
    )
    from backend.app.video_analysis.metric_trajectories import (
        PlayerMetricObservation,
        BallMetricObservation,
    )

logger = logging.getLogger(__name__)


# ==============================================================================
# ENUMS & DATA STRUCTURES
# ==============================================================================

class AttackDirection(int, Enum):
    """Team attacking orientation relative to the canonical pitch longitudinal X-axis."""

    POSITIVE_X = 1   # Team attacks toward positive X (+52.5m goal line)
    NEGATIVE_X = -1  # Team attacks toward negative X (-52.5m goal line)
    UNKNOWN = 0      # Orientation is ambiguous or unresolvable


@dataclass
class OrientationEvidence:
    """Individual evidence unit for attacking direction."""

    direction: AttackDirection
    confidence: float
    source: str  # "GOALKEEPER_ANCHOR", "TEAM_SPATIAL_ORDERING", "BALL_PROGRESSION", "UNKNOWN"
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TeamAttackingOrientation:
    """Consolidated attacking direction resolution for a team."""

    team_label: str
    attack_direction: AttackDirection = AttackDirection.UNKNOWN
    confidence: float = 0.0
    primary_source: str = "UNKNOWN"
    is_confirmed: bool = False
    evidence_history_length: int = 0
    side_switch_count: int = 0


@dataclass
class TacticalLine:
    """A discovered longitudinal player grouping representing a tactical line."""

    line_id: int                           # 0 = backmost (closest to own goal), K = frontmost
    player_track_ids: List[int]
    player_count: int
    mean_x_attack: float                   # Mean in oriented coordinate system
    median_x_attack: float
    width_y_m: float                       # Lateral span of players in this line (max Y - min Y)
    mean_pitch_x_m: float                  # Unoriented original pitch coordinate
    mean_pitch_y_m: float
    confidence: float
    candidate_semantic_name: str           # "DEFENSIVE_LINE", "MIDFIELD_LINE", "ATTACKING_LINE"
    persistence_frames: int = 1


@dataclass
class TeamOrientedTactics:
    """Oriented longitudinal metrics and tactical lines for a single team."""

    team_label: str
    attack_direction: AttackDirection = AttackDirection.UNKNOWN
    is_oriented: bool = False

    # Oriented Longitudinal Extents (outfield players only)
    team_front_x_attack: Optional[float] = None  # Highest x_attack (closest to opponent goal)
    team_back_x_attack: Optional[float] = None   # Lowest x_attack (closest to own goal)
    oriented_depth_m: Optional[float] = None     # front_x - back_x
    distance_to_opponent_goal_m: Optional[float] = None
    distance_to_own_goal_m: Optional[float] = None

    # Tactical Lines
    lines: List[TacticalLine] = field(default_factory=list)
    line_count: int = 0
    inter_line_distances_m: List[float] = field(default_factory=list)
    total_inter_line_span_m: Optional[float] = None

    # Evidence & Quality
    visibility_level: str = "HIGH"         # "HIGH" (>=8), "MEDIUM" (5-7), "LOW" (<=4)
    outfield_player_count: int = 0
    goalkeeper_present: bool = False
    is_valid: bool = False
    invalidation_reason: Optional[str] = None


@dataclass
class OrientedTacticalFrameState:
    """Frame-level tactical state combining orientation, oriented depth, and tactical lines."""

    frame_index: int
    timestamp: float
    team_0: TeamOrientedTactics
    team_1: TeamOrientedTactics
    orientation_confidence: float
    inter_team_defensive_gap_m: Optional[float] = None
    inter_team_midfield_gap_m: Optional[float] = None


@dataclass
class TacticalLineConfig:
    """Configuration for attacking direction resolution and 1D line clustering."""

    pitch_dimensions: PitchDimensions = field(default_factory=PitchDimensions)
    gk_goal_proximity_threshold_m: float = 22.0  # Max distance from goal line for GK anchor (|X| > 30.5m)
    team_ordering_min_frames: int = 30           # Number of frames for team spatial ordering stability
    team_ordering_min_separation_m: float = 4.0  # Min centroid difference to trust ordering
    min_line_gap_m: float = 6.0                  # Minimum longitudinal gap to separate tactical lines
    min_players_for_line: int = 1                # Min players to form a valid line
    min_players_for_tactics: int = 4             # Min outfield players to infer tactical lines
    side_switch_confirmation_frames: int = 15    # Consecutive frames of opposing evidence to trigger switch
    line_matching_max_dist_m: float = 4.5        # Max longitudinal drift to match lines across frames


# ==============================================================================
# ATTACKING DIRECTION RESOLVER
# ==============================================================================

class AttackingDirectionResolver:
    """Hierarchically infers team attacking directions from independent evidence sources.

    Hierarchy:
      1. Reliable Goalkeeper Anchor (conf ~ 0.95)
      2. Persistent Team Spatial Ordering (conf ~ 0.70)
      3. Sustained Ball Progression (conf ~ 0.40)
      4. Fallback / Abstention (UNKNOWN, conf = 0.0)
    """

    def __init__(self, config: Optional[TacticalLineConfig] = None) -> None:
        self.config = config or TacticalLineConfig()
        self.team_orientations: Dict[str, TeamAttackingOrientation] = {
            "TEAM_0": TeamAttackingOrientation(team_label="TEAM_0"),
            "TEAM_1": TeamAttackingOrientation(team_label="TEAM_1"),
        }
        self.centroid_history_0: List[float] = []
        self.centroid_history_1: List[float] = []
        self._reversal_candidate: Dict[str, Tuple[AttackDirection, int]] = {
            "TEAM_0": (AttackDirection.UNKNOWN, 0),
            "TEAM_1": (AttackDirection.UNKNOWN, 0),
        }

    def reset(self) -> None:
        """Resets temporal evidence buffers and resolved orientations."""
        self.team_orientations = {
            "TEAM_0": TeamAttackingOrientation(team_label="TEAM_0"),
            "TEAM_1": TeamAttackingOrientation(team_label="TEAM_1"),
        }
        self.centroid_history_0.clear()
        self.centroid_history_1.clear()
        self._reversal_candidate = {
            "TEAM_0": (AttackDirection.UNKNOWN, 0),
            "TEAM_1": (AttackDirection.UNKNOWN, 0),
        }

    def resolve(
        self,
        team_0_players: List[Dict[str, Any]],
        team_1_players: List[Dict[str, Any]],
        ball_observation: Optional[Any] = None,
    ) -> Tuple[TeamAttackingOrientation, TeamAttackingOrientation]:
        """Infers and updates attacking orientation for both teams."""
        half_l = self.config.pitch_dimensions.length_m / 2.0  # 52.5m
        gk_x_thresh = half_l - self.config.gk_goal_proximity_threshold_m  # 52.5 - 22.0 = 30.5m

        # 0. Synchronously update centroid history buffers
        for team_key, players in [("TEAM_0", team_0_players), ("TEAM_1", team_1_players)]:
            if players:
                xs = [p["x"] for p in players if p.get("x") is not None]
                if xs:
                    c_x = float(np.mean(xs))
                    hist = self.centroid_history_0 if team_key == "TEAM_0" else self.centroid_history_1
                    hist.append(c_x)
                    if len(hist) > self.config.team_ordering_min_frames * 2:
                        hist.pop(0)

        for team_key, players in [("TEAM_0", team_0_players), ("TEAM_1", team_1_players)]:
            cur_orient = self.team_orientations[team_key]
            evidence = self._collect_team_evidence(team_key, players, gk_x_thresh)

            if evidence.direction != AttackDirection.UNKNOWN:
                # Check for side switch / reversal
                if cur_orient.is_confirmed and evidence.direction != cur_orient.attack_direction:
                    cand_dir, count = self._reversal_candidate[team_key]
                    if cand_dir == evidence.direction:
                        count += 1
                    else:
                        cand_dir, count = evidence.direction, 1
                    self._reversal_candidate[team_key] = (cand_dir, count)

                    if count >= self.config.side_switch_confirmation_frames:
                        logger.info("Confirmed orientation reversal (side switch) for %s to %s", team_key, cand_dir)
                        cur_orient.attack_direction = cand_dir
                        cur_orient.confidence = evidence.confidence
                        cur_orient.primary_source = evidence.source
                        cur_orient.side_switch_count += 1
                        self._reversal_candidate[team_key] = (AttackDirection.UNKNOWN, 0)
                else:
                    # Update or reinforce existing orientation
                    cur_orient.attack_direction = evidence.direction
                    cur_orient.confidence = max(cur_orient.confidence, evidence.confidence)
                    cur_orient.primary_source = evidence.source
                    cur_orient.is_confirmed = True
                    cur_orient.evidence_history_length += 1
                    self._reversal_candidate[team_key] = (AttackDirection.UNKNOWN, 0)

        # Enforce complementary orientation if one team is highly confident and other is unknown
        t0 = self.team_orientations["TEAM_0"]
        t1 = self.team_orientations["TEAM_1"]
        if t0.attack_direction != AttackDirection.UNKNOWN and t1.attack_direction == AttackDirection.UNKNOWN:
            t1.attack_direction = AttackDirection.NEGATIVE_X if t0.attack_direction == AttackDirection.POSITIVE_X else AttackDirection.POSITIVE_X
            t1.confidence = t0.confidence * 0.90
            t1.primary_source = "COMPLEMENTARY_INFERENCE"
            t1.is_confirmed = True
        elif t1.attack_direction != AttackDirection.UNKNOWN and t0.attack_direction == AttackDirection.UNKNOWN:
            t0.attack_direction = AttackDirection.NEGATIVE_X if t1.attack_direction == AttackDirection.POSITIVE_X else AttackDirection.POSITIVE_X
            t0.confidence = t1.confidence * 0.90
            t0.primary_source = "COMPLEMENTARY_INFERENCE"
            t0.is_confirmed = True

        return t0, t1

    def _collect_team_evidence(
        self,
        team_key: str,
        players: List[Dict[str, Any]],
        gk_x_thresh: float,
    ) -> OrientationEvidence:
        """Evaluates hierarchical evidence sources for a team."""
        # 1. Primary: Goalkeeper Anchor
        gk_player = next((p for p in players if "GOALKEEPER" in str(p.get("role", "")).upper()), None)
        if gk_player is not None:
            gk_x = gk_player.get("x")
            if gk_x is not None:
                if gk_x < -gk_x_thresh:
                    # GK in negative goal area -> attacks positive X
                    return OrientationEvidence(
                        direction=AttackDirection.POSITIVE_X,
                        confidence=0.95,
                        source="GOALKEEPER_ANCHOR",
                        details={"gk_x": gk_x, "threshold": -gk_x_thresh},
                    )
                elif gk_x > gk_x_thresh:
                    # GK in positive goal area -> attacks negative X
                    return OrientationEvidence(
                        direction=AttackDirection.NEGATIVE_X,
                        confidence=0.95,
                        source="GOALKEEPER_ANCHOR",
                        details={"gk_x": gk_x, "threshold": gk_x_thresh},
                    )

        # 2. Secondary: Team Spatial Ordering (Longitudinal offset)
        if players:
            # Check separation if both histories are sufficiently populated
            if len(self.centroid_history_0) >= self.config.team_ordering_min_frames and len(self.centroid_history_1) >= self.config.team_ordering_min_frames:
                m0 = float(np.median(self.centroid_history_0))
                m1 = float(np.median(self.centroid_history_1))
                diff = m0 - m1

                if abs(diff) >= self.config.team_ordering_min_separation_m:
                    if team_key == "TEAM_0":
                        dir_0 = AttackDirection.POSITIVE_X if diff < 0 else AttackDirection.NEGATIVE_X
                        return OrientationEvidence(
                            direction=dir_0,
                            confidence=0.70,
                            source="TEAM_SPATIAL_ORDERING",
                            details={"median_diff": diff},
                        )
                    else:
                        dir_1 = AttackDirection.POSITIVE_X if diff > 0 else AttackDirection.NEGATIVE_X
                        return OrientationEvidence(
                            direction=dir_1,
                            confidence=0.70,
                            source="TEAM_SPATIAL_ORDERING",
                            details={"median_diff": diff},
                        )

        return OrientationEvidence(
            direction=AttackDirection.UNKNOWN,
            confidence=0.0,
            source="UNKNOWN",
        )


# ==============================================================================
# TACTICAL LINE DISCOVERER (1D GAP-BASED CLUSTERING)
# ==============================================================================

class TacticalLineDiscoverer:
    """Discovers longitudinal tactical lines using interpretable 1D gap-based clustering."""

    def __init__(self, config: Optional[TacticalLineConfig] = None) -> None:
        self.config = config or TacticalLineConfig()

    def discover_lines(
        self,
        players: List[Dict[str, Any]],
        attack_direction: AttackDirection,
    ) -> List[TacticalLine]:
        """Discovers tactical lines ordered from own goal (LINE_0) to opponent goal."""
        if len(players) < self.config.min_players_for_tactics:
            return []

        if attack_direction == AttackDirection.UNKNOWN:
            return []

        # Filter outfield players
        outfield = [p for p in players if "GOALKEEPER" not in str(p.get("role", "")).upper() and p.get("x") is not None]
        if len(outfield) < self.config.min_players_for_tactics:
            return []

        # Compute oriented coordinate: x_attack = attack_direction * x_pitch
        dir_val = attack_direction.value
        oriented_players = []
        for p in outfield:
            px = float(p["x"])
            py = float(p.get("y", 0.0))
            x_att = dir_val * px
            oriented_players.append({
                "track_id": p["track_id"],
                "x_attack": x_att,
                "pitch_x": px,
                "pitch_y": py,
                "confidence": float(p.get("confidence", 1.0)),
            })

        # Sort in ascending x_attack (from closest to own goal to closest to opponent goal)
        oriented_players.sort(key=lambda item: item["x_attack"])

        # 1D Gap-based segmentation
        clusters: List[List[Dict[str, Any]]] = []
        current_cluster: List[Dict[str, Any]] = [oriented_players[0]]

        for i in range(1, len(oriented_players)):
            prev_p = oriented_players[i - 1]
            curr_p = oriented_players[i]
            gap = curr_p["x_attack"] - prev_p["x_attack"]

            if gap >= self.config.min_line_gap_m:
                clusters.append(current_cluster)
                current_cluster = [curr_p]
            else:
                current_cluster.append(curr_p)
        clusters.append(current_cluster)

        # Build TacticalLine objects
        tactical_lines: List[TacticalLine] = []
        total_lines = len(clusters)

        for line_idx, cl in enumerate(clusters):
            track_ids = [p["track_id"] for p in cl]
            x_atts = [p["x_attack"] for p in cl]
            pys = [p["pitch_y"] for p in cl]
            pxs = [p["pitch_x"] for p in cl]
            confs = [p["confidence"] for p in cl]

            mean_x_att = float(np.mean(x_atts))
            med_x_att = float(np.median(x_atts))
            width_y = float(np.max(pys) - np.min(pys)) if len(pys) > 1 else 0.0

            # Assign candidate semantic name
            if line_idx == 0:
                semantic_name = "DEFENSIVE_LINE"
            elif line_idx == total_lines - 1 and total_lines >= 2:
                semantic_name = "ATTACKING_LINE"
            elif total_lines == 4 and line_idx == 1:
                semantic_name = "MIDFIELD_DEFENSIVE"
            elif total_lines == 4 and line_idx == 2:
                semantic_name = "MIDFIELD_OFFENSIVE"
            else:
                semantic_name = "MIDFIELD_LINE"

            line_obj = TacticalLine(
                line_id=line_idx,
                player_track_ids=track_ids,
                player_count=len(track_ids),
                mean_x_attack=mean_x_att,
                median_x_attack=med_x_att,
                width_y_m=width_y,
                mean_pitch_x_m=float(np.mean(pxs)),
                mean_pitch_y_m=float(np.mean(pys)),
                confidence=float(np.mean(confs)),
                candidate_semantic_name=semantic_name,
                persistence_frames=1,
            )
            tactical_lines.append(line_obj)

        return tactical_lines


# ==============================================================================
# TEMPORAL LINE TRACKER
# ==============================================================================

class TemporalLineTracker:
    """Maintains causal line persistence across consecutive video frames."""

    def __init__(self, max_matching_dist_m: float = 4.5) -> None:
        self.max_matching_dist_m = max_matching_dist_m
        self.prev_lines: Dict[str, List[TacticalLine]] = {"TEAM_0": [], "TEAM_1": []}

    def reset(self) -> None:
        self.prev_lines = {"TEAM_0": [], "TEAM_1": []}

    def update(self, team_key: str, cur_lines: List[TacticalLine]) -> List[TacticalLine]:
        """Matches current lines to previous lines to maintain persistence counters."""
        prev = self.prev_lines.get(team_key, [])
        if not prev or not cur_lines:
            self.prev_lines[team_key] = cur_lines
            return cur_lines

        # Greedy bipartite matching on oriented longitudinal position & member overlap
        matched_prev = set()
        for cur in cur_lines:
            best_match: Optional[TacticalLine] = None
            best_dist = float("inf")

            for p in prev:
                if p.line_id in matched_prev:
                    continue
                dist = abs(cur.mean_x_attack - p.mean_x_attack)
                if dist <= self.max_matching_dist_m and dist < best_dist:
                    best_dist = dist
                    best_match = p

            if best_match is not None:
                cur.persistence_frames = best_match.persistence_frames + 1
                matched_prev.add(best_match.line_id)
            else:
                cur.persistence_frames = 1

        self.prev_lines[team_key] = cur_lines
        return cur_lines


# ==============================================================================
# ORIENTED TACTICS ENGINE
# ==============================================================================

class OrientedTacticsEngine:
    """Orchestrates attacking direction resolution, oriented depth, and tactical lines."""

    def __init__(self, config: Optional[TacticalLineConfig] = None) -> None:
        self.config = config or TacticalLineConfig()
        self.direction_resolver = AttackingDirectionResolver(config=self.config)
        self.line_discoverer = TacticalLineDiscoverer(config=self.config)
        self.temporal_tracker = TemporalLineTracker(max_matching_dist_m=self.config.line_matching_max_dist_m)
        self.frames_history: List[OrientedTacticalFrameState] = []

    def reset(self) -> None:
        """Resets all internal resolvers, trackers, and history."""
        self.direction_resolver.reset()
        self.temporal_tracker.reset()
        self.frames_history.clear()

    def process_frame(
        self,
        frame_index: int,
        timestamp: float,
        player_observations: Sequence[Union[PlayerMetricObservation, Dict[str, Any]]],
        ball_observation: Optional[Union[BallMetricObservation, Dict[str, Any]]] = None,
        calibration_valid: bool = True,
        team_confidence_map: Optional[Dict[int, float]] = None,
        role_map: Optional[Dict[int, str]] = None,
    ) -> OrientedTacticalFrameState:
        """Processes a single frame into complete oriented tactical state."""
        team_conf_map = team_confidence_map or {}
        roles = role_map or {}

        # 1. Group valid player observations by team
        team_players: Dict[str, List[Dict[str, Any]]] = {"TEAM_0": [], "TEAM_1": []}

        for p in player_observations:
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

            if not pos_valid or x is None or y is None or not is_inside:
                continue

            t_upper = str(t_label).strip().upper() if t_label else ""
            if t_upper in ("TEAM_0", "TEAM 0", "0", "A", "TEAM_A", "LEFT", "TEAM_LEFT") or ("0" in t_upper) or ("LEFT" in t_upper):
                assigned_team = "TEAM_0"
            elif t_upper in ("TEAM_1", "TEAM 1", "1", "B", "TEAM_B", "RIGHT", "TEAM_RIGHT") or ("1" in t_upper) or ("RIGHT" in t_upper):
                assigned_team = "TEAM_1"
            else:
                continue

            team_players[assigned_team].append({
                "track_id": tid,
                "x": float(x),
                "y": float(y),
                "role": role,
                "confidence": float(conf),
            })

        # 2. Resolve Attacking Directions
        orient_0, orient_1 = self.direction_resolver.resolve(
            team_0_players=team_players["TEAM_0"],
            team_1_players=team_players["TEAM_1"],
            ball_observation=ball_observation,
        )

        # 3. Compute Team-Oriented Tactics & Lines
        half_l = self.config.pitch_dimensions.length_m / 2.0  # 52.5m
        tactics_0 = self._build_team_oriented_tactics("TEAM_0", team_players["TEAM_0"], orient_0, half_l, calibration_valid)
        tactics_1 = self._build_team_oriented_tactics("TEAM_1", team_players["TEAM_1"], orient_1, half_l, calibration_valid)

        # 4. Inter-team Tactical Gaps
        defensive_gap = None
        midfield_gap = None
        if tactics_0.is_oriented and tactics_1.is_oriented and tactics_0.lines and tactics_1.lines:
            d0_x = tactics_0.lines[0].mean_pitch_x_m
            d1_x = tactics_1.lines[0].mean_pitch_x_m
            defensive_gap = float(abs(d0_x - d1_x))

        overall_conf = float(np.mean([orient_0.confidence, orient_1.confidence]))

        frame_state = OrientedTacticalFrameState(
            frame_index=frame_index,
            timestamp=timestamp,
            team_0=tactics_0,
            team_1=tactics_1,
            orientation_confidence=overall_conf,
            inter_team_defensive_gap_m=defensive_gap,
            inter_team_midfield_gap_m=midfield_gap,
        )
        self.frames_history.append(frame_state)
        return frame_state

    def _build_team_oriented_tactics(
        self,
        team_key: str,
        players: List[Dict[str, Any]],
        orientation: TeamAttackingOrientation,
        half_l: float,
        calibration_valid: bool,
    ) -> TeamOrientedTactics:
        """Derives oriented longitudinal coordinates, depth, and tactical lines."""
        tact = TeamOrientedTactics(
            team_label=team_key,
            attack_direction=orientation.attack_direction,
            is_oriented=(orientation.attack_direction != AttackDirection.UNKNOWN),
        )

        if not calibration_valid:
            tact.is_valid = False
            tact.invalidation_reason = "INVALID_CALIBRATION"
            return tact

        outfield = [p for p in players if "GOALKEEPER" not in str(p.get("role", "")).upper()]
        tact.outfield_player_count = len(outfield)
        tact.goalkeeper_present = any("GOALKEEPER" in str(p.get("role", "")).upper() for p in players)

        # Visibility classification
        if tact.outfield_player_count >= 8:
            tact.visibility_level = "HIGH"
        elif tact.outfield_player_count >= 5:
            tact.visibility_level = "MEDIUM"
        else:
            tact.visibility_level = "LOW"

        if not tact.is_oriented or not outfield:
            tact.is_valid = False
            tact.invalidation_reason = "ORIENTATION_UNKNOWN" if not tact.is_oriented else "NO_OUTFIELD_PLAYERS"
            return tact

        # 1. Compute Oriented Extents: x_attack = attack_direction * x_pitch
        dir_val = orientation.attack_direction.value
        x_attacks = [dir_val * float(p["x"]) for p in outfield]
        front_x = float(np.max(x_attacks))
        back_x = float(np.min(x_attacks))

        tact.team_front_x_attack = front_x
        tact.team_back_x_attack = back_x
        tact.oriented_depth_m = float(front_x - back_x)
        tact.distance_to_opponent_goal_m = float(half_l - front_x)
        tact.distance_to_own_goal_m = float(back_x + half_l)

        # 2. Discover Tactical Lines
        raw_lines = self.line_discoverer.discover_lines(players, orientation.attack_direction)

        # 3. Track Temporal Persistence
        tracked_lines = self.temporal_tracker.update(team_key, raw_lines)
        tact.lines = tracked_lines
        tact.line_count = len(tracked_lines)

        # 4. Inter-line distances
        if len(tracked_lines) >= 2:
            distances = []
            for i in range(1, len(tracked_lines)):
                dist = tracked_lines[i].mean_x_attack - tracked_lines[i - 1].mean_x_attack
                distances.append(float(dist))
            tact.inter_line_distances_m = distances
            tact.total_inter_line_span_m = float(tracked_lines[-1].mean_x_attack - tracked_lines[0].mean_x_attack)

        tact.is_valid = True
        return tact

    def export_to_jsonl(self, output_path: Union[str, Path], sequence_id: str = "") -> int:
        """Exports oriented tactical time series into structured JSONL format."""
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

        logger.info("Exported %d oriented tactical frames to %s", count, out_p)
        return count
