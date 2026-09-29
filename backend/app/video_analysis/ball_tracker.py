from __future__ import annotations

from dataclasses import asdict, dataclass
from math import hypot, sqrt
from typing import Any

from app.video_analysis.detectors import RawDetection
from app.video_analysis.tracking_schemas import (
    BallLifecycleState,
    BallObservationState,
    BallTrackObservation,
)


@dataclass(frozen=True)
class BallTrackConfig:
    """Explicit, frozen configuration for BallTrackManager."""

    min_detection_confidence: float = 0.25         # Locked canonical ball threshold
    max_gap_interpolation: int = 15                 # Max missing frames allowed for interpolation (~0.5s at 30 fps)
    max_velocity_pixels_per_frame: float = 120.0    # Physical velocity ceiling in pixels/frame
    spatial_gate_base_distance: float = 150.0      # Base search radius in pixels
    trajectory_history_length: int = 300            # Frame history for retrospective smoothing & diagnostics
    fps: float = 30.0
    version: str = "1.0.0"

    # --- V2 Extensions (Defaults preserve V1 behavior when not explicitly set) ---
    spatial_gate_growth_per_frame: float = 35.0    # Sub-linear expansion per missing frame
    spatial_gate_max_radius: float | None = None   # Hard cap on spatial gate radius (None = unbounded V1)
    enable_track_lifecycle: bool = False           # Multi-track lifecycle & identity management
    lost_timeout_frames: int = 25                  # Frames in LOST state before terminating tracklet (~0.8s)
    reacquisition_max_distance: float = 300.0      # Max distance to re-associate a lost track vs spawning new ID
    anchor_consistency_max_speed: float = 60.0     # Max average speed across gap to accept candidate as valid anchor
    conditional_interpolation_max_speed: float = 30.0  # Speed ceiling for 4-5 frame gaps
    conditional_interpolation_max_dist: float = 150.0   # Distance ceiling for 4-5 frame gaps
    max_safe_interpolation_gap: int = 3            # Gaps <= this are interpolated if anchor is consistent


def create_ball_track_config_v2(
    fps: float = 30.0,
    spatial_gate_max_radius: float = 500.0,
    lost_timeout_frames: int = 25,
    reacquisition_max_distance: float = 300.0,
    anchor_consistency_max_speed: float = 60.0,
    conditional_interpolation_max_speed: float = 30.0,
    conditional_interpolation_max_dist: float = 150.0,
    max_gap_interpolation: int = 0,
    max_safe_interpolation_gap: int = 0,
) -> BallTrackConfig:
    """Factory creating a locked BallTrackConfig V2 instance with optimal defaults."""
    return BallTrackConfig(
        fps=fps,
        version="2.0.0",
        min_detection_confidence=0.25,
        max_gap_interpolation=max_gap_interpolation,
        max_velocity_pixels_per_frame=120.0,
        spatial_gate_base_distance=150.0,
        trajectory_history_length=300,
        spatial_gate_growth_per_frame=35.0,
        spatial_gate_max_radius=spatial_gate_max_radius,
        enable_track_lifecycle=True,
        lost_timeout_frames=lost_timeout_frames,
        reacquisition_max_distance=reacquisition_max_distance,
        anchor_consistency_max_speed=anchor_consistency_max_speed,
        conditional_interpolation_max_speed=conditional_interpolation_max_speed,
        conditional_interpolation_max_dist=conditional_interpolation_max_dist,
        max_safe_interpolation_gap=max_safe_interpolation_gap,
    )


