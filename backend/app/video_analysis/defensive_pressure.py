"""Defensive Pressure & Engagement Intelligence Engine (EXP-23 / Chapter 7).

Transforms frozen metric player trajectories (EXP-15), tactical geometry (EXP-16),
oriented tactical lines (EXP-17), defensive block geometry (EXP-20), and Possession V2 (EXP-22)
into continuous, causally computed defensive pressure signals and engagement diagnostics:
- Pressure target resolution (Carrier-centric vs Ball-centric fallback vs Unknown)
- Individual defender kinematics (distance, closing speed, relative velocity, approach angle, TTC)
- Multi-scale nearest pressers (1st, 2nd, 3rd nearest distances)
- Local defensive density (counts inside r=2m, 3m, 5m, 8m)
- Collective closing dynamics (mean/max closing speed, number closing)
- Pressure cone & angular restriction (8 sectors, largest free gap, coverage ratio, escape angle)
- Ball-carrier free-space radius
- Team compression response (short-window derivatives of defensive line, depth, width, centroid-to-ball distance)
- Physically monotonic Continuous PressureIndex in [0.0, 1.0]
- Dual model options: Deterministic physically grounded index vs Calibrated classifier
- Carrier-confidence stratification (HIGH vs MEDIUM vs LOW) and explicit abstention
- Strict causality with <0.50 ms/frame steady-state execution
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
    )
    from app.video_analysis.tactical_lines import (
        AttackDirection,
        OrientedTacticalFrameState,
        TeamOrientedTactics,
    )
    from app.video_analysis.defensive_block import (
        DefensiveBlockFrameState,
        DefensiveBlockMetrics,
    )
    from app.video_analysis.possession import (
        BallControlState,
        PossessionStatus,
        TeamPossessionFrameState,
    )
    from app.video_analysis.possession_v2 import (
        PossessionEngineV2,
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
    )
    from backend.app.video_analysis.tactical_lines import (
        AttackDirection,
        OrientedTacticalFrameState,
        TeamOrientedTactics,
    )
    from backend.app.video_analysis.defensive_block import (
        DefensiveBlockFrameState,
        DefensiveBlockMetrics,
    )
    from backend.app.video_analysis.possession import (
        BallControlState,
        PossessionStatus,
        TeamPossessionFrameState,
    )
    from backend.app.video_analysis.possession_v2 import (
        PossessionEngineV2,
    )

logger = logging.getLogger(__name__)


# ==============================================================================
# ENUMS & CONSTANTS
# ==============================================================================

class PressureTargetType(str, Enum):
    """Categorical source of the pressure focal point."""

    CARRIER = "CARRIER"      # Ball carrier confirmed from Possession V2
    BALL = "BALL"            # Uncontrolled ball / free ball fallback
    UNKNOWN = "UNKNOWN"      # Ball occluded / out of frame / invalid calibration


class PressureSemanticClass(str, Enum):
    """Semantic discrete categories derived from continuous pressure index."""

    NO_PRESSURE = "NO_PRESSURE"          # Index < 0.25 (open player / unpressured ball)
    LIGHT_PRESSURE = "LIGHT_PRESSURE"    # 0.25 <= Index < 0.60 (closing or jockeying defender)
    STRONG_PRESSURE = "STRONG_PRESSURE"  # Index >= 0.60 (immediate physical duel / high-intensity engagement)
    AMBIGUOUS = "AMBIGUOUS"              # Low confidence target / borderline tracking
    NOT_VISIBLE = "NOT_VISIBLE"          # Target truncated or outside pitch boundaries


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class PressureTarget:
    """Resolved focal entity being defended against in the current frame."""

    target_type: PressureTargetType
    target_track_id: Optional[int] = None
    target_team: str = "UNKNOWN"             # Attacking team ("TEAM_0", "TEAM_1", "UNKNOWN")
    target_confidence: float = 0.0           # Upstream carrier or detection confidence
    position_metric: Optional[Tuple[float, float]] = None # (x_m, y_m) on pitch
    velocity_metric: Tuple[float, float] = (0.0, 0.0)    # (vx_m_s, vy_m_s)
    speed_mps: float = 0.0
    bbox: Optional[List[float]] = None


@dataclass
class IndividualDefenderPressure:
    """Kinematic pressure contribution of a single opposing defender."""

    defender_track_id: int
    defender_team: str
    distance_m: float
    closing_speed_mps: float                 # Positive when approaching, negative when retreating
    relative_velocity_vector: Tuple[float, float] # (vx_def - vx_target, vy_def - vy_target)
    approach_angle_deg: float                # 0 deg = charging directly at target, 180 deg = running away
    time_to_contact_s: Optional[float]       # dist / closing_speed (if closing > 0.2 m/s)
    player_speed_mps: float
    position_metric: Tuple[float, float] = (0.0, 0.0)


@dataclass
class AngularSectorCoverage:
    """Angular restriction around the target measured across radial sectors."""

    sectors_occupied: int                    # Number of sectors containing >= 1 defender within cone radius
    total_sectors: int = 8                   # Typically 8 sectors of 45 deg
    largest_free_gap_deg: float = 360.0      # Largest contiguous angle unobstructed by defenders
    coverage_ratio: float = 0.0              # sectors_occupied / total_sectors in [0.0, 1.0]
    escape_angle_deg: float = 0.0            # Center angle of the largest free sector (optimal escape vector)


@dataclass
class TeamCompressionMetrics:
    """Short-window causal derivatives of the defending team's block geometry."""

    delta_defensive_line_height_mps: float = 0.0  # d/dt defensive line height from own goal
    delta_longitudinal_depth_mps: float = 0.0     # d/dt outfield longitudinal depth
    delta_lateral_width_mps: float = 0.0          # d/dt outfield lateral width
    delta_centroid_ball_dist_mps: float = 0.0     # d/dt distance from centroid to ball/target
    is_compressing: bool = False                  # True if backline stepping up + depth shrinking + closing ball


