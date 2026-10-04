from __future__ import annotations

import hashlib
import logging
import re
import secrets
import shutil
import threading
from pathlib import Path
from uuid import uuid4

from fastapi import UploadFile

from app.core.config import Settings
from app.video_analysis.backends import diagnose_video_backend
from app.video_analysis.canonical_modes import (
    LOCKED_RFDETR_SHA256,
    check_environment_preflight,
)
from app.video_analysis.detectors import ObjectDetector, create_detector
from app.video_analysis.pipeline import VideoPipeline
from app.video_analysis.real_pipeline import RealVideoAnalysisPipeline
from app.video_analysis.reproducibility import (
    build_analysis_key,
    build_canonical_config,
    resolve_git_sha,
    resolve_model_identity,
    resolve_tracker_identity,
)
from app.video_analysis.schemas import (
    AnalysisCreated,
    AnalysisJob,
    ArtifactSet,
    JobError,
    JobStatus,
    PIPELINE_VERSION,
    PipelineMetadata,
)
from app.video_analysis.storage import ResultStorage
from app.video_analysis.trackers import (
    BallTracker,
    Tracker,
    create_tracker,
    resolve_ball_tracker_timing,
)
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
        self._model_checksum_cache: dict[tuple[str, int, int], str] = {}
        self._explicit_detector = detector is not None
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
        self._tracker_metadata = tracker.metadata() if tracker is not None else None
        self.validator = VideoValidator(
            allowed_extensions=set(settings.video_extensions),
            max_size_bytes=settings.VIDEO_MAX_SIZE_MB * 1024 * 1024,
            max_duration_seconds=settings.VIDEO_MAX_DURATION_SECONDS,
            min_width=settings.VIDEO_MIN_WIDTH,
            min_height=settings.VIDEO_MIN_HEIGHT,
            minimum_free_bytes=settings.VIDEO_MIN_FREE_DISK_MB * 1024 * 1024,
        )
        self._active_analyses: set[str] = set()
        self._active_lock = threading.Lock()

    async def create(
        self, upload: UploadFile, match_id: str | None = None, mode: str = "QUALITY"
    ) -> AnalysisCreated:
        if self.settings.APP_ENV == "production" and not self.settings.PUBLIC_UPLOAD_ENABLED:
            raise VideoValidationError(
                "Public video uploads are disabled on this production deployment."
            )

        with self._active_lock:
            if len(self._active_analyses) >= self.settings.MAX_CONCURRENT_ANALYSES:
                raise VideoValidationError(
                    f"Le serveur traite actuellement le nombre maximal d'analyses simultanées "
                    f"({self.settings.MAX_CONCURRENT_ANALYSES}). Veuillez patienter avant de soumettre une nouvelle vidéo."
                )

        mode_upper = mode.strip().upper()
        if mode_upper not in ("QUALITY", "LOW_LATENCY"):
            raise VideoValidationError(
                f"Mode inconnu '{mode}'. Modes autorisés : 'QUALITY', 'LOW_LATENCY'."
            )

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
        pipeline_metadata = self._build_pipeline_metadata(sha256, mode=mode_upper)
        analysis_key = pipeline_metadata.analysis_key
        assert analysis_key is not None

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

        completed = self.storage.find_completed_by_analysis_key(analysis_key)
        if completed:
            temporary.unlink(missing_ok=True)
            if completed.access_token_hash and completed.access_token_hash not in completed.access_token_hashes:
                completed.access_token_hashes.append(completed.access_token_hash)
            if token_hash not in completed.access_token_hashes:
                completed.access_token_hashes.append(token_hash)
            if not completed.access_token_hash:
                completed.access_token_hash = token_hash
            self.storage.save_job(completed)
            return AnalysisCreated(
                analysis_id=completed.analysis_id,
                match_id=completed.match_id,
                status=completed.status,
                reused=True,
                access_token=raw_token,
            )

        analysis_id = f"analysis_{uuid4().hex}"
        resolved_match_id = match_id or f"match_{uuid4().hex[:12]}"
        directory = self.storage.analysis_dir(analysis_id)
        job = AnalysisJob(
            analysis_id=analysis_id,
            match_id=resolved_match_id,
            mode=mode_upper,
            analysis_source="REAL_UPLOAD",
            evidence_origin="REAL_VIDEO_PIPELINE",
            source_sha256=sha256,
            analysis_key=analysis_key,
            pipeline=pipeline_metadata,
            access_token_hash=token_hash,
            access_token_hashes=[token_hash],
        )
        self.storage.create_job(job)
        source = directory / f"source.{extension}"
        shutil.move(str(temporary), source)
        logger.info(
            "video_job_created analysis_id=%s mode=%s filename=%s",
            analysis_id,
            mode_upper,
            filename,
        )
        (directory / "original_filename.txt").write_text(filename, encoding="utf-8")
        return AnalysisCreated(
            analysis_id=analysis_id,
            match_id=resolved_match_id,
            status=job.status,
            access_token=raw_token,
        )

    def process(self, analysis_id: str) -> None:
        with self._active_lock:
            self._active_analyses.add(analysis_id)
        try:
            self._process_internal(analysis_id)
        finally:
            with self._active_lock:
                self._active_analyses.discard(analysis_id)

    def _process_internal(self, analysis_id: str) -> None:
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

            def progress(percent: float, step: str) -> None:
                self._update(job, JobStatus.PROCESSING, percent, step)

            if self._explicit_detector:
                ball_tracker_timing = resolve_ball_tracker_timing(
                    max_missing_seconds=self.settings.VIDEO_BALL_TRACK_MAX_MISSING_SECONDS,
                    trajectory_seconds=self.settings.VIDEO_BALL_TRAJECTORY_SECONDS,
                    source_fps=metadata.fps,
                )
                self._update(job, JobStatus.PROCESSING, 20, "loading_detector")
                pipeline = VideoPipeline(
                    detector=self.detector,
                    tracker=self.tracker_factory(),
                    ball_tracker=BallTracker(
                        max_missing_frames=(
                            ball_tracker_timing.max_missing_frames_effective
                        ),
                        max_distance_ratio=(
                            self.settings.VIDEO_BALL_TRACK_MAX_DISTANCE_RATIO
                        ),
                        trajectory_length=(
                            ball_tracker_timing.trajectory_frames_effective
                        ),
                    ),
                    ball_tracker_timing=ball_tracker_timing,
                    frame_sample_rate=self.settings.VIDEO_FRAME_SAMPLE_RATE,
                    keep_extracted_frames=self.settings.VIDEO_KEEP_TEMPORARY_FILES,
                    preserve_audio=self.settings.VIDEO_PRESERVE_AUDIO,
                    max_processing_seconds=self.settings.VIDEO_MAX_PROCESSING_SECONDS,
                )
                result = pipeline.run(
                    analysis_id=analysis_id,
                    match_id=job.match_id,
                    source=source,
                    output_dir=directory,
                    metadata=metadata,
                    progress=progress,
                    pipeline_metadata=(
                        job.pipeline
                        or self._build_pipeline_metadata(job.source_sha256 or "unknown")
                    ),
                )
            else:
                self._update(job, JobStatus.PROCESSING, 15, "initializing_real_pipeline")
                mode = job.mode or (job.pipeline.mode if job.pipeline else "QUALITY")
                real_pipeline = RealVideoAnalysisPipeline(mode=mode, settings=self.settings)

                result = real_pipeline.run(
                    analysis_id=analysis_id,
                    match_id=job.match_id,
                    source=source,
                    output_dir=directory,
                    metadata=metadata,
                    progress=progress,
                    pipeline_metadata=job.pipeline,
                )
            self.storage.save_result(result)
            job.status = JobStatus.COMPLETED
            job.progress_percent = 100
            job.current_step = "completed"
            job.artifacts = result.artifacts
            job.warnings = result.warnings
            job.result_available = True
            job.pipeline = result.pipeline
            job.analysis_key = result.pipeline.analysis_key
            self.storage.save_job(job)
            if not self.settings.VIDEO_RETAIN_SOURCE:
                source.unlink(missing_ok=True)
            logger.info("video_job_completed analysis_id=%s", analysis_id)
        except VideoValidationError as exc:
            source.unlink(missing_ok=True)
            self._fail(job, "invalid_video", str(exc))
        except Exception as exc:
            if not self.settings.VIDEO_RETAIN_SOURCE:
                source.unlink(missing_ok=True)
            logger.exception("video_job_failed analysis_id=%s", analysis_id)
            self._fail(job, "processing_failed", str(exc))
        finally:
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass

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
        job.artifacts = ArtifactSet(annotated_video=None, detections_json=None, preview_image=None)
        job.result_available = False
        self.storage.save_job(job)
        logger.error(
            "video_job_failed analysis_id=%s code=%s message=%s",
            job.analysis_id,
            code,
            message,
        )

    def _build_pipeline_metadata(
        self, source_sha256: str, mode: str = "QUALITY"
    ) -> PipelineMetadata:
        detector_metadata = self.detector.metadata()
        model = resolve_model_identity(
            self.settings,
            detector_metadata,
            backend_root=Path(__file__).resolve().parents[2],
            checksum_cache=self._model_checksum_cache,
        )
        tracker_name, tracker_version = resolve_tracker_identity(
            self.settings, self._tracker_metadata
        )
        backend = diagnose_video_backend()
        canonical_config = build_canonical_config(
            self.settings,
            model,
            tracker_name=tracker_name,
            tracker_version=tracker_version,
            video_backend=backend.video_backend,
            ffmpeg_version=backend.ffmpeg_version,
        )
        analysis_key = build_analysis_key(
            source_sha256,
            model.model_checksum,
            canonical_config,
        )
        checkpoint_sha = (
            LOCKED_RFDETR_SHA256 if mode == "QUALITY" else model.model_checksum
        )
        return PipelineMetadata(
            version=PIPELINE_VERSION,
            pipeline_version=PIPELINE_VERSION,
            detector=model.model_id,
            detector_name=model.detector_name,
            detector_version=model.detector_version,
            mode=mode,
            evidence_origin="REAL_VIDEO_PIPELINE",
            checkpoint_sha256=checkpoint_sha,
            frame_sample_rate=self.settings.VIDEO_FRAME_SAMPLE_RATE,
            device=str(detector_metadata.get("device") or self.settings.VIDEO_DEVICE),
            tracker_name=tracker_name,
            tracker_version=tracker_version,
            tracking_enabled=tracker_name != "none",
            ffmpeg_version=backend.ffmpeg_version,
            video_backend=backend.video_backend,
            source_sha256=source_sha256,
            analysis_key=analysis_key,
            git_sha=resolve_git_sha(self.settings.VIDEO_GIT_SHA),
            model_id=model.model_id,
            model_checksum=model.model_checksum,
            thresholds=canonical_config["thresholds"],
            ball_track_max_missing_seconds=(
                self.settings.VIDEO_BALL_TRACK_MAX_MISSING_SECONDS
            ),
            ball_trajectory_seconds=self.settings.VIDEO_BALL_TRAJECTORY_SECONDS,
            canonical_config=canonical_config,
        )

    @staticmethod
    def _safe_filename(filename: str) -> str:
        basename = Path(filename).name
        return re.sub(r"[^A-Za-z0-9._-]", "_", basename)