class BallTrackManager:
    """
    Dedicated temporal ball tracker and gap interpolation manager.
    Treats ball tracking strictly separately from multi-player tracking.

    States:
      - DETECTED: Valid detector observation with confidence >= min_detection_confidence and consistent motion.
      - PREDICTED: Forward motion prediction during active tracking when observation is missing (1 <= gap <= max_gap).
      - INTERPOLATED: Retrospectively smoothed positions across a short gap once re-detected.
      - LOST: Out of play or missing for > max_gap (no trajectory hallucination).
    """

    def __init__(self, config: BallTrackConfig | None = None) -> None:
        self.config = config or BallTrackConfig()
        self.reset()

    def reset(self) -> None:
        """Resets tracker state."""
        self._history: dict[int, BallTrackObservation] = {}
        self._last_detected_frame: int | None = None
        self._previous_detected_frame: int | None = None
        self._pending_gap_frames: list[int] = []
        self._consecutive_misses: int = 0
        self._recovered_gaps_count: int = 0
        self._recovered_frames_count: int = 0
        self._rejected_jump_count: int = 0
        self._rejected_anchor_count: int = 0

        # V2 lifecycle state
        self._current_track_id: int = 1
        self._lifecycle_state: BallLifecycleState = BallLifecycleState.LOST
        self._last_active_position: tuple[float, float] | None = None
        self._total_spawned_tracks: int = 0

    @property
    def history(self) -> dict[int, BallTrackObservation]:
        """Returns map of frame_index -> BallTrackObservation."""
        return dict(self._history)

    @property
    def recovered_gaps_count(self) -> int:
        return self._recovered_gaps_count

    @property
    def recovered_frames_count(self) -> int:
        return self._recovered_frames_count

    @property
    def rejected_jump_count(self) -> int:
        return self._rejected_jump_count

    @property
    def rejected_anchor_count(self) -> int:
        return self._rejected_anchor_count

    @property
    def current_track_id(self) -> int:
        return self._current_track_id

    @property
    def lifecycle_state(self) -> BallLifecycleState:
        return self._lifecycle_state

    @property
    def total_spawned_tracks(self) -> int:
        return self._total_spawned_tracks

    @staticmethod
    def _bbox_center(bbox: tuple[float, float, float, float] | list[float]) -> tuple[float, float]:
        x1, y1, x2, y2 = bbox[:4]
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    @staticmethod
    def _bbox_at_center(
        reference_bbox: tuple[float, float, float, float],
        center: tuple[float, float],
    ) -> tuple[float, float, float, float]:
        w = max(1.0, reference_bbox[2] - reference_bbox[0])
        h = max(1.0, reference_bbox[3] - reference_bbox[1])
        x1 = center[0] - w / 2.0
        y1 = center[1] - h / 2.0
        return (x1, y1, x1 + w, y1 + h)

    def _expected_position(self, frame_index: int) -> tuple[float, float]:
        """Predicts center position based on last observed velocity."""
        if self._last_detected_frame is None:
            return (0.0, 0.0)
        last_obs = self._history[self._last_detected_frame]
        if self._previous_detected_frame is None:
            return last_obs.position

        prev_obs = self._history[self._previous_detected_frame]
        dt = max(1, last_obs.frame_index - prev_obs.frame_index)
        vx = (last_obs.position[0] - prev_obs.position[0]) / dt
        vy = (last_obs.position[1] - prev_obs.position[1]) / dt

        # Bound predicted velocity to physical ceiling
        v_mag = hypot(vx, vy)
        if v_mag > self.config.max_velocity_pixels_per_frame:
            scale = self.config.max_velocity_pixels_per_frame / v_mag
            vx *= scale
            vy *= scale

        elapsed = frame_index - last_obs.frame_index
        # Rapid velocity decay during missing frames to prevent runaway linear drift
        decay = (0.5 ** max(0, elapsed - 1)) if elapsed > 1 else 1.0
        return (
            last_obs.position[0] + vx * elapsed * decay,
            last_obs.position[1] + vy * elapsed * decay,
        )

    def _gate_radius(self, dt: int) -> float:
        """Computes spatial gate radius for a given time delta dt."""
        if self.config.spatial_gate_max_radius is not None:
            radius = self.config.spatial_gate_base_distance + self.config.spatial_gate_growth_per_frame * max(0, dt - 1)
            return min(radius, self.config.spatial_gate_max_radius)
        return max(
            self.config.spatial_gate_base_distance,
            self.config.max_velocity_pixels_per_frame * dt,
        )

    def _is_plausible_jump(
        self,
        candidate_center: tuple[float, float],
        frame_index: int,
    ) -> bool:
        """Validates that candidate motion does not exceed physical velocity limits and gate radius."""
        if self._last_detected_frame is None:
            return True

        last_obs = self._history[self._last_detected_frame]
        dt = max(1, frame_index - last_obs.frame_index)
        dist = hypot(candidate_center[0] - last_obs.position[0], candidate_center[1] - last_obs.position[1])
        speed = dist / dt

        gate_radius = self._gate_radius(dt)
        if dist > gate_radius or speed > self.config.max_velocity_pixels_per_frame:
            return False
        return True

    def _select_best_candidate(
        self,
        candidates: list[RawDetection],
        frame_index: int,
    ) -> RawDetection | None:
        """Selects best candidate using spatial gating, lifecycle state, and confidence score."""
        if not candidates:
            return None

        valid_above_thresh = [c for c in candidates if c.confidence >= self.config.min_detection_confidence]
        if not valid_above_thresh:
            return None

        if not self.config.enable_track_lifecycle:
            # V1 backwards-compatible candidate selection
            if self._last_detected_frame is None:
                return max(valid_above_thresh, key=lambda c: c.confidence)

            expected_x, expected_y = self._expected_position(frame_index)
            last_obs = self._history[self._last_detected_frame]
            dt = max(1, frame_index - last_obs.frame_index)
            gate_radius = self._gate_radius(dt)

            valid_scored: list[tuple[float, RawDetection]] = []
            for candidate in valid_above_thresh:
                center = self._bbox_center(candidate.bbox)
                if not self._is_plausible_jump(center, frame_index):
                    self._rejected_jump_count += 1
                    continue

                dist = hypot(center[0] - expected_x, center[1] - expected_y)
                proximity = max(0.0, 1.0 - (dist / gate_radius))
                score = 0.6 * proximity + 0.4 * candidate.confidence
                valid_scored.append((score, candidate))

            if not valid_scored:
                return None

            valid_scored.sort(key=lambda item: item[0], reverse=True)
            return valid_scored[0][1]

        # V2 candidate selection
        if self._last_detected_frame is None:
            return max(valid_above_thresh, key=lambda c: c.confidence)

        last_obs = self._history[self._last_detected_frame]
        dt = max(1, frame_index - last_obs.frame_index)
        gate_radius = self._gate_radius(dt)
        expected_x, expected_y = self._expected_position(frame_index)

        # 1. Search within the bounded gate (speed <= 120 px/f and dist <= gate_radius)
        valid_scored: list[tuple[float, RawDetection]] = []
        for candidate in valid_above_thresh:
            center = self._bbox_center(candidate.bbox)
            if not self._is_plausible_jump(center, frame_index):
                self._rejected_jump_count += 1
                continue

            dist = hypot(center[0] - expected_x, center[1] - expected_y)
            proximity = max(0.0, 1.0 - (dist / gate_radius))
            score = 0.6 * proximity + 0.4 * candidate.confidence
            valid_scored.append((score, candidate))

        if valid_scored:
            valid_scored.sort(key=lambda item: item[0], reverse=True)
            return valid_scored[0][1]

        # 2. If dead period >= lost_timeout_frames (e.g. >= 30 frames), allow solid restart candidates
        if self.config.enable_track_lifecycle and self._consecutive_misses >= self.config.lost_timeout_frames:
            restarts = [c for c in valid_above_thresh if c.confidence >= 0.30]
            if restarts:
                return max(restarts, key=lambda c: c.confidence)

        return None

    def _clean_uninterpolated_gap(self) -> None:
        """Converts pending predicted frames into LOST observations to eliminate hallucinated boxes."""
        for f in self._pending_gap_frames:
            if f in self._history:
                old_obs = self._history[f]
                self._history[f] = BallTrackObservation(
                    frame_index=f,
                    timestamp=old_obs.timestamp,
                    bbox=(0.0, 0.0, 0.0, 0.0),
                    position=(0.0, 0.0),
                    velocity=None,
                    observation_state=BallObservationState.LOST,
                    gap_length=old_obs.gap_length,
                    confidence=None,
                    source_detector=None,
                    source_frame_detections=(),
                    track_id=None,
                    lifecycle_state=BallLifecycleState.LOST,
                )
        self._pending_gap_frames.clear()

    def _interpolate_short_gap(self, end_frame: int) -> None:
        """
        Retrospectively interpolates missing frames in pending gap [t_start, t_end].
        Replaces PREDICTED states with INTERPOLATED states if consistency checks pass.
        """
        if not self._pending_gap_frames or self._last_detected_frame is None:
            return

        start_frame = self._last_detected_frame
        gap_size = len(self._pending_gap_frames)

        # Check maximum gap ceiling
        if gap_size > self.config.max_gap_interpolation:
            if self.config.enable_track_lifecycle:
                self._clean_uninterpolated_gap()
            else:
                self._pending_gap_frames.clear()
            return

        start_obs = self._history[start_frame]
        end_obs = self._history[end_frame]
        total_dt = end_frame - start_frame
        if total_dt <= 0:
            self._pending_gap_frames.clear()
            return

        gap_dist = hypot(end_obs.position[0] - start_obs.position[0], end_obs.position[1] - start_obs.position[1])
        eff_speed = gap_dist / float(total_dt)

        if self.config.enable_track_lifecycle:
            # 1. Do not interpolate across different track identities
            if start_obs.track_id != end_obs.track_id:
                self._clean_uninterpolated_gap()
                return

            # 2. Reject distractor anchor if effective speed across gap exceeds anchor ceiling
            if eff_speed > self.config.anchor_consistency_max_speed:
                self._rejected_anchor_count += 1
                self._clean_uninterpolated_gap()
                return

            # 3. Gap length & conditional interpolation policy
            if gap_size <= self.config.max_safe_interpolation_gap:
                should_interpolate = True
            elif gap_size <= self.config.max_gap_interpolation:
                # Conditional interpolation for 4-5 frame gaps
                should_interpolate = (
                    eff_speed <= self.config.conditional_interpolation_max_speed
                    and gap_dist <= self.config.conditional_interpolation_max_dist
                )
            else:
                should_interpolate = False

            if not should_interpolate:
                self._clean_uninterpolated_gap()
                return

        # Perform linear interpolation
        for frame_idx in self._pending_gap_frames:
            alpha = (frame_idx - start_frame) / float(total_dt)
            interp_x = (1.0 - alpha) * start_obs.position[0] + alpha * end_obs.position[0]
            interp_y = (1.0 - alpha) * start_obs.position[1] + alpha * end_obs.position[1]
            interp_center = (interp_x, interp_y)
            interp_bbox = self._bbox_at_center(start_obs.bbox, interp_center)

            vx = (end_obs.position[0] - start_obs.position[0]) / float(total_dt)
            vy = (end_obs.position[1] - start_obs.position[1]) / float(total_dt)

            timestamp = frame_idx / self.config.fps

            interpolated_obs = BallTrackObservation(
                frame_index=frame_idx,
                timestamp=round(timestamp, 6),
                bbox=interp_bbox,
                position=interp_center,
                velocity=(vx, vy),
                observation_state=BallObservationState.INTERPOLATED,
                gap_length=gap_size,
                confidence=None,
                source_detector=None,
                source_frame_detections=(start_frame, end_frame),
                track_id=end_obs.track_id,
                lifecycle_state=BallLifecycleState.ACTIVE,
            )
            self._history[frame_idx] = interpolated_obs

        self._recovered_gaps_count += 1
        self._recovered_frames_count += gap_size
        self._pending_gap_frames.clear()

    def update(
        self,
        frame_index: int,
        timestamp: float,
        detections: list[RawDetection],
        source_detector: str = "rf-detr-small",
    ) -> BallTrackObservation:
        """
        Processes a single frame for the ball.
        Returns the resulting BallTrackObservation with its explicit state and persistent track identity.
        """
        ball_candidates = [
            d for d in detections if d.class_name in ("sports ball", "ball")
        ]
        best_candidate = self._select_best_candidate(ball_candidates, frame_index)

        if best_candidate is not None:
            center = self._bbox_center(best_candidate.bbox)
            bbox = (
                float(best_candidate.bbox[0]),
                float(best_candidate.bbox[1]),
                float(best_candidate.bbox[2]),
                float(best_candidate.bbox[3]),
            )

            is_new_track = False
            if self.config.enable_track_lifecycle:
                if self._total_spawned_tracks == 0:
                    self._current_track_id = 1
                    self._total_spawned_tracks = 1
                    is_new_track = True
                else:
                    ref_pos = self._last_active_position or (self._history[self._last_detected_frame].position if self._last_detected_frame else None)
                    dist = hypot(center[0] - ref_pos[0], center[1] - ref_pos[1]) if ref_pos else 0.0
                    # Replacement ball / restart condition:
                    if (
                        self._consecutive_misses >= self.config.lost_timeout_frames
                        or (self._consecutive_misses >= 10 and dist > self.config.reacquisition_max_distance)
                    ):
                        self._current_track_id += 1
                        self._total_spawned_tracks += 1
                        is_new_track = True
                        if self._pending_gap_frames:
                            self._clean_uninterpolated_gap()
                self._lifecycle_state = BallLifecycleState.ACTIVE
                assigned_track_id = self._current_track_id
            else:
                assigned_track_id = 1

            # Compute velocity if not a new track and previous detection exists
            velocity = None
            if not is_new_track and self._last_detected_frame is not None:
                last_obs = self._history[self._last_detected_frame]
                dt = max(1, frame_index - last_obs.frame_index)
                velocity = (
                    (center[0] - last_obs.position[0]) / dt,
                    (center[1] - last_obs.position[1]) / dt,
                )

            current_obs = BallTrackObservation(
                frame_index=frame_index,
                timestamp=timestamp,
                bbox=bbox,
                position=center,
                velocity=velocity,
                observation_state=BallObservationState.DETECTED,
                gap_length=0,
                confidence=float(best_candidate.confidence),
                source_detector=source_detector,
                source_frame_detections=(frame_index,),
                track_id=assigned_track_id,
                lifecycle_state=BallLifecycleState.ACTIVE,
            )
            self._history[frame_index] = current_obs

            # Retrospectively interpolate any short gap leading to this detection
            if self._pending_gap_frames:
                self._interpolate_short_gap(frame_index)

            if is_new_track:
                self._previous_detected_frame = None
            else:
                self._previous_detected_frame = self._last_detected_frame

            self._last_detected_frame = frame_index
            self._last_active_position = center
            self._consecutive_misses = 0
            return current_obs

        # No valid detection in this frame: Gap handling
        self._consecutive_misses += 1

        if self._last_detected_frame is not None and self._consecutive_misses <= self.config.max_gap_interpolation:
            # Active gap: forward predict position
            center = self._expected_position(frame_index)
            last_obs = self._history[self._last_detected_frame]
            bbox = self._bbox_at_center(last_obs.bbox, center)
            dt = max(1, frame_index - last_obs.frame_index)
            velocity = (
                (center[0] - last_obs.position[0]) / dt,
                (center[1] - last_obs.position[1]) / dt,
            )

            pred_obs = BallTrackObservation(
                frame_index=frame_index,
                timestamp=timestamp,
                bbox=bbox,
                position=center,
                velocity=velocity,
                observation_state=BallObservationState.PREDICTED,
                gap_length=self._consecutive_misses,
                confidence=None,
                source_detector=None,
                source_frame_detections=(self._last_detected_frame,),
                track_id=self._current_track_id if self.config.enable_track_lifecycle else 1,
                lifecycle_state=BallLifecycleState.ACTIVE,
            )
            self._history[frame_index] = pred_obs
            self._pending_gap_frames.append(frame_index)
            return pred_obs

        # Gap exceeds max allowed interpolation window or ball was never detected
        if self.config.enable_track_lifecycle:
            if self._pending_gap_frames:
                self._clean_uninterpolated_gap()

            if self._consecutive_misses > self.config.lost_timeout_frames:
                self._lifecycle_state = BallLifecycleState.TERMINATED
            else:
                self._lifecycle_state = BallLifecycleState.LOST
        else:
            self._pending_gap_frames.clear()

        lost_obs = BallTrackObservation(
            frame_index=frame_index,
            timestamp=timestamp,
            bbox=(0.0, 0.0, 0.0, 0.0),
            position=(0.0, 0.0),
            velocity=None,
            observation_state=BallObservationState.LOST,
            gap_length=self._consecutive_misses,
            confidence=None,
            source_detector=None,
            source_frame_detections=(),
            track_id=None,
            lifecycle_state=self._lifecycle_state if self.config.enable_track_lifecycle else BallLifecycleState.LOST,
        )
        self._history[frame_index] = lost_obs
        return lost_obs

    def metadata(self) -> dict[str, Any]:
        """Returns complete, frozen provenance and parameters."""
        data = asdict(self.config)
        data.update({
            "name": "ball_track_manager",
            "recovered_gaps_count": self._recovered_gaps_count,
            "recovered_frames_count": self._recovered_frames_count,
            "rejected_jump_count": self._rejected_jump_count,
            "rejected_anchor_count": self._rejected_anchor_count,
            "total_spawned_tracks": self._total_spawned_tracks,
            "current_track_id": self._current_track_id,
            "lifecycle_state": self._lifecycle_state.value if isinstance(self._lifecycle_state, BallLifecycleState) else str(self._lifecycle_state),
        })
        return data