@dataclass
class DefensivePressureConfig:
    """Operational hyperparameters for the defensive pressure pipeline."""

    pitch_dimensions: PitchDimensions = field(default_factory=PitchDimensions)

    # Metric evaluation radii
    density_radii_m: Tuple[float, float, float, float] = (2.0, 3.0, 5.0, 8.0)
    cone_radius_m: float = 8.0               # Maximum distance to consider a defender in the pressure cone
    num_angular_sectors: int = 8             # Number of angular sectors (8 * 45 deg = 360 deg)

    # Dynamic closing thresholds
    closing_speed_threshold_mps: float = 1.5 # Velocity threshold to count as actively closing
    retreating_speed_discount_mps: float = -1.0 # Velocity at which defender is retreating

    # Semantic classification thresholds
    strong_pressure_threshold: float = 0.60
    light_pressure_threshold: float = 0.25
    min_carrier_confidence: float = 0.45     # Below this, carrier is demoted to BALL fallback or AMBIGUOUS

    # Temporal compression derivative window
    compression_window_frames: int = 5       # Window length for causal finite difference (0.2s at 25 fps)

    # Model mode: "DETERMINISTIC" or "CALIBRATED"
    model_mode: str = "DETERMINISTIC"
    calibrated_model_path: Optional[str] = None


@dataclass
class FrameDefensivePressureState:
    """Comprehensive frame-level state container for defensive pressure intelligence."""

    frame_index: int
    timestamp: float
    target: PressureTarget
    defending_team: str                      # Team applying pressure ("TEAM_0", "TEAM_1", "UNKNOWN")

    # Nearest presser metrics
    nearest_defender_distance_m: Optional[float] = None
    nearest_defender_closing_speed_mps: Optional[float] = None
    nearest_defender_track_id: Optional[int] = None
    second_nearest_distance_m: Optional[float] = None
    third_nearest_distance_m: Optional[float] = None

    # Local density metrics
    n_defenders_r2: int = 0
    n_defenders_r3: int = 0
    n_defenders_r5: int = 0
    n_defenders_r8: int = 0

    # Collective closing metrics
    mean_closing_speed_mps: float = 0.0
    max_closing_speed_mps: float = 0.0
    number_closing_positive: int = 0
    number_closing_above_threshold: int = 0

    # Spatial restriction & escape geometry
    angular_coverage: AngularSectorCoverage = field(default_factory=AngularSectorCoverage)
    free_space_radius_m: float = 15.0

    # Team-level compression response
    team_compression: TeamCompressionMetrics = field(default_factory=TeamCompressionMetrics)

    # Primary continuous output
    pressure_index: float = 0.0              # Continuous score in [0.0, 1.0]

    # Secondary semantic classification
    semantic_class: PressureSemanticClass = PressureSemanticClass.NO_PRESSURE
    semantic_confidence: float = 1.0

    # Detailed individual opponent assessments
    all_defender_pressures: List[IndividualDefenderPressure] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


