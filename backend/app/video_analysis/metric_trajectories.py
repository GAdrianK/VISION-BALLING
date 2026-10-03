"""Metric Trajectory Engine for Tracked Football Entities (EXP-15).

Converts 2D image detections/tracks of players and the ball into temporally
coherent metric pitch trajectories with velocity estimation, physical plausibility
checks, multi-method smoothing (Raw, Moving Polynomial, Kalman Filter), and
world-space JSONL serialization.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

try:
    from app.video_analysis.pitch_calibration import (
        PitchCalibrationResult,
        PitchDimensions,
    )
    from app.video_analysis.temporal_calibration import (
        TemporalCalibrationResult,
        TemporalCalibrationState,
    )
except ImportError:
    from backend.app.video_analysis.pitch_calibration import (
        PitchCalibrationResult,
        PitchDimensions,
    )
    from backend.app.video_analysis.temporal_calibration import (
        TemporalCalibrationResult,
        TemporalCalibrationState,
    )

logger = logging.getLogger(__name__)


class SmoothingMethod(str, Enum):
    """Supported metric trajectory filtering and smoothing baselines."""

    RAW = "RAW"                      # No smoothing applied
    POLYNOMIAL = "POLYNOMIAL"        # Local moving polynomial (Savitzky-Golay style)
    KALMAN = "KALMAN"                # Constant-velocity 2D Kalman filter


@dataclass
class PlayerMetricObservation:
    """Metric pitch observation for a single tracked player at a given frame."""

    track_id: int
    frame_index: int
    timestamp: float
    team_label: Optional[str] = None
    role: Optional[str] = None
    image_anchor_px: Tuple[float, float] = (0.0, 0.0)  # Bbox bottom-center (u, v)
    pitch_x_m: Optional[float] = None
    pitch_y_m: Optional[float] = None
    smoothed_x_m: Optional[float] = None
    smoothed_y_m: Optional[float] = None
    velocity_x_mps: Optional[float] = None
    velocity_y_mps: Optional[float] = None
    speed_mps: Optional[float] = None
    calibration_state: str = "INVALID"
    calibration_age: int = 0
    calibration_confidence: float = 0.0
    position_valid: bool = False
    is_inside_pitch: bool = False
    speed_plausible: bool = True
    invalidation_reason: Optional[str] = None


@dataclass
class BallMetricObservation:
    """Metric ground-plane pitch observation for the tracked ball.

    CRITICAL NOTE: Footballs are often airborne (Z > 0). This is strictly a
    GROUND-PLANE PROJECTION (Z = 0), NOT a full 3D ballistic trajectory.
    """

    track_id: int
    frame_index: int
    timestamp: float
    image_anchor_px: Tuple[float, float] = (0.0, 0.0)  # Bbox center (u, v)
    pitch_x_m: Optional[float] = None
    pitch_y_m: Optional[float] = None
    smoothed_x_m: Optional[float] = None
    smoothed_y_m: Optional[float] = None
    velocity_x_mps: Optional[float] = None
    velocity_y_mps: Optional[float] = None
    speed_mps: Optional[float] = None
    calibration_state: str = "INVALID"
    calibration_age: int = 0
    calibration_confidence: float = 0.0
    position_valid: bool = False
    is_inside_pitch: bool = False
    speed_plausible: bool = True
    invalidation_reason: Optional[str] = None
    is_ground_plane_projection: bool = True


@dataclass
class MetricTrajectoryConfig:
    """Configuration for metric trajectory projection, smoothing, and validation."""

    smoothing_method: SmoothingMethod = SmoothingMethod.KALMAN
    pitch_dimensions: PitchDimensions = field(default_factory=PitchDimensions)
    pitch_margin_m: float = 8.0              # Permissible boundary margin in meters
    max_player_speed_mps: float = 12.5       # Usain Bolt ~12.4 m/s; top footballer sprint ~10.5 m/s
    max_ball_speed_mps: float = 55.0         # Hardest recorded strikes ~45-50 m/s
    max_player_acceleration_mps2: float = 12.0 # Maximum physical human acceleration
    polynomial_window_size: int = 5          # Window size for polynomial moving filter
    kalman_process_noise_std: float = 1.5    # Process noise standard deviation (m/s^2)
    kalman_measurement_noise_std: float = 0.4 # Measurement uncertainty on footpoint (meters)
    max_interpolation_gap_frames: int = 3   # Max missing span to interpolate smoothly


class LinearKalman2D:
    """Constant-velocity 2D Kalman filter for metric track smoothing."""

    def __init__(self, init_x: float, init_y: float, dt: float = 0.04, q_std: float = 1.5, r_std: float = 0.4) -> None:
        self.dt = dt
        # State: [x, y, vx, vy]
        self.state = np.array([init_x, init_y, 0.0, 0.0], dtype=np.float64)
        # Covariance
        self.P = np.eye(4, dtype=np.float64) * (r_std ** 2)

        # Transition matrix
        self.F = np.array([
            [1.0, 0.0, dt,  0.0],
            [0.0, 1.0, 0.0, dt],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ], dtype=np.float64)

        # Measurement matrix (observing x, y)
        self.H = np.array([
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
        ], dtype=np.float64)

        # Process noise covariance
        q_pos = (q_std ** 2) * (dt ** 4) / 4.0
        q_vel = (q_std ** 2) * (dt ** 2)
        q_cross = (q_std ** 2) * (dt ** 3) / 2.0
        self.Q = np.array([
            [q_pos,   0.0,     q_cross, 0.0],
            [0.0,     q_pos,   0.0,     q_cross],
            [q_cross, 0.0,     q_vel,   0.0],
            [0.0,     q_cross, 0.0,     q_vel],
        ], dtype=np.float64)

        # Measurement noise covariance
        self.R = np.eye(2, dtype=np.float64) * (r_std ** 2)

    def predict(self, dt: Optional[float] = None) -> Tuple[float, float]:
        """Kalman state time-update."""
        if dt is not None and abs(dt - self.dt) > 1e-4:
            self.dt = dt
            self.F[0, 2] = dt
            self.F[1, 3] = dt

        self.state = self.F @ self.state
        self.P = self.F @ self.P @ self.F.T + self.Q
        return float(self.state[0]), float(self.state[1])

    def update(self, z_x: float, z_y: float) -> Tuple[float, float, float, float]:
        """Kalman measurement update."""
        z = np.array([z_x, z_y], dtype=np.float64)
        y = z - self.H @ self.state  # Residual
        S = self.H @ self.P @ self.H.T + self.R
        K = self.P @ self.H.T @ np.linalg.inv(S)

        self.state = self.state + K @ y
        self.P = (np.eye(4, dtype=np.float64) - K @ self.H) @ self.P
        return float(self.state[0]), float(self.state[1]), float(self.state[2]), float(self.state[3])


class TrackTrajectoryHistory:
    """Maintains time-series history for a single entity track ID."""

    def __init__(self, track_id: int, is_ball: bool = False, config: Optional[MetricTrajectoryConfig] = None) -> None:
        self.track_id = track_id
        self.is_ball = is_ball
        self.config = config or MetricTrajectoryConfig()
        self.observations: List[Union[PlayerMetricObservation, BallMetricObservation]] = []
        self._kalman: Optional[LinearKalman2D] = None
        self._last_valid_time: Optional[float] = None

    def add_observation(self, obs: Union[PlayerMetricObservation, BallMetricObservation]) -> None:
        self.observations.append(obs)
        max_speed = self.config.max_ball_speed_mps if self.is_ball else self.config.max_player_speed_mps

        # Update Kalman filter if enabled and position is valid
        if self.config.smoothing_method == SmoothingMethod.KALMAN:
            if obs.position_valid and obs.pitch_x_m is not None and obs.pitch_y_m is not None:
                max_gap_s = (self.config.max_interpolation_gap_frames * 0.04) + 0.05
                if self._kalman is None or (self._last_valid_time is not None and (obs.timestamp - self._last_valid_time) > max_gap_s):
                    self._kalman = LinearKalman2D(
                        obs.pitch_x_m,
                        obs.pitch_y_m,
                        q_std=self.config.kalman_process_noise_std,
                        r_std=self.config.kalman_measurement_noise_std,
                    )
                    obs.smoothed_x_m = obs.pitch_x_m
                    obs.smoothed_y_m = obs.pitch_y_m
                    obs.velocity_x_mps = 0.0
                    obs.velocity_y_mps = 0.0
                    obs.speed_mps = 0.0
                    obs.speed_plausible = True
                else:
                    dt = max(0.001, obs.timestamp - self._last_valid_time) if self._last_valid_time else 0.04
                    self._kalman.predict(dt=dt)
                    sx, sy, vx, vy = self._kalman.update(obs.pitch_x_m, obs.pitch_y_m)
                    obs.smoothed_x_m = sx
                    obs.smoothed_y_m = sy
                    obs.velocity_x_mps = vx
                    obs.velocity_y_mps = vy
                    spd = float(np.hypot(vx, vy))
                    obs.speed_mps = spd
                    obs.speed_plausible = (spd <= max_speed)

                self._last_valid_time = obs.timestamp
            else:
                obs.smoothed_x_m = None
                obs.smoothed_y_m = None
                obs.velocity_x_mps = None
                obs.velocity_y_mps = None
                obs.speed_mps = None
                obs.speed_plausible = True
        elif self.config.smoothing_method == SmoothingMethod.RAW:
            obs.smoothed_x_m = obs.pitch_x_m
            obs.smoothed_y_m = obs.pitch_y_m

    def compute_windowed_velocities_and_smoothing(self) -> None:
        """Compute central differences velocities and moving polynomial smoothing in batch."""
        n = len(self.observations)
        if n == 0:
            return

        # 1. Moving Polynomial Smoothing if requested
        if self.config.smoothing_method == SmoothingMethod.POLYNOMIAL:
            w = self.config.polynomial_window_size
            half_w = w // 2
            for i in range(n):
                obs = self.observations[i]
                if not obs.position_valid or obs.pitch_x_m is None:
                    continue

                # Gather valid window within frame distance
                i_start = max(0, i - half_w)
                i_end = min(n, i + half_w + 1)
                window = [
                    self.observations[k]
                    for k in range(i_start, i_end)
                    if self.observations[k].position_valid
                    and self.observations[k].pitch_x_m is not None
                    and abs(self.observations[k].frame_index - obs.frame_index) <= half_w
                ]

                if len(window) >= 3:
                    xs = [o.pitch_x_m for o in window]
                    ys = [o.pitch_y_m for o in window]
                    ts = [o.timestamp - obs.timestamp for o in window]
                    # Degree 1 or 2 fit
                    deg = 2 if len(window) >= 4 else 1
                    try:
                        poly_x = np.polyfit(ts, xs, deg)
                        poly_y = np.polyfit(ts, ys, deg)
                        obs.smoothed_x_m = float(poly_x[-1])
                        obs.smoothed_y_m = float(poly_y[-1])
                    except np.linalg.LinAlgError:
                        obs.smoothed_x_m = obs.pitch_x_m
                        obs.smoothed_y_m = obs.pitch_y_m
                else:
                    obs.smoothed_x_m = obs.pitch_x_m
                    obs.smoothed_y_m = obs.pitch_y_m

        # 2. Central Differences Velocity Calculation (for RAW and POLYNOMIAL)
        if self.config.smoothing_method in (SmoothingMethod.RAW, SmoothingMethod.POLYNOMIAL):
            for i in range(n):
                obs = self.observations[i]
                if not obs.position_valid:
                    obs.velocity_x_mps = None
                    obs.velocity_y_mps = None
                    obs.speed_mps = None
                    continue

                pos_x_key = "smoothed_x_m" if obs.smoothed_x_m is not None else "pitch_x_m"
                pos_y_key = "smoothed_y_m" if obs.smoothed_y_m is not None else "pitch_y_m"

                has_prev = (
                    (i > 0)
                    and self.observations[i - 1].position_valid
                    and (obs.frame_index - self.observations[i - 1].frame_index) <= self.config.max_interpolation_gap_frames
                )
                has_next = (
                    (i < n - 1)
                    and self.observations[i + 1].position_valid
                    and (self.observations[i + 1].frame_index - obs.frame_index) <= self.config.max_interpolation_gap_frames
                )

                if has_prev and has_next:
                    prev_obs = self.observations[i - 1]
                    next_obs = self.observations[i + 1]
                    dt = next_obs.timestamp - prev_obs.timestamp
                    if dt > 1e-4:
                        vx = (getattr(next_obs, pos_x_key) - getattr(prev_obs, pos_x_key)) / dt
                        vy = (getattr(next_obs, pos_y_key) - getattr(prev_obs, pos_y_key)) / dt
                        obs.velocity_x_mps = float(vx)
                        obs.velocity_y_mps = float(vy)
                        obs.speed_mps = float(np.hypot(vx, vy))
                elif has_next:
                    # Forward difference
                    next_obs = self.observations[i + 1]
                    dt = next_obs.timestamp - obs.timestamp
                    if dt > 1e-4:
                        vx = (getattr(next_obs, pos_x_key) - getattr(obs, pos_x_key)) / dt
                        vy = (getattr(next_obs, pos_y_key) - getattr(obs, pos_y_key)) / dt
                        obs.velocity_x_mps = float(vx)
                        obs.velocity_y_mps = float(vy)
                        obs.speed_mps = float(np.hypot(vx, vy))
                elif has_prev:
                    # Backward difference
                    prev_obs = self.observations[i - 1]
                    dt = obs.timestamp - prev_obs.timestamp
                    if dt > 1e-4:
                        vx = (getattr(obs, pos_x_key) - getattr(prev_obs, pos_x_key)) / dt
                        vy = (getattr(obs, pos_y_key) - getattr(prev_obs, pos_y_key)) / dt
                        obs.velocity_x_mps = float(vx)
                        obs.velocity_y_mps = float(vy)
                        obs.speed_mps = float(np.hypot(vx, vy))
                else:
                    obs.velocity_x_mps = None
                    obs.velocity_y_mps = None
                    obs.speed_mps = None

        # 3. Physical Plausibility Flagging
        max_speed = self.config.max_ball_speed_mps if self.is_ball else self.config.max_player_speed_mps
        for obs in self.observations:
            if obs.speed_mps is not None:
                obs.speed_plausible = (obs.speed_mps <= max_speed)


class MetricTrajectoryEngine:
    """Orchestrates track projection, trajectory state maintenance, smoothing, and export."""

    def __init__(self, config: Optional[MetricTrajectoryConfig] = None) -> None:
        self.config = config or MetricTrajectoryConfig()
        self.player_histories: Dict[int, TrackTrajectoryHistory] = {}
        self.ball_history: TrackTrajectoryHistory = TrackTrajectoryHistory(
            track_id=0, is_ball=True, config=self.config
        )

    def reset(self) -> None:
        """Reset all active trajectory tracks."""
        self.player_histories.clear()
        self.ball_history = TrackTrajectoryHistory(
            track_id=0, is_ball=True, config=self.config
        )

    def process_frame(
        self,
        frame_index: int,
        timestamp: float,
        player_tracks: List[Dict[str, Any]],
        ball_detection_or_track: Optional[Dict[str, Any]],
        calibration_result: Union[PitchCalibrationResult, TemporalCalibrationResult],
    ) -> Tuple[List[PlayerMetricObservation], Optional[BallMetricObservation]]:
        """Project current frame player and ball tracks onto metric pitch and update histories."""
        player_observations: List[PlayerMetricObservation] = []

        # 1. Process Players
        for p in player_tracks:
            tid = int(p.get("track_id", -1))
            bbox = p.get("bbox") or p.get("box")
            team_label = p.get("team_label") or p.get("team")
            role = p.get("role")

            if tid not in self.player_histories:
                self.player_histories[tid] = TrackTrajectoryHistory(
                    track_id=tid, is_ball=False, config=self.config
                )

            obs = self._project_player(
                track_id=tid,
                frame_index=frame_index,
                timestamp=timestamp,
                bbox=bbox,
                team_label=team_label,
                role=role,
                calibration_result=calibration_result,
            )
            self.player_histories[tid].add_observation(obs)
            player_observations.append(obs)

        # 2. Process Ball
        ball_obs: Optional[BallMetricObservation] = None
        if ball_detection_or_track:
            b_bbox = ball_detection_or_track.get("bbox") or ball_detection_or_track.get("box")
            b_tid = int(ball_detection_or_track.get("track_id", 0))
            ball_obs = self._project_ball(
                track_id=b_tid,
                frame_index=frame_index,
                timestamp=timestamp,
                bbox=b_bbox,
                calibration_result=calibration_result,
            )
            self.ball_history.add_observation(ball_obs)

        return player_observations, ball_obs

    def _project_player(
        self,
        track_id: int,
        frame_index: int,
        timestamp: float,
        bbox: Optional[Union[List[float], Tuple[float, float, float, float]]],
        team_label: Optional[str],
        role: Optional[str],
        calibration_result: Union[PitchCalibrationResult, TemporalCalibrationResult],
    ) -> PlayerMetricObservation:
        """Project player bottom-center anchor onto pitch ground plane."""
        if bbox is None or len(bbox) < 4:
            return PlayerMetricObservation(
                track_id=track_id,
                frame_index=frame_index,
                timestamp=timestamp,
                team_label=team_label,
                role=role,
                position_valid=False,
                invalidation_reason="MISSING_BBOX",
            )

        x1, y1, x2, y2 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
        if x2 <= x1 or y2 <= y1:
            return PlayerMetricObservation(
                track_id=track_id,
                frame_index=frame_index,
                timestamp=timestamp,
                team_label=team_label,
                role=role,
                position_valid=False,
                invalidation_reason="DEGENERATE_BBOX",
            )

        anchor_u = (x1 + x2) / 2.0
        anchor_v = y2

        calib_state = getattr(calibration_result, "state", TemporalCalibrationState.CALIBRATED)
        calib_state_str = calib_state.value if hasattr(calib_state, "value") else str(calib_state)
        calib_age = getattr(calibration_result, "calibration_age", 0)
        calib_conf = getattr(calibration_result, "propagation_confidence", 1.0 if calibration_result.valid else 0.0)

        if not calibration_result.valid:
            return PlayerMetricObservation(
                track_id=track_id,
                frame_index=frame_index,
                timestamp=timestamp,
                team_label=team_label,
                role=role,
                image_anchor_px=(anchor_u, anchor_v),
                calibration_state=calib_state_str,
                calibration_age=calib_age,
                calibration_confidence=calib_conf,
                position_valid=False,
                invalidation_reason="INVALID_CALIBRATION",
            )

        pitch_pt = calibration_result.image_to_pitch(anchor_u, anchor_v, check_bounds=False)
        if pitch_pt is None:
            return PlayerMetricObservation(
                track_id=track_id,
                frame_index=frame_index,
                timestamp=timestamp,
                team_label=team_label,
                role=role,
                image_anchor_px=(anchor_u, anchor_v),
                calibration_state=calib_state_str,
                calibration_age=calib_age,
                calibration_confidence=calib_conf,
                position_valid=False,
                invalidation_reason="UNPROJECTABLE_HOMOGRAPHY",
            )

        px, py = pitch_pt
        is_inside = self.config.pitch_dimensions.is_inside(px, py, margin_m=self.config.pitch_margin_m)

        return PlayerMetricObservation(
            track_id=track_id,
            frame_index=frame_index,
            timestamp=timestamp,
            team_label=team_label,
            role=role,
            image_anchor_px=(anchor_u, anchor_v),
            pitch_x_m=px,
            pitch_y_m=py,
            calibration_state=calib_state_str,
            calibration_age=calib_age,
            calibration_confidence=calib_conf,
            position_valid=True,
            is_inside_pitch=is_inside,
        )

    def _project_ball(
        self,
        track_id: int,
        frame_index: int,
        timestamp: float,
        bbox: Optional[Union[List[float], Tuple[float, float, float, float]]],
        calibration_result: Union[PitchCalibrationResult, TemporalCalibrationResult],
    ) -> BallMetricObservation:
        """Project ball center anchor onto pitch ground plane."""
        if bbox is None or len(bbox) < 4:
            return BallMetricObservation(
                track_id=track_id,
                frame_index=frame_index,
                timestamp=timestamp,
                position_valid=False,
                invalidation_reason="MISSING_BALL_BBOX",
            )

        x1, y1, x2, y2 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
        if x2 <= x1 or y2 <= y1:
            return BallMetricObservation(
                track_id=track_id,
                frame_index=frame_index,
                timestamp=timestamp,
                position_valid=False,
                invalidation_reason="DEGENERATE_BALL_BBOX",
            )

        center_u = (x1 + x2) / 2.0
        center_v = (y1 + y2) / 2.0

        calib_state = getattr(calibration_result, "state", TemporalCalibrationState.CALIBRATED)
        calib_state_str = calib_state.value if hasattr(calib_state, "value") else str(calib_state)
        calib_age = getattr(calibration_result, "calibration_age", 0)
        calib_conf = getattr(calibration_result, "propagation_confidence", 1.0 if calibration_result.valid else 0.0)

        if not calibration_result.valid:
            return BallMetricObservation(
                track_id=track_id,
                frame_index=frame_index,
                timestamp=timestamp,
                image_anchor_px=(center_u, center_v),
                calibration_state=calib_state_str,
                calibration_age=calib_age,
                calibration_confidence=calib_conf,
                position_valid=False,
                invalidation_reason="INVALID_CALIBRATION",
            )

        pitch_pt = calibration_result.image_to_pitch(center_u, center_v, check_bounds=False)
        if pitch_pt is None:
            return BallMetricObservation(
                track_id=track_id,
                frame_index=frame_index,
                timestamp=timestamp,
                image_anchor_px=(center_u, center_v),
                calibration_state=calib_state_str,
                calibration_age=calib_age,
                calibration_confidence=calib_conf,
                position_valid=False,
                invalidation_reason="UNPROJECTABLE_HOMOGRAPHY",
            )

        px, py = pitch_pt
        is_inside = self.config.pitch_dimensions.is_inside(px, py, margin_m=self.config.pitch_margin_m)

        return BallMetricObservation(
            track_id=track_id,
            frame_index=frame_index,
            timestamp=timestamp,
            image_anchor_px=(center_u, center_v),
            pitch_x_m=px,
            pitch_y_m=py,
            calibration_state=calib_state_str,
            calibration_age=calib_age,
            calibration_confidence=calib_conf,
            position_valid=True,
            is_inside_pitch=is_inside,
        )

    def finalize_offline_smoothing(self) -> None:
        """Run batch smoothing and central difference velocity calculations across all tracks."""
        for hist in self.player_histories.values():
            hist.compute_windowed_velocities_and_smoothing()
        self.ball_history.compute_windowed_velocities_and_smoothing()

    def export_to_jsonl(self, output_file: Union[str, Path], sequence_id: str = "") -> int:
        """Export all framed entity metric trajectories into structured JSONL format."""
        out_p = Path(output_file)
        out_p.parent.mkdir(parents=True, exist_ok=True)

        # Collect observations grouped by frame
        by_frame: Dict[int, Dict[str, Any]] = {}

        for tid, hist in self.player_histories.items():
            for obs in hist.observations:
                fid = obs.frame_index
                if fid not in by_frame:
                    by_frame[fid] = {
                        "sequence_id": sequence_id,
                        "frame_index": fid,
                        "timestamp": obs.timestamp,
                        "players": [],
                        "ball": None,
                    }
                by_frame[fid]["players"].append(asdict(obs))

        for b_obs in self.ball_history.observations:
            fid = b_obs.frame_index
            if fid not in by_frame:
                by_frame[fid] = {
                    "sequence_id": sequence_id,
                    "frame_index": fid,
                    "timestamp": b_obs.timestamp,
                    "players": [],
                    "ball": None,
                }
            by_frame[fid]["ball"] = asdict(b_obs)

        count = 0
        import json
        with open(out_p, "w") as f:
            for fid in sorted(by_frame.keys()):
                f.write(json.dumps(by_frame[fid]) + "\n")
                count += 1

        logger.info("Exported %d frame trajectory records to %s", count, out_p)
        return count
