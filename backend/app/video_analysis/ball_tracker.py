from __future__ import annotations

from dataclasses import asdict, dataclass
from math import hypot, sqrt
from typing import Any

from app.video_analysis.detectors import RawDetection
from app.video_analysis.tracking_schemas import BallObservationState, BallTrackObservation


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

        elapsed = frame_index - last_obs.frame_index
        return (
            last_obs.position[0] + vx * elapsed,
            last_obs.position[1] + vy * elapsed,
        )

    def _is_plausible_jump(
        self,
        candidate_center: tuple[float, float],
        frame_index: int,
    ) -> bool:
        """Validates that candidate motion does not exceed physical velocity limits."""
        if self._last_detected_frame is None:
            return True

        last_obs = self._history[self._last_detected_frame]
        dt = max(1, frame_index - last_obs.frame_index)
        dist = hypot(candidate_center[0] - last_obs.position[0], candidate_center[1] - last_obs.position[1])
        speed = dist / dt

        # Dynamic gate expanding with time elapsed up to max physical velocity
        max_allowed_dist = max(
            self.config.spatial_gate_base_distance,
            self.config.max_velocity_pixels_per_frame * dt,
        )
        if dist > max_allowed_dist or speed > self.config.max_velocity_pixels_per_frame:
            return False
        return True

    def _select_best_candidate(
        self,
        candidates: list[RawDetection],
        frame_index: int,
    ) -> RawDetection | None:
        """Selects best candidate using spatial gating and confidence score."""
        if not candidates:
            return None

        if self._last_detected_frame is None:
            # First detection: select highest confidence above threshold
            valid = [c for c in candidates if c.confidence >= self.config.min_detection_confidence]
            return max(valid, key=lambda c: c.confidence) if valid else None

        expected_x, expected_y = self._expected_position(frame_index)
        last_obs = self._history[self._last_detected_frame]
        dt = max(1, frame_index - last_obs.frame_index)
        gate_radius = max(
            self.config.spatial_gate_base_distance,
            self.config.max_velocity_pixels_per_frame * dt,
        )

        valid_scored: list[tuple[float, RawDetection]] = []
        for candidate in candidates:
            if candidate.confidence < self.config.min_detection_confidence:
                continue
            center = self._bbox_center(candidate.bbox)
            if not self._is_plausible_jump(center, frame_index):
                self._rejected_jump_count += 1
                continue

            dist = hypot(center[0] - expected_x, center[1] - expected_y)
            proximity = max(0.0, 1.0 - (dist / gate_radius))
            # 60% spatial proximity + 40% detector confidence
            score = 0.6 * proximity + 0.4 * candidate.confidence
            valid_scored.append((score, candidate))

        if not valid_scored:
            return None

        valid_scored.sort(key=lambda item: item[0], reverse=True)
        return valid_scored[0][1]

    def _interpolate_short_gap(self, end_frame: int) -> None:
        """
        Retrospectively interpolates missing frames in pending gap [t_start, t_end].
        Replaces PREDICTED states with INTERPOLATED states.
        """
        if not self._pending_gap_frames or self._last_detected_frame is None:
            return

        start_frame = self._last_detected_frame
        gap_size = len(self._pending_gap_frames)
        if gap_size > self.config.max_gap_interpolation:
            return

        start_obs = self._history[start_frame]
        end_obs = self._history[end_frame]
        total_dt = end_frame - start_frame

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
        Returns the resulting BallTrackObservation with its explicit state.
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

            # Compute velocity if previous detection exists
            velocity = None
            if self._last_detected_frame is not None:
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
            )
            self._history[frame_index] = current_obs

            # Retrospectively interpolate any short gap leading to this detection
            if self._pending_gap_frames:
                self._interpolate_short_gap(frame_index)

            self._previous_detected_frame = self._last_detected_frame
            self._last_detected_frame = frame_index
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
            )
            self._history[frame_index] = pred_obs
            self._pending_gap_frames.append(frame_index)
            return pred_obs

        # Lost state: gap exceeds max allowed interpolation window or ball was never detected
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
        })
        return data