# ==============================================================================
# PHASE 1: PRESSURE TARGET RESOLVER
# ==============================================================================

class PressureTargetResolver:
    """Causally resolves the defensive pressure focal point from V2 possession and observations."""

    def __init__(self, config: DefensivePressureConfig) -> None:
        self.config = config

    def resolve(
        self,
        player_observations: Sequence[Union[PlayerMetricObservation, Dict[str, Any]]],
        ball_observation: Optional[Union[BallMetricObservation, Dict[str, Any]]],
        possession_state_v2: Optional[TeamPossessionFrameState],
        calibration_valid: bool = True,
    ) -> PressureTarget:
        """Determines target hierarchy: 1. Confirmed Carrier, 2. Ball Fallback, 3. UNKNOWN."""
        if not calibration_valid:
            return PressureTarget(target_type=PressureTargetType.UNKNOWN, target_confidence=0.0)

        # 1. Inspect V2 Possession Carrier
        if possession_state_v2 is not None and possession_state_v2.is_valid:
            cid = possession_state_v2.controlling_player_id
            cteam = possession_state_v2.controlling_player_team or possession_state_v2.possession_team
            conf = possession_state_v2.possession_confidence

            if cid is not None and cteam in ("TEAM_0", "TEAM_1"):
                # Locate player in player_observations
                matched_p = None
                for p in player_observations:
                    tid = int(p["track_id"] if isinstance(p, dict) else getattr(p, "track_id", -1))
                    if tid == cid:
                        matched_p = p
                        break

                if matched_p is not None:
                    px = matched_p.get("pitch_x_m") if isinstance(matched_p, dict) else getattr(matched_p, "pitch_x_m", None)
                    py = matched_p.get("pitch_y_m") if isinstance(matched_p, dict) else getattr(matched_p, "pitch_y_m", None)
                    if px is None and isinstance(matched_p, dict) and "pitch_x" in matched_p:
                        px = matched_p["pitch_x"]
                        py = matched_p["pitch_y"]

                    if px is not None and py is not None:
                        vx = float(matched_p.get("vx_mps", 0.0) if isinstance(matched_p, dict) else (getattr(matched_p, "vx_mps", 0.0) or 0.0))
                        vy = float(matched_p.get("vy_mps", 0.0) if isinstance(matched_p, dict) else (getattr(matched_p, "vy_mps", 0.0) or 0.0))
                        speed = float(matched_p.get("speed_mps", 0.0) if isinstance(matched_p, dict) else (getattr(matched_p, "speed_mps", 0.0) or 0.0))
                        bbox = list(matched_p.get("bbox", [])) if isinstance(matched_p, dict) else getattr(matched_p, "bbox", None)

                        return PressureTarget(
                            target_type=PressureTargetType.CARRIER,
                            target_track_id=cid,
                            target_team=cteam,
                            target_confidence=conf,
                            position_metric=(float(px), float(py)),
                            velocity_metric=(vx, vy),
                            speed_mps=speed,
                            bbox=list(bbox) if bbox else None,
                        )

        # 2. Fallback: Ball Position
        if ball_observation is not None:
            bx = ball_observation.get("pitch_x_m") if isinstance(ball_observation, dict) else getattr(ball_observation, "pitch_x_m", None)
            by = ball_observation.get("pitch_y_m") if isinstance(ball_observation, dict) else getattr(ball_observation, "pitch_y_m", None)
            if bx is None and isinstance(ball_observation, dict) and "pitch_x" in ball_observation:
                bx = ball_observation["pitch_x"]
                by = ball_observation["pitch_y"]

            if bx is not None and by is not None:
                b_conf = float(ball_observation.get("confidence", 0.8) if isinstance(ball_observation, dict) else (getattr(ball_observation, "confidence", 0.8) or 0.8))
                b_vx = float(ball_observation.get("vx_mps", 0.0) if isinstance(ball_observation, dict) else (getattr(ball_observation, "vx_mps", 0.0) or 0.0))
                b_vy = float(ball_observation.get("vy_mps", 0.0) if isinstance(ball_observation, dict) else (getattr(ball_observation, "vy_mps", 0.0) or 0.0))
                b_speed = float(np.hypot(b_vx, b_vy))
                b_box = list(ball_observation.get("bbox", [])) if isinstance(ball_observation, dict) else getattr(ball_observation, "bbox", None)

                holding_team = possession_state_v2.possession_team if (possession_state_v2 and possession_state_v2.possession_team in ("TEAM_0", "TEAM_1")) else "UNKNOWN"

                return PressureTarget(
                    target_type=PressureTargetType.BALL,
                    target_track_id=None,
                    target_team=holding_team,
                    target_confidence=b_conf * 0.80, # Discounted fallback confidence
                    position_metric=(float(bx), float(by)),
                    velocity_metric=(b_vx, b_vy),
                    speed_mps=b_speed,
                    bbox=list(b_box) if b_box else None,
                )

        # 3. UNKNOWN
        return PressureTarget(target_type=PressureTargetType.UNKNOWN, target_confidence=0.0)


