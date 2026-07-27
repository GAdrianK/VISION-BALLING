from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import cv2

from app.video_analysis.schemas import VideoMetadata


class VideoValidationError(ValueError):
    pass


class VideoValidator:
    def __init__(
        self,
        allowed_extensions: set[str],
        max_size_bytes: int,
        max_duration_seconds: float,
        min_width: int,
        min_height: int,
        minimum_free_bytes: int,
    ) -> None:
        self.allowed_extensions = {ext.lower().lstrip(".") for ext in allowed_extensions}
        self.max_size_bytes = max_size_bytes
        self.max_duration_seconds = max_duration_seconds
        self.min_width = min_width
        self.min_height = min_height
        self.minimum_free_bytes = minimum_free_bytes

    def validate(self, path: Path, original_filename: str) -> VideoMetadata:
        extension = path.suffix.lower().lstrip(".")
        if extension not in self.allowed_extensions:
            raise VideoValidationError(
                f"Format .{extension or 'inconnu'} non autorisé. "
                f"Formats acceptés : {', '.join(sorted(self.allowed_extensions))}."
            )
        if not path.is_file() or path.stat().st_size == 0:
            raise VideoValidationError("Le fichier vidéo est vide ou introuvable.")
        if path.stat().st_size > self.max_size_bytes:
            raise VideoValidationError("La vidéo dépasse la taille maximale configurée.")
        free_bytes = shutil.disk_usage(path.parent).free
        if free_bytes < self.minimum_free_bytes:
            raise VideoValidationError("Espace disque insuffisant pour traiter la vidéo.")

        metadata = self._probe(path, original_filename)
        if metadata.duration_seconds > self.max_duration_seconds:
            raise VideoValidationError(
                f"Durée {metadata.duration_seconds:.1f}s supérieure à la limite "
                f"de développement ({self.max_duration_seconds:.0f}s)."
            )
        if metadata.width < self.min_width or metadata.height < self.min_height:
            raise VideoValidationError(
                f"Résolution {metadata.width}x{metadata.height} trop faible ; minimum "
                f"{self.min_width}x{self.min_height}."
            )
        return metadata

    def _probe(self, path: Path, filename: str) -> VideoMetadata:
        if shutil.which("ffprobe"):
            try:
                return self._probe_ffmpeg(path, filename)
            except (OSError, subprocess.SubprocessError, ValueError, KeyError, json.JSONDecodeError):
                pass
        return self._probe_opencv(path, filename)

    @staticmethod
    def _probe_ffmpeg(path: Path, filename: str) -> VideoMetadata:
        completed = subprocess.run(
            [
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries",
                "stream=codec_name,width,height,avg_frame_rate,nb_frames:format=duration,format_name",
                "-of", "json", str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        payload = json.loads(completed.stdout)
        streams = payload.get("streams", [])
        if not streams:
            raise VideoValidationError("Aucun flux vidéo détecté.")
        stream = streams[0]
        numerator, denominator = stream["avg_frame_rate"].split("/")
        fps = float(numerator) / float(denominator)
        duration = float(payload["format"]["duration"])
        frame_count = int(stream.get("nb_frames") or round(duration * fps))
        return VideoMetadata(
            filename=filename,
            duration_seconds=duration,
            fps=fps,
            width=int(stream["width"]),
            height=int(stream["height"]),
            frame_count=frame_count,
            container=payload["format"].get("format_name"),
            codec=stream.get("codec_name"),
        )

    @staticmethod
    def _probe_opencv(path: Path, filename: str) -> VideoMetadata:
        capture = cv2.VideoCapture(str(path))
        try:
            if not capture.isOpened():
                raise VideoValidationError("La vidéo est illisible ou ne contient aucun flux vidéo.")
            fps = float(capture.get(cv2.CAP_PROP_FPS))
            width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
            ok, _ = capture.read()
            if not ok or fps <= 0 or width <= 0 or height <= 0 or frame_count <= 0:
                raise VideoValidationError("Métadonnées vidéo invalides ou première frame illisible.")
            return VideoMetadata(
                filename=filename,
                duration_seconds=frame_count / fps,
                fps=fps,
                width=width,
                height=height,
                frame_count=frame_count,
                container=path.suffix.lower().lstrip("."),
            )
        finally:
            capture.release()

