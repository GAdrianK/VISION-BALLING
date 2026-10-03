from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pytest
from app.video_analysis.backends import (
    build_audio_remux_command,
    build_video_normalization_command,
    diagnose_video_backend,
    run_command,
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


class FakeYOLOModel:
    def __init__(self, boxes: list[SimpleNamespace]) -> None:
        self.boxes = boxes
        self.predict_kwargs = {}

    def predict(self, **kwargs):
        self.predict_kwargs = kwargs
        return [SimpleNamespace(boxes=self.boxes)]


def fake_box(class_id: int, confidence: float) -> SimpleNamespace:
    return SimpleNamespace(
        cls=np.array(class_id),
        conf=np.array(confidence),
        xyxy=np.array([[1.0, 2.0, 8.0, 9.0]]),
    )


def test_detector_selection_and_hog_fallback():
    assert isinstance(create_detector("hog"), OpenCVHOGPersonDetector)
    yolo = create_detector("yolo")
    assert isinstance(yolo, UltralyticsYOLODetector)
    assert yolo.model_profile == "coco"
    assert yolo.class_map == {0: "person", 32: "sports ball"}
    with pytest.raises(ValueError):
        create_detector("mystery")


def test_h250_model_profile_mapping():
    detector = create_detector("yolo", model_profile="h250")

    assert isinstance(detector, UltralyticsYOLODetector)
    assert detector.model_profile == "h250"
    assert detector.class_map == {0: "sports ball", 1: "person"}


def test_unknown_yolo_model_profile_is_rejected():
    with pytest.raises(ValueError, match="Profil de modèle YOLO inconnu"):
        create_detector("yolo", model_profile="unknown")


def test_explicit_class_map_has_priority_over_model_profile():
    custom_map = {7: "sports ball"}
    detector = create_detector(
        "yolo", model_profile="h250", class_map=custom_map
    )
    assert isinstance(detector, UltralyticsYOLODetector)
    model = FakeYOLOModel([fake_box(7, 0.9)])
    detector._model = model

    output = detector.detect(np.zeros((10, 10, 3), dtype=np.uint8))

    assert detector.class_map == custom_map
    assert model.predict_kwargs["classes"] == [7]
    assert [item.class_name for item in output] == ["sports ball"]


@pytest.mark.parametrize(
    ("model_profile", "class_ids", "expected_classes", "expected_names"),
    [
        ("coco", [0, 32], [0, 32], ["person", "sports ball"]),
        ("h250", [0, 1], [0, 1], ["sports ball", "person"]),
    ],
)
def test_yolo_profiles_normalize_classes_sent_to_predict(
    model_profile: str,
    class_ids: list[int],
    expected_classes: list[int],
    expected_names: list[str],
):
    detector = UltralyticsYOLODetector(
        "unused.pt", model_profile=model_profile
    )
    model = FakeYOLOModel([fake_box(class_id, 0.9) for class_id in class_ids])
    detector._model = model

    output = detector.detect(np.zeros((10, 10, 3), dtype=np.uint8))

    assert model.predict_kwargs["classes"] == expected_classes
    assert [item.class_name for item in output] == expected_names


def test_yolo_profile_applies_person_and_ball_thresholds():
    detector = UltralyticsYOLODetector(
        "unused.pt",
        model_profile="h250",
        person_threshold=0.45,
        ball_threshold=0.25,
    )
    model = FakeYOLOModel(
        [
            fake_box(0, 0.24),
            fake_box(0, 0.25),
            fake_box(1, 0.44),
            fake_box(1, 0.45),
        ]
    )
    detector._model = model

    output = detector.detect(np.zeros((10, 10, 3), dtype=np.uint8))

    assert model.predict_kwargs["conf"] == 0.25
    assert [(item.class_name, item.confidence) for item in output] == [
        ("sports ball", 0.25),
        ("person", 0.45),
    ]


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


def test_ffmpeg_command_produces_browser_compatible_mp4(tmp_path: Path):
    command = build_audio_remux_command(
        "ffmpeg",
        tmp_path / "annotated_silent.mp4",
        tmp_path / "source.mp4",
        tmp_path / "annotated.mp4",
    )

    assert command[command.index("-c:v") + 1] == "libx264"
    assert command[command.index("-preset") + 1] == "veryfast"
    assert command[command.index("-crf") + 1] == "20"
    assert command[command.index("-pix_fmt") + 1] == "yuv420p"
    assert command[command.index("-tag:v") + 1] == "avc1"
    assert command[command.index("-fps_mode") + 1] == "cfr"
    assert command[command.index("-avoid_negative_ts") + 1] == "make_non_negative"
    assert command[command.index("-c:a") + 1] == "aac"
    assert command[command.index("-movflags") + 1] == "+faststart"
    assert [
        command[index + 1]
        for index, argument in enumerate(command)
        if argument == "-map"
    ] == ["0:v:0", "1:a:0?"]
    assert "-shortest" in command
    assert "copy" not in command


def test_ffmpeg_command_normalizes_silent_output_too(tmp_path: Path):
    command = build_video_normalization_command(
        "ffmpeg",
        tmp_path / "annotated_silent.mp4",
        tmp_path / "annotated.mp4",
        fps=25,
        preserve_audio=False,
    )

    assert command[command.index("-c:v") + 1] == "libx264"
    assert command[command.index("-pix_fmt") + 1] == "yuv420p"
    assert command[command.index("-tag:v") + 1] == "avc1"
    assert command[command.index("-r") + 1] == "25"
    assert command[command.index("-fps_mode") + 1] == "cfr"
    assert command[command.index("-avoid_negative_ts") + 1] == "make_non_negative"
    assert "-an" in command
    assert "-c:a" not in command
    assert command.count("-i") == 1


def test_command_runner_never_uses_a_shell(monkeypatch: pytest.MonkeyPatch):
    completed = Mock()
    monkeypatch.setattr("app.video_analysis.backends.subprocess.run", completed)

    run_command(["ffmpeg", "-version"], timeout=5)

    completed.assert_called_once_with(
        ["ffmpeg", "-version"],
        capture_output=True,
        text=True,
        check=True,
        timeout=5,
        shell=False,
    )