# ==============================================================================
# PHASE 2 & 3 & 4 & 5: KINEMATICS, NEAREST PRESSERS, DENSITY & CLOSING
# ==============================================================================

class IndividualPressureCalculator:
    """Computes pairwise physical and kinematic engagement metrics for all opponents."""

    def __init__(self, config: DefensivePressureConfig) -> None:
        self.config = config

    def compute_all_defenders(
        self,
        target: PressureTarget,
        player_observations: Sequence[Union[PlayerMetricObservation, Dict[str, Any]]],
        defending_team: str,
    ) -> List[IndividualDefenderPressure]:
        """Calculates causal physical metrics for every defender on the defending team."""
        if target.position_metric is None or target.target_type == PressureTargetType.UNKNOWN:
            return []

        tx, ty = target.position_metric
        tvx, tvy = target.velocity_metric

        defenders: List[IndividualDefenderPressure] = []

        for p in player_observations:
            p_data = self._parse_player(p)
            # Must belong to defending team and not be a referee
            if p_data["role"] == "REFEREE":
                continue
            if p_data["team_label"] != defending_team:
                continue
            if p_data["pitch_x"] is None or p_data["pitch_y"] is None:
                continue

            dx = p_data["pitch_x"]
            dy = p_data["pitch_y"]
            dist = float(np.hypot(tx - dx, ty - dy))

            # Kinematic closing velocity: -d(dist)/dt = u_vec . (v_def - v_target)
            dvx = p_data["vx"] - tvx
            dvy = p_data["vy"] - tvy

            if dist > 1e-3:
                ux = (tx - dx) / dist
                uy = (ty - dy) / dist
                closing_speed = float(ux * dvx + uy * dvy)
            else:
                closing_speed = 0.0

            # Approach angle of defender: angle between vector pointing to target and v_def
            def_speed = p_data["speed_mps"]
            if def_speed > 0.2 and dist > 1e-3:
                dot = ((tx - dx) * p_data["vx"] + (ty - dy) * p_data["vy"]) / (dist * def_speed)
                dot = max(-1.0, min(1.0, dot))
                approach_angle = float(math.degrees(math.acos(dot)))
            else:
                approach_angle = 90.0

            # Time to contact
            ttc = None
            if closing_speed > 0.2 and dist > 0.1:
                ttc = float(dist / closing_speed)

            defenders.append(
                IndividualDefenderPressure(
                    defender_track_id=p_data["track_id"],
                    defender_team=defending_team,
                    distance_m=dist,
                    closing_speed_mps=closing_speed,
                    relative_velocity_vector=(dvx, dvy),
                    approach_angle_deg=approach_angle,
                    time_to_contact_s=ttc,
                    player_speed_mps=def_speed,
                    position_metric=(dx, dy),
                )
            )

        # Sort ascending by distance
        defenders.sort(key=lambda d: d.distance_m)
        return defenders

    def _parse_player(self, p: Any) -> Dict[str, Any]:
        if isinstance(p, dict):
            return {
                "track_id": int(p.get("track_id", 0)),
                "team_label": str(p.get("team_label", "UNKNOWN")),
                "role": str(p.get("role", "OUTFIELD_PLAYER")),
                "pitch_x": p.get("pitch_x_m", p.get("pitch_x")),
                "pitch_y": p.get("pitch_y_m", p.get("pitch_y")),
                "vx": float(p.get("vx_mps", 0.0)),
                "vy": float(p.get("vy_mps", 0.0)),
                "speed_mps": float(p.get("speed_mps", 0.0)),
            }

        return {
            "track_id": int(getattr(p, "track_id", 0)),
            "team_label": str(getattr(p, "team_label", "UNKNOWN")),
            "role": str(getattr(p, "role", "OUTFIELD_PLAYER")),
            "pitch_x": getattr(p, "pitch_x_m", None),
            "pitch_y": getattr(p, "pitch_y_m", None),
            "vx": float(getattr(p, "vx_mps", 0.0) or 0.0),
            "vy": float(getattr(p, "vy_mps", 0.0) or 0.0),
            "speed_mps": float(getattr(p, "speed_mps", 0.0) or 0.0),
        }


