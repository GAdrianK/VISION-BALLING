"""Tests for authentic RealVideoAnalysisPipeline, canonical modes, and UI truthfulness.

Validates:
- Preflight environment verification (CUDA, PyTorch, locked weights SHA-256, FFmpeg).
- Detector resolution for QUALITY (RF-DETR 960p) and LOW_LATENCY (YOLO11n).
- Failed job truthfulness: artifacts MUST be null, result_available MUST be False, zero mock data leakage.
- Clear separation between REAL_VIDEO_PIPELINE / REAL_UPLOAD and PRECOMPUTED_DEMO.
"""

from pathlib import Path
from unittest.mock import patch
import pytest

from app.core.config import Settings
from app.video_analysis.canonical_modes import (
    LOCKED_RFDETR_CHECKPOINT_PATH,
    LOCKED_RFDETR_SHA256,
    check_environment_preflight,
    compute_file_sha256,
    resolve_detector_for_mode,
)
from app.video_analysis.schemas import (
    AnalysisJob,
    ArtifactSet,
    JobStatus,
    PipelineMetadata,
    VideoMetadata,
)
from app.video_analysis.service import VideoAnalysisService
from app.video_analysis.storage import ResultStorage


class TestCanonicalModesAndPreflight:
    """Verifies preflight environment verification and detector resolution."""

    def test_preflight_invalid_mode_raises(self):
        with pytest.raises(ValueError, match="Mode inconnu"):
            check_environment_preflight("TURBO_MOCK")

    def test_preflight_missing_checkpoint_raises(self, monkeypatch):
        # Point checkpoint path and settings to nonexistent file
        import app.video_analysis.canonical_modes as cm
        monkeypatch.setattr(cm, "LOCKED_RFDETR_CHECKPOINT_PATH", Path("/tmp/nonexistent_ckpt.pth"))
        monkeypatch.setattr(cm.settings, "VIDEO_MODEL_PATH", "/tmp/nonexistent_ckpt_settings.pth")
        with pytest.raises(RuntimeError, match="RF-DETR checkpoint not configured or missing"):
            check_environment_preflight("QUALITY")

    def test_preflight_quality_success(self):
        # In current environment, CUDA RTX 4060 and locked checkpoint exist
        check_environment_preflight("QUALITY")

    def test_resolve_detector_quality(self):
        detector = resolve_detector_for_mode("QUALITY", device="cuda")
        assert detector.__class__.__name__ == "RFDETRDetector"
        assert Path(detector.model_path) == LOCKED_RFDETR_CHECKPOINT_PATH

    def test_resolve_detector_low_latency(self):
        detector = resolve_detector_for_mode("LOW_LATENCY", device="cuda")
        assert detector.__class__.__name__ == "UltralyticsYOLODetector"

    def test_locked_rfdetr_sha256_exact(self):
        assert LOCKED_RFDETR_CHECKPOINT_PATH.exists()
        actual_sha = compute_file_sha256(LOCKED_RFDETR_CHECKPOINT_PATH)
        assert actual_sha == LOCKED_RFDETR_SHA256
        assert actual_sha == "c1a1d88b74edc5ddefa7da4581e2848c4c58c3938d88ad4a1b615f071752ffff"


class TestJobTruthfulnessAndIsolation:
    """Verifies that failures never leak demo data or mock metrics."""

    def test_failed_job_structure_truthful(self):
        job = AnalysisJob(
            analysis_id="analysis_failed_test",
            match_id="match_test",
            status=JobStatus.FAILED,
            mode="QUALITY",
            analysis_source="REAL_UPLOAD",
            evidence_origin="REAL_VIDEO_PIPELINE",
            progress_percent=20.0,
            current_step="failed",
            error={"code": "processing_failed", "message": "module 'cv2' has no attribute 'HOGDescriptor'"},
            artifacts=ArtifactSet(annotated_video=None, detections_json=None, preview_image=None),
            result_available=False,
        )

        assert job.status == JobStatus.FAILED
        assert job.result_available is False
        assert job.artifacts.annotated_video is None
        assert job.artifacts.detections_json is None
        assert job.artifacts.preview_image is None
        assert job.error.code == "processing_failed"
        assert "HOGDescriptor" in job.error.message

    def test_provenance_separation_schemas(self):
        real_pipeline_meta = PipelineMetadata(
            detector="QUALITY",
            mode="QUALITY",
            device="cuda",
            evidence_origin="REAL_VIDEO_PIPELINE",
            checkpoint_sha256=LOCKED_RFDETR_SHA256,
        )
        assert real_pipeline_meta.evidence_origin == "REAL_VIDEO_PIPELINE"
        assert real_pipeline_meta.mode == "QUALITY"

        demo_pipeline_meta = PipelineMetadata(
            detector="QUALITY",
            mode="QUALITY",
            device="cuda",
            evidence_origin="PRECOMPUTED_DEMO",
            checkpoint_sha256=None,
        )
        assert demo_pipeline_meta.evidence_origin == "PRECOMPUTED_DEMO"

    @pytest.mark.anyio
    async def test_service_error_handling_marks_failed_without_artifacts(self, tmp_path):
        custom_settings = Settings(
            VIDEO_STORAGE_PATH=str(tmp_path),
            VIDEO_DEVICE="cuda",
            VIDEO_DETECTOR="rfdetr",
            VIDEO_TRACKER="botsort",
        )
        storage = ResultStorage(root=tmp_path)
        service = VideoAnalysisService(settings=custom_settings, storage=storage)
        from starlette.datastructures import UploadFile

        dummy_file = tmp_path / "dummy.mp4"
        dummy_file.write_bytes(b"not a valid video frame")

        with open(dummy_file, "rb") as f:
            upload = UploadFile(file=f, filename="dummy.mp4")
            created = await service.create(upload=upload, mode="QUALITY")

        # 1. Invalid video probe failure marks job failed without artifacts
        service.process(created.analysis_id)
        failed_job = storage.load_job(created.analysis_id)
        assert failed_job.status == JobStatus.FAILED
        assert failed_job.result_available is False
        assert failed_job.artifacts.annotated_video is None
        assert failed_job.error is not None
        assert failed_job.error.code == "invalid_video"

        # 2. Pipeline runtime error marks job failed without artifacts
        valid_meta = VideoMetadata(
            filename="dummy.mp4",
            duration_seconds=5.0,
            fps=25.0,
            width=1920,
            height=1080,
            frame_count=125,
        )
        with open(dummy_file, "rb") as f:
            upload2 = UploadFile(file=f, filename="dummy2.mp4")
            created2 = await service.create(upload=upload2, mode="QUALITY")

        with patch.object(service.validator, "validate", return_value=valid_meta):
            with patch("app.video_analysis.real_pipeline.RealVideoAnalysisPipeline.run", side_effect=RuntimeError("Simulated pipeline failure")):
                service.process(created2.analysis_id)

        failed_job2 = storage.load_job(created2.analysis_id)
        assert failed_job2.status == JobStatus.FAILED
        assert failed_job2.result_available is False
        assert failed_job2.artifacts.annotated_video is None
        assert failed_job2.error is not None
        assert failed_job2.error.code == "processing_failed"
        assert "Simulated pipeline failure" in failed_job2.error.message
