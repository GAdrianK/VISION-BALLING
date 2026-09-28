from __future__ import annotations

from dataclasses import asdict, dataclass
from math import hypot
from typing import Any

from app.video_analysis.tracking_schemas import BallObservationState, BallTrackObservation


@dataclass(frozen=True)
class BallTrackingDiagnostics:
    """Comprehensive diagnostic metrics for ball temporal tracking and interpolation."""

    total_frames: int
    observed_detection_frames: int
    observed_detection_coverage: float   # observed / total_frames
    temporal_track_frames: int          # detected + interpolated
    temporal_track_coverage: float      # (detected + interpolated) / total_frames
    recovered_short_gaps: int           # number of gaps successfully bridged by interpolation
    recovered_frames_count: int         # total number of frames rescued via interpolation
    incorrect_interpolation_count: int  # interpolations contradicting ground truth if GT present
    track_fragmentation: int            # number of transitions into LOST state
    longest_continuous_track: int       # max consecutive frames with active observation
    positional_error_mean: float | None = None  # mean distance to GT center (in pixels)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_ball_diagnostics(
    ball_history: dict[int, BallTrackObservation],
    ground_truth: dict[int, tuple[float, float]] | None = None,
) -> BallTrackingDiagnostics:
    """
    Computes diagnostic tracking metrics from a sequential dictionary of BallTrackObservation.
    Optional ground_truth is a map {frame_index: (center_x, center_y)}.
    """
    if not ball_history:
        return BallTrackingDiagnostics(
            total_frames=0,
            observed_detection_frames=0,
            observed_detection_coverage=0.0,
            temporal_track_frames=0,
            temporal_track_coverage=0.0,
            recovered_short_gaps=0,
            recovered_frames_count=0,
            incorrect_interpolation_count=0,
            track_fragmentation=0,
            longest_continuous_track=0,
            positional_error_mean=None,
        )

    sorted_frames = sorted(ball_history.keys())
    total_frames = len(sorted_frames)

    observed_detection_frames = 0
    interpolated_frames = 0
    longest_continuous = 0
    current_continuous = 0
    fragmentation_count = 0
    was_lost = True

    errors: list[float] = []
    incorrect_interp = 0

    # Distinct bridged gap counting
    bridged_gaps: set[tuple[int, ...]] = set()

    for f_idx in sorted_frames:
        obs = ball_history[f_idx]
        state = obs.observation_state

        if state in (BallObservationState.DETECTED, BallObservationState.INTERPOLATED):
            if state == BallObservationState.DETECTED:
                observed_detection_frames += 1
            else:
                interpolated_frames += 1
                if obs.source_frame_detections:
                    bridged_gaps.add(obs.source_frame_detections)
            current_continuous += 1
            was_lost = False
        else:
            if state == BallObservationState.LOST and not was_lost:
                fragmentation_count += 1
                was_lost = True
            current_continuous = 0


        longest_continuous = max(longest_continuous, current_continuous)

        if ground_truth and f_idx in ground_truth:
            gt_center = ground_truth[f_idx]
            if state in (BallObservationState.DETECTED, BallObservationState.INTERPOLATED, BallObservationState.PREDICTED):
                dist = hypot(obs.position[0] - gt_center[0], obs.position[1] - gt_center[1])
                errors.append(dist)
                if state == BallObservationState.INTERPOLATED and dist > 150.0:
                    incorrect_interp += 1

    temporal_track_frames = observed_detection_frames + interpolated_frames
    observed_cov = observed_detection_frames / total_frames if total_frames > 0 else 0.0
    temporal_cov = temporal_track_frames / total_frames if total_frames > 0 else 0.0
    mean_err = float(sum(errors) / len(errors)) if errors else None

    return BallTrackingDiagnostics(
        total_frames=total_frames,
        observed_detection_frames=observed_detection_frames,
        observed_detection_coverage=round(observed_cov, 4),
        temporal_track_frames=temporal_track_frames,
        temporal_track_coverage=round(temporal_cov, 4),
        recovered_short_gaps=len(bridged_gaps),
        recovered_frames_count=interpolated_frames,
        incorrect_interpolation_count=incorrect_interp,
        track_fragmentation=fragmentation_count,
        longest_continuous_track=longest_continuous,
        positional_error_mean=round(mean_err, 2) if mean_err is not None else None,
    )