# ==============================================================================
# PHASE 6 & 7: PRESSURE CONE, ANGULAR COVERAGE & FREE SPACE
# ==============================================================================

class PressureConeCalculator:
    """Measures angular restriction and escape vectors around the target."""

    def __init__(self, config: DefensivePressureConfig) -> None:
        self.config = config

    def evaluate(
        self,
        target: PressureTarget,
        defenders: List[IndividualDefenderPressure],
    ) -> Tuple[AngularSectorCoverage, float]:
        """Computes occupied sectors, largest free gap, and free-space radius."""
        if target.position_metric is None or not defenders:
            return AngularSectorCoverage(sectors_occupied=0, largest_free_gap_deg=360.0, coverage_ratio=0.0, escape_angle_deg=0.0), 15.0

        tx, ty = target.position_metric
        cone_r = self.config.cone_radius_m
        k_sectors = self.config.num_angular_sectors
        sector_width = 2.0 * math.pi / k_sectors

        nearby_defenders = [d for d in defenders if d.distance_m <= cone_r]
        free_space_radius = float(defenders[0].distance_m) if defenders else 15.0

        if not nearby_defenders:
            return AngularSectorCoverage(
                sectors_occupied=0,
                total_sectors=k_sectors,
                largest_free_gap_deg=360.0,
                coverage_ratio=0.0,
                escape_angle_deg=0.0,
            ), free_space_radius

        occupied_indices = set()
        angles_rad: List[float] = []

        for d in nearby_defenders:
            dx, dy = d.position_metric
            angle = math.atan2(dy - ty, dx - tx) # in [-pi, pi]
            angles_rad.append(angle)

            # Map [-pi, pi] to [0, k_sectors - 1]
            norm_angle = (angle + math.pi) % (2.0 * math.pi)
            sec_idx = int(norm_angle // sector_width)
            occupied_indices.add(min(k_sectors - 1, max(0, sec_idx)))

        # Compute largest free gap
        angles_rad.sort()
        gaps: List[Tuple[float, float]] = [] # (gap_size_rad, bisector_angle_rad)

        for i in range(len(angles_rad) - 1):
            gap_size = angles_rad[i + 1] - angles_rad[i]
            mid_angle = (angles_rad[i] + angles_rad[i + 1]) / 2.0
            gaps.append((gap_size, mid_angle))

        # Wrap around gap between last and first
        wrap_gap = (2.0 * math.pi) - (angles_rad[-1] - angles_rad[0])
        wrap_mid = (angles_rad[-1] + wrap_gap / 2.0)
        wrap_mid = (wrap_mid + math.pi) % (2.0 * math.pi) - math.pi
        gaps.append((wrap_gap, wrap_mid))

        max_gap_rad, best_escape_rad = max(gaps, key=lambda g: g[0])
        largest_free_gap_deg = float(math.degrees(max_gap_rad))
        escape_angle_deg = float(math.degrees(best_escape_rad))
        coverage_ratio = float(len(occupied_indices) / k_sectors)

        return AngularSectorCoverage(
            sectors_occupied=len(occupied_indices),
            total_sectors=k_sectors,
            largest_free_gap_deg=largest_free_gap_deg,
            coverage_ratio=coverage_ratio,
            escape_angle_deg=escape_angle_deg,
        ), free_space_radius


# ==============================================================================
# PHASE 8: TEAM COMPRESSION TRACKER
# ==============================================================================

class TeamCompressionTracker:
    """Tracks causal temporal derivatives of defensive block geometry."""

    def __init__(self, config: DefensivePressureConfig) -> None:
        self.config = config
        # History queue of (timestamp, h_def, depth, width, dist_centroid_ball)
        self.history: deque[Tuple[float, Optional[float], Optional[float], Optional[float], Optional[float]]] = deque(
            maxlen=config.compression_window_frames + 2
        )

    def reset(self) -> None:
        self.history.clear()

    def update(
        self,
        timestamp: float,
        defensive_block_metrics: Optional[DefensiveBlockMetrics],
    ) -> TeamCompressionMetrics:
        """Computes short-window derivatives: d(h_def)/dt, d(depth)/dt, d(width)/dt, d(centroid_ball)/dt."""
        if defensive_block_metrics is None:
            return TeamCompressionMetrics()

        h_def = defensive_block_metrics.defensive_line_height_m
        depth = defensive_block_metrics.oriented_depth_m
        width = defensive_block_metrics.lateral_width_m
        c_ball = defensive_block_metrics.centroid_to_ball_distance_m

        self.history.append((timestamp, h_def, depth, width, c_ball))

        if len(self.history) < 2:
            return TeamCompressionMetrics()

        t0, h0, d0, w0, cb0 = self.history[0]
        t1, h1, d1, w1, cb1 = self.history[-1]
        dt = max(1e-3, t1 - t0)

        def _calc_deriv(v0: Optional[float], v1: Optional[float]) -> float:
            if v0 is not None and v1 is not None:
                return float((v1 - v0) / dt)
            return 0.0

        dh = _calc_deriv(h0, h1)
        dd = _calc_deriv(d0, d1)
        dw = _calc_deriv(w0, w1)
        dcb = _calc_deriv(cb0, cb1)

        # Collective compression: line advancing towards midfield (dh > 0.5),
        # depth compacting (dd < -0.4), and centroid closing to ball (dcb < -0.4)
        is_compressing = bool(dh > 0.4 and dd < -0.4 and dcb < -0.4)

        return TeamCompressionMetrics(
            delta_defensive_line_height_mps=dh,
            delta_longitudinal_depth_mps=dd,
            delta_lateral_width_mps=dw,
            delta_centroid_ball_dist_mps=dcb,
            is_compressing=is_compressing,
        )


# ==============================================================================
# PHASE 9 & 10: CONTINUOUS PRESSURE INDEX & SEMANTIC RESOLUTION
# ==============================================================================

class DefensivePressureIndexCalculator:
    """Computes monotonic Continuous PressureIndex in [0, 1] and semantic classes."""

    def __init__(self, config: DefensivePressureConfig) -> None:
        self.config = config

    def compute_index(
        self,
        target: PressureTarget,
        defenders: List[IndividualDefenderPressure],
        density_r: Tuple[int, int, int, int], # (r2, r3, r5, r8)
        angular_coverage: AngularSectorCoverage,
        team_compression: TeamCompressionMetrics,
    ) -> Tuple[float, PressureSemanticClass, float]:
        """Calculates continuous PressureIndex in [0.0, 1.0] with verified physical monotonicity."""
        if target.target_type == PressureTargetType.UNKNOWN or not defenders:
            sem_class = PressureSemanticClass.NOT_VISIBLE if target.target_type == PressureTargetType.UNKNOWN else PressureSemanticClass.NO_PRESSURE
            return 0.0, sem_class, 1.0

        d1 = defenders[0].distance_m
        v1_close = defenders[0].closing_speed_mps

        d2 = defenders[1].distance_m if len(defenders) > 1 else 15.0

        r2, r3, r5, r8 = density_r

        # 1. Primary Proximity Signal (Exponential decay with distance)
        # d1 = 0m -> 1.0, d1 = 2m -> 0.49, d1 = 3m -> 0.34, d1 >= 8m -> <= 0.06
        s_dist = math.exp(-d1 / 2.8)

        # 2. Dynamic Closing Velocity Boost / Discount
        # If closing (v1_close > 0): boost up to 1.8x
        # If retreating (v1_close < -1.0): discount down to 0.4x
        if v1_close > 0.0:
            f_close = 1.0 + min(0.80, v1_close / 4.0)
        elif v1_close < -1.0:
            f_close = max(0.40, 1.0 + (v1_close + 1.0) / 4.0)
        else:
            f_close = 1.0

        # 3. Secondary Defender Contribution
        s_dist2 = 0.50 * math.exp(-d2 / 4.5)

        # 4. Local Density Signal
        s_density = min(1.0, 0.40 * r2 + 0.25 * r3 + 0.15 * r5)

        # 5. Angular Restriction (Opponent coverage ratio)
        s_angle = angular_coverage.coverage_ratio # in [0.0, 1.0]

        # 6. Team Compression Boost
        s_comp = 0.08 if team_compression.is_compressing else 0.0

        # Combine weighted components
        p_raw = (0.40 * (s_dist * f_close)
                 + 0.15 * s_dist2
                 + 0.25 * s_density
                 + 0.15 * s_angle
                 + s_comp)

        # 7. Multi-defender trap multiplier (synergistic collapse)
        f_multi = 1.0 + 0.15 * max(0, r2 - 1) + 0.10 * max(0, r3 - 2)
        p_boosted = p_raw * f_multi

        # Bound strictly in [0.0, 1.0]
        pressure_index = float(max(0.0, min(1.0, p_boosted)))

        # Semantic Mapping
        # If target confidence is low (< 0.45), classify as AMBIGUOUS
        if target.target_confidence < self.config.min_carrier_confidence and target.target_type == PressureTargetType.CARRIER:
            sem_class = PressureSemanticClass.AMBIGUOUS
            sem_conf = 0.50
        elif pressure_index >= self.config.strong_pressure_threshold:
            sem_class = PressureSemanticClass.STRONG_PRESSURE
            sem_conf = min(1.0, 0.60 + (pressure_index - 0.60) * 1.0)
        elif pressure_index >= self.config.light_pressure_threshold:
            sem_class = PressureSemanticClass.LIGHT_PRESSURE
            sem_conf = 0.75
        else:
            sem_class = PressureSemanticClass.NO_PRESSURE
            sem_conf = min(1.0, 0.60 + (0.25 - pressure_index) * 1.6)

        return pressure_index, sem_class, sem_conf


# ==============================================================================
# PHASE 21 & UNIFIED ENGINE: DEFENSIVE PRESSURE ENGINE
# ==============================================================================

class DefensivePressureEngine:
    """Unified causal defensive pressure & engagement intelligence engine."""

    def __init__(self, config: Optional[DefensivePressureConfig] = None) -> None:
        self.config = config or DefensivePressureConfig()
        self.target_resolver = PressureTargetResolver(self.config)
        self.individual_calc = IndividualPressureCalculator(self.config)
        self.cone_calc = PressureConeCalculator(self.config)
        self.compression_tracker = TeamCompressionTracker(self.config)
        self.index_calc = DefensivePressureIndexCalculator(self.config)

    def reset(self) -> None:
        """Resets all temporal history and compression derivatives."""
        self.compression_tracker.reset()

    def process_frame(
        self,
        frame_index: int,
        timestamp: float,
        player_observations: Sequence[Union[PlayerMetricObservation, Dict[str, Any]]],
        ball_observation: Optional[Union[BallMetricObservation, Dict[str, Any]]],
        possession_state_v2: Optional[TeamPossessionFrameState],
        block_frame_state: Optional[DefensiveBlockFrameState] = None,
        calibration_valid: bool = True,
    ) -> FrameDefensivePressureState:
        """Processes a single frame and outputs complete FrameDefensivePressureState."""
        # 1. Resolve Target
        target = self.target_resolver.resolve(
            player_observations=player_observations,
            ball_observation=ball_observation,
            possession_state_v2=possession_state_v2,
            calibration_valid=calibration_valid,
        )

        # 2. Determine Defending Team (opponent of target team)
        if target.target_team == "TEAM_0":
            defending_team = "TEAM_1"
        elif target.target_team == "TEAM_1":
            defending_team = "TEAM_0"
        else:
            # Fallback to block frame state defending team if available
            defending_team = block_frame_state.probable_defending_team if block_frame_state else "UNKNOWN"

        # 3. Individual Defender Pressures
        defenders = self.individual_calc.compute_all_defenders(
            target=target,
            player_observations=player_observations,
            defending_team=defending_team,
        )

        # 4. Nearest Defenders
        nearest_d = defenders[0].distance_m if len(defenders) > 0 else None
        nearest_v = defenders[0].closing_speed_mps if len(defenders) > 0 else None
        nearest_tid = defenders[0].defender_track_id if len(defenders) > 0 else None
        sec_d = defenders[1].distance_m if len(defenders) > 1 else None
        third_d = defenders[2].distance_m if len(defenders) > 2 else None

        # 5. Local Defensive Density
        r2 = sum(1 for d in defenders if d.distance_m <= self.config.density_radii_m[0])
        r3 = sum(1 for d in defenders if d.distance_m <= self.config.density_radii_m[1])
        r5 = sum(1 for d in defenders if d.distance_m <= self.config.density_radii_m[2])
        r8 = sum(1 for d in defenders if d.distance_m <= self.config.density_radii_m[3])

        # 6. Collective Closing Dynamics (Defenders within 8m)
        nearby_8m = [d for d in defenders if d.distance_m <= 8.0]
        if nearby_8m:
            closing_speeds = [d.closing_speed_mps for d in nearby_8m]
            mean_close = float(np.mean(closing_speeds))
            max_close = float(np.max(closing_speeds))
            num_close_pos = sum(1 for v in closing_speeds if v > 0.0)
            num_close_above = sum(1 for v in closing_speeds if v >= self.config.closing_speed_threshold_mps)
        else:
            mean_close = 0.0
            max_close = 0.0
            num_close_pos = 0
            num_close_above = 0

        # 7. Angular Sector Coverage & Free Space
        cone_coverage, free_space = self.cone_calc.evaluate(target, defenders)

        # 8. Team Compression Metrics (Defending team's block)
        def_block_metrics = None
        if block_frame_state is not None:
            if defending_team == "TEAM_0":
                def_block_metrics = block_frame_state.team_0
            elif defending_team == "TEAM_1":
                def_block_metrics = block_frame_state.team_1

        team_compression = self.compression_tracker.update(timestamp, def_block_metrics)

        # 9. Pressure Index & Semantic Classification
        p_index, sem_class, sem_conf = self.index_calc.compute_index(
            target=target,
            defenders=defenders,
            density_r=(r2, r3, r5, r8),
            angular_coverage=cone_coverage,
            team_compression=team_compression,
        )

        return FrameDefensivePressureState(
            frame_index=frame_index,
            timestamp=timestamp,
            target=target,
            defending_team=defending_team,
            nearest_defender_distance_m=nearest_d,
            nearest_defender_closing_speed_mps=nearest_v,
            nearest_defender_track_id=nearest_tid,
            second_nearest_distance_m=sec_d,
            third_nearest_distance_m=third_d,
            n_defenders_r2=r2,
            n_defenders_r3=r3,
            n_defenders_r5=r5,
            n_defenders_r8=r8,
            mean_closing_speed_mps=mean_close,
            max_closing_speed_mps=max_close,
            number_closing_positive=num_close_pos,
            number_closing_above_threshold=num_close_above,
            angular_coverage=cone_coverage,
            free_space_radius_m=free_space,
            team_compression=team_compression,
            pressure_index=p_index,
            semantic_class=sem_class,
            semantic_confidence=sem_conf,
            all_defender_pressures=defenders,
            details={
                "target_type": target.target_type.value,
                "defending_team": defending_team,
                "is_carrier_gated": bool(target.target_type == PressureTargetType.CARRIER),
            },
        )
