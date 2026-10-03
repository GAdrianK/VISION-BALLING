from __future__ import annotations

import numpy as np
import pytest
from app.video_analysis.detectors import RawDetection
from app.video_analysis.pipeline import VideoPipeline
from app.video_analysis.trackers import BallTracker


def frame() -> np.ndarray:
    return np.zeros((200, 200, 3), dtype=np.uint8)


def ball(
    center_x: int,
    center_y: int = 100,
    confidence: float = 0.8,
) -> RawDetection:
    return RawDetection(
        class_name="sports ball",
        football_role="ball_candidate",
        confidence=confidence,
        bbox=(center_x - 4, center_y - 4, center_x + 4, center_y + 4),
    )


def test_continuous_motion_uses_recent_velocity():
    tracker = BallTracker(max_distance_ratio=0.2)

    positions = [
        tracker.update(0, frame(), [ball(20)]),
        tracker.update(1, frame(), [ball(30)]),
        tracker.update(2, frame(), [ball(40)]),
    ]

    assert [position.state for position in positions if position] == [
        "observed",
        "observed",
        "observed",
    ]
    assert [position.center[0] for position in positions if position] == [20, 30, 40]


def test_short_disappearance_uses_motion_prediction():
    tracker = BallTracker(max_missing_frames=5, max_distance_ratio=0.2)
    tracker.update(0, frame(), [ball(20)])
    tracker.update(1, frame(), [ball(30)])

    first = tracker.update(2, frame(), [])
    second = tracker.update(3, frame(), [])

    assert first and first.state == "predicted" and first.center[0] == 40
    assert second and second.state == "predicted" and second.center[0] == 50


def test_prediction_stops_and_resets_after_long_disappearance():
    tracker = BallTracker(max_missing_frames=2)
    tracker.update(0, frame(), [ball(20)])

    assert tracker.update(1, frame(), []) is not None
    assert tracker.update(2, frame(), []) is not None
    assert tracker.update(3, frame(), []) is None
    assert tracker.trajectory == ()
    assert tracker.reset_count == 1


def test_default_prediction_limit_is_exactly_five_and_stays_in_frame():
    tracker = BallTracker()
    tracker.update(0, frame(), [ball(180)])
    tracker.update(1, frame(), [ball(195)])

    predictions = [tracker.update(index, frame(), []) for index in range(2, 8)]

    assert all(position is not None for position in predictions[:5])
    assert predictions[5] is None
    assert all(position.confidence is None for position in predictions[:5] if position)
    assert all(
        0 <= position.bbox[0] < position.bbox[2] <= 200
        and 0 <= position.bbox[1] < position.bbox[3] <= 200
        for position in predictions[:5]
        if position
    )


def test_multiple_candidates_use_confidence_position_and_motion():
    tracker = BallTracker(max_distance_ratio=0.5)
    tracker.update(0, frame(), [ball(20)])
    tracker.update(1, frame(), [ball(30)])
    candidates = [ball(40, confidence=0.55), ball(120, confidence=0.99)]
    original_candidates = list(candidates)

    selected = tracker.update(2, frame(), candidates)

    assert selected and selected.center[0] == 40
    assert selected.confidence == 0.55
    assert candidates == original_candidates


def test_aberrant_jump_starts_a_new_trajectory():
    tracker = BallTracker(max_distance_ratio=0.05)
    tracker.update(0, frame(), [ball(20)])
    tracker.update(1, frame(), [ball(30)])

    jumped = tracker.update(2, frame(), [ball(180, confidence=0.95)])
    rendered = frame()

    assert jumped is not None
    assert tracker.trajectory == (jumped,)
    assert tracker.reset_count == 1
    VideoPipeline._annotate_ball_trajectory(rendered, jumped, tracker.trajectory)
    assert not np.any(rendered[:, :100])

    predicted = tracker.update(3, frame(), [])

    assert jumped and jumped.state == "observed" and jumped.center[0] == 180
    assert predicted and predicted.center[0] == 180
    assert len(tracker.trajectory) == 2


def test_resolution_change_clamps_prediction_and_invalid_size_resets():
    tracker = BallTracker()
    tracker.update(0, frame(), [ball(180)])
    tracker.update(1, frame(), [ball(195)])

    smaller_frame = np.zeros((40, 40, 3), dtype=np.uint8)
    predicted = tracker.update(2, smaller_frame, [])

    assert predicted is not None
    x1, y1, x2, y2 = predicted.bbox
    assert 0 <= x1 < x2 <= 40
    assert 0 <= y1 < y2 <= 40
    assert tracker.update(3, np.zeros((0, 40, 3), dtype=np.uint8), []) is None
    assert tracker.trajectory == ()
    assert tracker.reset_count == 1


def test_explicit_reset_discards_previous_motion():
    tracker = BallTracker()
    tracker.update(0, frame(), [ball(20)])
    tracker.update(1, frame(), [ball(30)])

    tracker.reset()

    assert tracker.trajectory == ()
    assert tracker.update(2, frame(), []) is None
    restarted = tracker.update(3, frame(), [ball(150)])
    assert restarted and restarted.center[0] == 150
    assert len(tracker.trajectory) == 1


def test_observed_and_predicted_positions_are_explicitly_separated():
    tracker = BallTracker()

    observed = tracker.update(0, frame(), [ball(20, confidence=0.75)])
    predicted = tracker.update(1, frame(), [])

    assert observed and observed.state == "observed"
    assert observed.class_name == "sports ball"
    assert observed.confidence == 0.75
    assert predicted and predicted.state == "predicted"
    assert predicted.class_name == "sports ball"
    assert predicted.confidence is None


def test_trajectory_rendering_draws_a_short_visible_path():
    tracker = BallTracker(trajectory_length=3)
    tracker.update(0, frame(), [ball(20, center_y=40)])
    tracker.update(1, frame(), [ball(30, center_y=40)])
    current = tracker.update(2, frame(), [])
    rendered = frame()

    assert current is not None
    VideoPipeline._annotate_ball_trajectory(
        rendered, current, tracker.trajectory
    )

    assert np.count_nonzero(rendered) > 0
    assert np.any(rendered[36:45, 20:41])


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"max_missing_frames": -1}, "max_missing_frames"),
        ({"trajectory_length": 0}, "trajectory_length"),
        ({"max_distance_ratio": 0}, "max_distance_ratio"),
        ({"max_distance_ratio": 1.01}, "max_distance_ratio"),
    ],
)
def test_invalid_configuration_is_rejected(kwargs, message):
    with pytest.raises(ValueError, match=message):
        BallTracker(**kwargs)
