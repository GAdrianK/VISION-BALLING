from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from app.video_analysis.backends import (
    build_audio_remux_command,
    diagnose_video_backend,
)
from app.video_analysis.detectors import (
    OpenCVHOGPersonDetector,
    UltralyticsYOLODetector,
    create_detector,
)
from app.video_analysis.trackers import DisabledTracker, IoUTracker, create_tracker


def detection():
    from app.video_analysis.detectors import RawDetection

    return RawDetection("person", "player_candidate", 0.9, (10, 10, 30, 50))


def test_detector_selection_and_hog_fallback():
    assert isinstance(create_detector("hog"), OpenCVHOGPersonDetector)
    assert isinstance(create_detector("yolo"), UltralyticsYOLODetector)
    with pytest.raises(ValueError):
        create_detector("mystery")


def test_tracker_disabled():
    tracker = create_tracker(False, "iou")
    assert isinstance(tracker, DisabledTracker)
    output = tracker.update(np.zeros((10, 10, 3)), [detection()])
    assert output[0].track_id is None


def test_tracker_reset_and_job_isolation():
    first, second = IoUTracker(), IoUTracker()
    frame = np.zeros((10, 10, 3))
    assert first.update(frame, [detection()])[0].track_id == 1
    assert second.update(frame, [detection()])[0].track_id == 1
    first.update(frame, [detection()])
    first.reset()
    assert first.update(frame, [detection()])[0].track_id == 1


def test_ball_is_not_assigned_unstable_track():
    from app.video_analysis.detectors import RawDetection

    tracker = IoUTracker()
    item = RawDetection("sports ball", "ball_candidate", 0.6, (1, 1, 4, 4))
    assert tracker.update(np.zeros((10, 10, 3)), [item])[0].track_id is None


def test_ffmpeg_diagnostic_shape():
    diagnostic = diagnose_video_backend()
    assert isinstance(diagnostic.ffmpeg_available, bool)
    assert diagnostic.video_backend in {"ffmpeg", "opencv"}


def test_ffmpeg_command_is_argument_safe(tmp_path: Path):
    command = build_audio_remux_command(
        "ffmpeg",
        tmp_path / "silent video.mp4",
        tmp_path / "source;video.mp4",
        tmp_path / "final video.mp4",
    )
    assert command[0] == "ffmpeg"
    assert str(tmp_path / "source;video.mp4") in command
    assert all("shell=True" not in part for part in command)
