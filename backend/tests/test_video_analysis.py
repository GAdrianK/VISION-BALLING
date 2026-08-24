from __future__ import annotations

import asyncio
from pathlib import Path

import cv2
import numpy as np
import pytest
from app.api.video_analysis import get_video_analysis_service
from app.core.config import Settings
from app.main import app
from app.video_analysis.detectors import ObjectDetector, RawDetection
from app.video_analysis.schemas import JobStatus
from app.video_analysis.service import VideoAnalysisService
from app.video_analysis.validation import VideoValidationError, VideoValidator
from fastapi.testclient import TestClient
from starlette.datastructures import UploadFile


class FakeDetector(ObjectDetector):
    def load(self) -> None:
        pass

    def detect(self, frame: np.ndarray) -> list[RawDetection]:
        return [
            RawDetection("person", "unknown_player", 0.9, (10, 20, 60, 150))
        ]

    def metadata(self) -> dict:
        return {
            "model_id": "fake-detector-v1",
            "provider": "tests",
            "device": "cpu",
            "classes": ["person"],
            "football_specific": False,
            "ball_detection": False,
        }


def make_video(path: Path, frames: int = 10, fps: float = 10) -> Path:
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"MJPG"), fps, (320, 240)
    )
    if not writer.isOpened():
        pytest.skip("Le codec MJPG OpenCV n'est pas disponible.")
    for index in range(frames):
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        cv2.circle(frame, (30 + index * 3, 100), 8, (255, 255, 255), -1)
        writer.write(frame)
    writer.release()
    return path


@pytest.fixture()
def sample_video(tmp_path: Path) -> Path:
    return make_video(tmp_path / "sample.avi")


@pytest.fixture()
def video_settings(tmp_path: Path) -> Settings:
    return Settings(
        VIDEO_UPLOAD_DIR=str(tmp_path / "uploads"),
        VIDEO_RESULT_DIR=str(tmp_path / "results"),
        VIDEO_ALLOWED_EXTENSIONS="avi,mp4",
        VIDEO_MAX_SIZE_MB=10,
        VIDEO_MAX_DURATION_SECONDS=10,
        VIDEO_MIN_WIDTH=320,
        VIDEO_MIN_HEIGHT=240,
        VIDEO_MIN_FREE_DISK_MB=0,
        VIDEO_FRAME_INTERVAL=2,
        VIDEO_KEEP_TEMPORARY_FILES=True,
    )


def make_validator() -> VideoValidator:
    return VideoValidator(
        {"avi", "mp4"}, 10 * 1024 * 1024, 10, 320, 240, 0
    )


def upload(service: VideoAnalysisService, sample_video: Path):
    async def create():
        with sample_video.open("rb") as source:
            return await service.create(UploadFile(source, filename="sample.avi"))

    return asyncio.run(create())


def test_valid_video_and_metadata_extraction(sample_video: Path):
    metadata = make_validator().validate(sample_video, "sample.avi")
    assert (metadata.width, metadata.height) == (320, 240)
    assert metadata.fps == pytest.approx(10, rel=0.1)
    assert metadata.frame_count == 10
    assert metadata.duration_seconds == pytest.approx(1, rel=0.1)


def test_invalid_format_is_rejected(tmp_path: Path):
    invalid = tmp_path / "notes.txt"
    invalid.write_text("not a video", encoding="utf-8")
    with pytest.raises(VideoValidationError, match="non autorisé"):
        make_validator().validate(invalid, "notes.txt")


def test_job_creation_status_progress_and_fake_detector(
    sample_video: Path, video_settings: Settings
):
    service = VideoAnalysisService(video_settings, detector=FakeDetector())
    created = upload(service, sample_video)
    queued = service.storage.load_job(created.analysis_id)
    assert queued and queued.status == JobStatus.QUEUED

    service.process(created.analysis_id)
    completed = service.storage.load_job(created.analysis_id)
    assert completed and completed.status == JobStatus.COMPLETED
    assert completed.progress_percent == 100
    result = service.storage.load_result(created.analysis_id)
    assert result and result.frames_analyzed == 5 and result.detections
    assert all(item.model_id == "fake-detector-v1" for item in result.detections)
    assert (service.storage.analysis_dir(created.analysis_id) / "annotated.mp4").is_file()


def test_service_propagates_video_model_profile(
    video_settings: Settings, monkeypatch: pytest.MonkeyPatch
):
    captured = {}
    fake_detector = FakeDetector()

    def fake_create_detector(name: str, **kwargs):
        captured["name"] = name
        captured.update(kwargs)
        return fake_detector

    video_settings.VIDEO_DETECTOR = "yolo"
    video_settings.VIDEO_MODEL_PROFILE = "h250"
    monkeypatch.setattr(
        "app.video_analysis.service.create_detector", fake_create_detector
    )

    service = VideoAnalysisService(video_settings)

    assert service.detector is fake_detector
    assert captured == {
        "name": "yolo",
        "model_path": video_settings.VIDEO_MODEL_PATH,
        "model_profile": "h250",
        "device": video_settings.VIDEO_DEVICE,
        "confidence_threshold": video_settings.VIDEO_CONFIDENCE_THRESHOLD,
        "person_threshold": video_settings.VIDEO_PERSON_CONFIDENCE_THRESHOLD,
        "ball_threshold": video_settings.VIDEO_BALL_CONFIDENCE_THRESHOLD,
    }


def test_processing_error_sets_failed_status(sample_video: Path, video_settings: Settings):
    class BrokenDetector(FakeDetector):
        def load(self) -> None:
            raise RuntimeError("model unavailable")

    service = VideoAnalysisService(video_settings, detector=BrokenDetector())
    created = upload(service, sample_video)
    service.process(created.analysis_id)
    failed = service.storage.load_job(created.analysis_id)
    assert failed and failed.status == JobStatus.FAILED
    assert failed.error and failed.error.code == "processing_failed"


def test_create_and_get_endpoints(sample_video: Path, video_settings: Settings):
    service = VideoAnalysisService(video_settings, detector=FakeDetector())
    app.dependency_overrides[get_video_analysis_service] = lambda: service
    try:
        with TestClient(app) as api:
            with sample_video.open("rb") as source:
                response = api.post(
                    "/api/video-analysis",
                    files={"video": ("sample.avi", source, "video/x-msvideo")},
                    data={"match_id": "match_integration"},
                )
            assert response.status_code == 202
            analysis_id = response.json()["analysis_id"]
            status = api.get(f"/api/video-analysis/{analysis_id}")
            assert status.status_code == 200
            assert status.json()["status"] == "completed"
            detections = api.get(f"/api/video-analysis/{analysis_id}/detections")
            assert detections.status_code == 200
            assert detections.json()["detections"]
            artifacts = api.get(f"/api/video-analysis/{analysis_id}/artifacts")
            assert artifacts.status_code == 200
            assert len(artifacts.json()["artifacts"]) >= 2
    finally:
        app.dependency_overrides.clear()


def test_create_endpoint_rejects_invalid_extension(video_settings: Settings):
    service = VideoAnalysisService(video_settings, detector=FakeDetector())
    app.dependency_overrides[get_video_analysis_service] = lambda: service
    try:
        with TestClient(app) as api:
            response = api.post(
                "/api/video-analysis",
                files={"video": ("payload.txt", b"not-video", "text/plain")},
            )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
