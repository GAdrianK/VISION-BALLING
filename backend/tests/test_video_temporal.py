from __future__ import annotations

import math

import pytest

from app.video_analysis.trackers import (
    TEMPORAL_FRAME_CONVERSION_RULE,
    resolve_ball_tracker_timing,
    seconds_to_source_frames,
)


@pytest.mark.parametrize(
    ("source_fps", "expected_frames"),
    [(25, 5), (30, 6), (50, 10), (60, 12)],
)
def test_missing_duration_is_fps_independent(
    source_fps: float, expected_frames: int
):
    timing = resolve_ball_tracker_timing(
        max_missing_seconds=0.2,
        trajectory_seconds=0.5,
        source_fps=source_fps,
    )

    assert timing.max_missing_frames_effective == expected_frames
    assert timing.max_missing_frames_effective / source_fps == pytest.approx(0.2)
    assert timing.conversion_rule == TEMPORAL_FRAME_CONVERSION_RULE


@pytest.mark.parametrize(
    ("source_fps", "expected_frames"), [(25, 13), (50, 25)]
)
def test_trajectory_duration_uses_the_validated_fps(
    source_fps: float, expected_frames: int
):
    timing = resolve_ball_tracker_timing(
        max_missing_seconds=0.2,
        trajectory_seconds=0.5,
        source_fps=source_fps,
    )

    assert timing.trajectory_frames_effective == expected_frames
    assert timing.trajectory_frames_effective / source_fps == pytest.approx(
        0.5, abs=1 / source_fps
    )


def test_temporal_conversion_uses_ceiling_for_small_and_fractional_values():
    assert seconds_to_source_frames(0, 25) == 0
    assert seconds_to_source_frames(0.001, 25) == 1
    assert seconds_to_source_frames(0.11, 25) == 3
    assert seconds_to_source_frames(0, 25, minimum=1) == 1


@pytest.mark.parametrize(
    ("seconds", "source_fps"),
    [(-0.1, 25), (math.inf, 25), (math.nan, 25), (0.2, 0), (0.2, math.inf)],
)
def test_temporal_conversion_rejects_invalid_limits(
    seconds: float, source_fps: float
):
    with pytest.raises(ValueError):
        seconds_to_source_frames(seconds, source_fps)


def test_trajectory_duration_must_be_positive():
    with pytest.raises(ValueError, match="strictement positif"):
        resolve_ball_tracker_timing(
            max_missing_seconds=0.2,
            trajectory_seconds=0,
            source_fps=25,
        )
