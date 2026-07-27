from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path

import cv2

from app.video_analysis.detectors import ObjectDetector
from app.video_analysis.schemas import (
    AnalysisResult,
    ArtifactSet,
    BoundingBox,
    Detection,
    JobStatus,
    PipelineMetadata,
    VideoMetadata,
)

logger = logging.getLogger("football.video_analysis")
ProgressCallback = Callable[[float, str], None]


class VideoPipeline:
    def __init__(
        self,
        detector: ObjectDetector,
        frame_interval: int,
        keep_extracted_frames: bool = False,
    ) -> None:
        self.detector = detector
        self.frame_interval = max(1, frame_interval)
        self.keep_extracted_frames = keep_extracted_frames

    def run(
        self,
        analysis_id: str,
        match_id: str,
        source: Path,
        output_dir: Path,
        metadata: VideoMetadata,
        progress: ProgressCallback,
    ) -> AnalysisResult:
        started_at = time.monotonic()
        self.detector.load()
        detector_metadata = self.detector.metadata()
        logger.info(
            "video_processing_started analysis_id=%s model=%s",
            analysis_id,
            detector_metadata["model_id"],
        )

        capture = cv2.VideoCapture(str(source))
        if not capture.isOpened():
            raise RuntimeError("Impossible d'ouvrir la vidéo après validation.")

        annotated_path = output_dir / "annotated.mp4"
        preview_path = output_dir / "preview.jpg"
        frames_dir = output_dir / "frames"
        if self.keep_extracted_frames:
            frames_dir.mkdir(exist_ok=True)

        writer = cv2.VideoWriter(
            str(annotated_path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            metadata.fps,
            (metadata.width, metadata.height),
        )
        if not writer.isOpened():
            capture.release()
            raise RuntimeError(
                "Impossible de créer la vidéo annotée. Vérifiez les codecs OpenCV/FFmpeg."
            )

        detections: list[Detection] = []
        frames_analyzed = 0
        preview_written = False
        frame_index = 0
        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break

                if frame_index % self.frame_interval == 0:
                    raw_detections = self.detector.detect(frame)
                    frames_analyzed += 1
                    for raw in raw_detections:
                        x1, y1, x2, y2 = raw.bbox
                        detection = Detection(
                            frame_index=frame_index,
                            timestamp_seconds=round(frame_index / metadata.fps, 6),
                            class_name=raw.class_name,
                            football_role=raw.football_role,
                            confidence=round(raw.confidence, 6),
                            bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
                            model_id=detector_metadata["model_id"],
                        )
                        detections.append(detection)
                        self._annotate(frame, detection)

                    if self.keep_extracted_frames:
                        cv2.imwrite(str(frames_dir / f"frame_{frame_index:08d}.jpg"), frame)
                    if not preview_written:
                        preview_written = cv2.imwrite(str(preview_path), frame)

                writer.write(frame)
                frame_index += 1
                if frame_index % max(1, int(metadata.fps * 2)) == 0:
                    ratio = min(frame_index / metadata.frame_count, 1)
                    progress(20 + ratio * 75, "detecting_objects")
        finally:
            capture.release()
            writer.release()

        if frame_index == 0:
            raise RuntimeError("Aucune frame n'a pu être traitée.")

        warnings = [
            "Baseline générique OpenCV HOG : les personnes détectées ne sont pas "
            "nécessairement des joueurs."
        ]
        if not detector_metadata.get("ball_detection"):
            warnings.append(
                "Ce détecteur ne prend pas en charge le ballon ; aucune position de ballon "
                "n'est inférée."
            )
        if not preview_written:
            warnings.append("La génération de l'image de prévisualisation a échoué.")

        duration = time.monotonic() - started_at
        logger.info(
            "video_processing_completed analysis_id=%s frames=%s detections=%s duration=%.3f",
            analysis_id,
            frames_analyzed,
            len(detections),
            duration,
        )
        return AnalysisResult(
            analysis_id=analysis_id,
            match_id=match_id,
            status=JobStatus.COMPLETED,
            video=metadata,
            pipeline=PipelineMetadata(
                detector=detector_metadata["model_id"],
                frame_interval=self.frame_interval,
                device=detector_metadata.get("device", "unknown"),
            ),
            detections=detections,
            artifacts=ArtifactSet(
                annotated_video=f"/api/video-analysis/{analysis_id}/artifacts/annotated_video",
                detections_json=f"/api/video-analysis/{analysis_id}/artifacts/detections_json",
                preview_image=(
                    f"/api/video-analysis/{analysis_id}/artifacts/preview_image"
                    if preview_written
                    else None
                ),
            ),
            warnings=warnings,
            frames_analyzed=frames_analyzed,
            processing_duration_seconds=round(duration, 3),
        )

    @staticmethod
    def _annotate(frame, detection: Detection) -> None:
        box = detection.bbox
        cv2.rectangle(frame, (box.x1, box.y1), (box.x2, box.y2), (199, 255, 61), 2)
        label = f"{detection.football_role} {detection.confidence:.2f}"
        cv2.putText(
            frame,
            label,
            (box.x1, max(18, box.y1 - 7)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (199, 255, 61),
            1,
            cv2.LINE_AA,
        )

