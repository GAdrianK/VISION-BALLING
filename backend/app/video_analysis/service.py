from __future__ import annotations

import hashlib
import logging
import re
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import Settings
from app.video_analysis.detectors import ObjectDetector, create_detector
from app.video_analysis.pipeline import VideoPipeline
from app.video_analysis.schemas import (
    AnalysisCreated,
    AnalysisJob,
    JobError,
    JobStatus,
)
from app.video_analysis.storage import ResultStorage
from app.video_analysis.trackers import Tracker, create_tracker
from app.video_analysis.validation import VideoValidationError, VideoValidator

logger = logging.getLogger("football.video_analysis")


class VideoAnalysisService:
    def __init__(
        self,
        settings: Settings,
        storage: ResultStorage | None = None,
        detector: ObjectDetector | None = None,
        tracker: Tracker | None = None,
    ) -> None:
        self.settings = settings
        self.upload_root = Path(settings.get_video_upload_dir())
        self.result_root = Path(settings.get_video_result_dir())
        self.upload_root.mkdir(parents=True, exist_ok=True)
        self.result_root.mkdir(parents=True, exist_ok=True)
        self.storage = storage or ResultStorage(self.result_root)
        self.detector = detector or create_detector(
            settings.VIDEO_DETECTOR,
            model_path=settings.VIDEO_MODEL_PATH,
            model_profile=settings.VIDEO_MODEL_PROFILE,
            device=settings.VIDEO_DEVICE,
            confidence_threshold=settings.VIDEO_CONFIDENCE_THRESHOLD,
            person_threshold=settings.VIDEO_PERSON_CONFIDENCE_THRESHOLD,
            ball_threshold=settings.VIDEO_BALL_CONFIDENCE_THRESHOLD,
        )
        self.tracker_factory = (
            (lambda: tracker)
            if tracker is not None
            else lambda: create_tracker(
                settings.VIDEO_TRACKING_ENABLED, settings.VIDEO_TRACKER
            )
        )
        self.validator = VideoValidator(
            allowed_extensions=set(settings.video_extensions),
            max_size_bytes=settings.VIDEO_MAX_SIZE_MB * 1024 * 1024,
            max_duration_seconds=settings.VIDEO_MAX_DURATION_SECONDS,
            min_width=settings.VIDEO_MIN_WIDTH,
            min_height=settings.VIDEO_MIN_HEIGHT,
            minimum_free_bytes=settings.VIDEO_MIN_FREE_DISK_MB * 1024 * 1024,
        )

    async def create(
        self, upload: UploadFile, match_id: str | None = None
    ) -> AnalysisCreated:
        filename = self._safe_filename(upload.filename or "video")
        extension = Path(filename).suffix.lower().lstrip(".")
        if extension not in self.settings.video_extensions:
            raise VideoValidationError(
                f"Format .{extension or 'inconnu'} non autorisé. "
                f"Formats acceptés : {', '.join(self.settings.video_extensions)}."
            )

        temporary = self.upload_root / f".upload_{uuid4().hex}.part"
        digest = hashlib.sha256()
        total = 0
        try:
            with temporary.open("wb") as destination:
                while chunk := await upload.read(1024 * 1024):
                    total += len(chunk)
                    if total > self.settings.VIDEO_MAX_SIZE_MB * 1024 * 1024:
                        raise VideoValidationError(
                            "La vidéo dépasse la taille maximale configurée."
                        )
                    digest.update(chunk)
                    destination.write(chunk)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise
        finally:
            await upload.close()

        sha256 = digest.hexdigest()
        completed = self.storage.find_completed_by_sha(sha256)
        if completed:
            temporary.unlink(missing_ok=True)
            return AnalysisCreated(
                analysis_id=completed.analysis_id,
                match_id=completed.match_id,
                status=completed.status,
                reused=True,
            )

        analysis_id = f"analysis_{uuid4().hex}"
        resolved_match_id = match_id or f"match_{uuid4().hex[:12]}"
        directory = self.storage.analysis_dir(analysis_id)
        job = AnalysisJob(
            analysis_id=analysis_id,
            match_id=resolved_match_id,
            source_sha256=sha256,
        )
        self.storage.create_job(job)
        source = directory / f"source.{extension}"
        shutil.move(str(temporary), source)
        logger.info(
            "video_job_created analysis_id=%s filename=%s", analysis_id, filename
        )
        (directory / "original_filename.txt").write_text(filename, encoding="utf-8")
        return AnalysisCreated(
            analysis_id=analysis_id,
            match_id=resolved_match_id,
            status=job.status,
        )

    def process(self, analysis_id: str) -> None:
        job = self.storage.load_job(analysis_id)
        if job is None or job.status == JobStatus.COMPLETED:
            return
        directory = self.storage.analysis_dir(analysis_id)
        source = next(directory.glob("source.*"), None)
        if source is None:
            self._fail(job, "source_missing", "Fichier source introuvable.")
            return
        original_filename = (directory / "original_filename.txt").read_text(
            encoding="utf-8"
        )
        try:
            self._update(job, JobStatus.VALIDATING, 5, "validating_video")
            logger.info("video_validation_started analysis_id=%s", analysis_id)
            metadata = self.validator.validate(source, original_filename)
            self._update(job, JobStatus.PROCESSING, 20, "loading_detector")
            pipeline = VideoPipeline(
                detector=self.detector,
                tracker=self.tracker_factory(),
                frame_interval=self.settings.video_frame_sample_rate,
                keep_extracted_frames=self.settings.VIDEO_KEEP_TEMPORARY_FILES,
                preserve_audio=self.settings.VIDEO_PRESERVE_AUDIO,
                max_processing_seconds=self.settings.VIDEO_MAX_PROCESSING_SECONDS,
            )

            def progress(percent: float, step: str) -> None:
                self._update(job, JobStatus.PROCESSING, percent, step)

            result = pipeline.run(
                analysis_id=analysis_id,
                match_id=job.match_id,
                source=source,
                output_dir=directory,
                metadata=metadata,
                progress=progress,
            )
            self.storage.save_result(result)
            job.status = JobStatus.COMPLETED
            job.progress_percent = 100
            job.current_step = "completed"
            job.artifacts = result.artifacts
            job.warnings = result.warnings
            job.result_available = True
            self.storage.save_job(job)
            if not self.settings.VIDEO_KEEP_TEMPORARY_FILES:
                source.unlink(missing_ok=True)
            logger.info("video_job_completed analysis_id=%s", analysis_id)
        except VideoValidationError as exc:
            self._fail(job, "invalid_video", str(exc))
        except Exception as exc:
            logger.exception("video_job_failed analysis_id=%s", analysis_id)
            self._fail(job, "processing_failed", str(exc))

    def _update(
        self, job: AnalysisJob, status: JobStatus, percent: float, current_step: str
    ) -> None:
        job.status = status
        job.progress_percent = round(min(max(percent, 0), 100), 2)
        job.current_step = current_step
        self.storage.save_job(job)

    def _fail(self, job: AnalysisJob, code: str, message: str) -> None:
        job.status = JobStatus.FAILED
        job.current_step = "failed"
        job.error = JobError(code=code, message=message)
        self.storage.save_job(job)
        logger.error(
            "video_job_failed analysis_id=%s code=%s message=%s",
            job.analysis_id,
            code,
            message,
        )

    @staticmethod
    def _safe_filename(filename: str) -> str:
        basename = Path(filename).name
        return re.sub(r"[^A-Za-z0-9._-]", "_", basename)
