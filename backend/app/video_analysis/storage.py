from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.video_analysis.schemas import AnalysisJob, AnalysisResult, JobStatus


class ResultStorage:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def analysis_dir(self, analysis_id: str) -> Path:
        if (
            not analysis_id.startswith("analysis_")
            or "/" in analysis_id
            or ".." in analysis_id
        ):
            raise ValueError("Identifiant d'analyse invalide.")
        return self.root / analysis_id

    def create_job(self, job: AnalysisJob) -> None:
        directory = self.analysis_dir(job.analysis_id)
        directory.mkdir(parents=True, exist_ok=False)
        self.save_job(job)

    def save_job(self, job: AnalysisJob) -> None:
        with self._lock:
            job.updated_at = datetime.now(timezone.utc)
            self._atomic_json(
                self.analysis_dir(job.analysis_id) / "job.json",
                job.model_dump(mode="json"),
            )

    def load_job(self, analysis_id: str) -> AnalysisJob | None:
        path = self.analysis_dir(analysis_id) / "job.json"
        if not path.exists():
            return None
        with self._lock:
            return AnalysisJob.model_validate_json(path.read_text(encoding="utf-8"))

    def save_result(self, result: AnalysisResult) -> Path:
        path = self.analysis_dir(result.analysis_id) / "detections.json"
        with self._lock:
            self._atomic_json(path, result.model_dump(mode="json"))
        return path

    def load_result(self, analysis_id: str) -> AnalysisResult | None:
        path = self.analysis_dir(analysis_id) / "detections.json"
        if not path.exists():
            return None
        return AnalysisResult.model_validate_json(path.read_text(encoding="utf-8"))

    def find_completed_by_sha(self, sha256: str) -> AnalysisJob | None:
        for job_path in self.root.glob("analysis_*/job.json"):
            try:
                job = AnalysisJob.model_validate_json(
                    job_path.read_text(encoding="utf-8")
                )
            except (OSError, ValueError):
                continue
            if job.source_sha256 == sha256 and job.status == JobStatus.COMPLETED:
                return job
        return None

    @staticmethod
    def _atomic_json(path: Path, payload: dict) -> None:
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)
