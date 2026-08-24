from __future__ import annotations

import logging
import shutil
import subprocess
import time
from collections.abc import Callable
from itertools import pairwise
from pathlib import Path

import cv2

from app.video_analysis.backends import (
    build_audio_remux_command,
    diagnose_video_backend,
    run_command,
)
from app.video_analysis.detectors import ObjectDetector
from app.video_analysis.schemas import (
    AnalysisResult,
    ArtifactSet,
    BallTrajectoryPoint,
    BoundingBox,
    Detection,
    JobStatus,
    PipelineMetadata,
    VideoMetadata,
)
from app.video_analysis.trackers import (
    BallTracker,
    BallTrackPosition,
    DisabledTracker,
    Tracker,
)

logger = logging.getLogger("football.video_analysis")
ProgressCallback = Callable[[float, str], None]


class VideoPipeline:
    def __init__(
        self,
        detector: ObjectDetector,
        frame_interval: int,
        tracker: Tracker | None = None,
        keep_extracted_frames: bool = False,
        preserve_audio: bool = True,
        max_processing_seconds: float = 0,
        ball_tracker: BallTracker | None = None,
    ) -> None:
        self.detector = detector
        self.tracker = tracker or DisabledTracker()
        self.ball_tracker = ball_tracker or BallTracker()
        self.frame_interval = max(1, frame_interval)
        self.keep_extracted_frames = keep_extracted_frames
        self.preserve_audio = preserve_audio
        self.max_processing_seconds = max_processing_seconds

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
        self.tracker.reset()
        self.ball_tracker.reset()
        detector_metadata = self.detector.metadata()
        tracker_metadata = self.tracker.metadata()
        backend = diagnose_video_backend()
        logger.info(
            "video_processing_started analysis_id=%s model=%s",
            analysis_id,
            detector_metadata["model_id"],
        )

        capture = cv2.VideoCapture(str(source))
        if not capture.isOpened():
            raise RuntimeError("Impossible d'ouvrir la vidéo après validation.")

        silent_path = output_dir / "annotated_silent.mp4"
        annotated_path = output_dir / "annotated.mp4"
        preview_path = output_dir / "preview.jpg"
        frames_dir = output_dir / "frames"
        if self.keep_extracted_frames:
            frames_dir.mkdir(exist_ok=True)

        writer = cv2.VideoWriter(
            str(silent_path),
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
        ball_trajectory: list[BallTrajectoryPoint] = []
        ball_observed_frames = 0
        ball_predicted_frames = 0
        ball_missing_frames = 0
        current_tracking_gap = 0
        longest_tracking_gap = 0
        frames_analyzed = 0
        frames_with_ball: set[int] = set()
        ball_confidences: list[float] = []
        person_count = 0
        unique_tracks: set[int] = set()
        longest_ball_gap = 0
        current_ball_gap = 0
        preview_written = False
        frame_index = 0
        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break

                frame_analyzed = frame_index % self.frame_interval == 0
                raw_detections = []
                if frame_analyzed:
                    try:
                        raw_detections = self.detector.detect(frame)
                    except Exception as exc:
                        raise RuntimeError(
                            f"Erreur du détecteur à la frame {frame_index}: {exc}"
                        ) from exc
                    tracked_detections = self.tracker.update(frame, raw_detections)
                    frames_analyzed += 1
                    frame_has_ball = False
                    for tracked in tracked_detections:
                        raw = tracked.detection
                        x1, y1, x2, y2 = raw.bbox
                        center = {"x": (x1 + x2) / 2, "y": (y1 + y2) / 2}
                        detection = Detection(
                            frame_index=frame_index,
                            timestamp_seconds=round(frame_index / metadata.fps, 6),
                            class_name=raw.class_name,
                            football_role=raw.football_role,
                            confidence=round(raw.confidence, 6),
                            bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
                            center=center,
                            track_id=tracked.track_id,
                            tracker_name=tracker_metadata["name"],
                            model_id=detector_metadata["model_id"],
                        )
                        detections.append(detection)
                        if raw.class_name == "person":
                            person_count += 1
                            if tracked.track_id is not None:
                                unique_tracks.add(tracked.track_id)
                        if raw.class_name == "sports ball":
                            frame_has_ball = True
                            frames_with_ball.add(frame_index)
                            ball_confidences.append(raw.confidence)
                        self._annotate(frame, detection)
                    if frame_has_ball:
                        current_ball_gap = 0
                    else:
                        current_ball_gap += 1
                        longest_ball_gap = max(longest_ball_gap, current_ball_gap)

                ball_position = self.ball_tracker.update(
                    frame_index, frame, raw_detections
                )
                if ball_position is None:
                    ball_missing_frames += 1
                    current_tracking_gap += 1
                    longest_tracking_gap = max(
                        longest_tracking_gap, current_tracking_gap
                    )
                else:
                    current_tracking_gap = 0
                    if ball_position.state == "observed":
                        ball_observed_frames += 1
                    else:
                        ball_predicted_frames += 1
                    x1, y1, x2, y2 = ball_position.bbox
                    ball_trajectory.append(
                        BallTrajectoryPoint(
                            frame_index=frame_index,
                            timestamp_seconds=round(frame_index / metadata.fps, 6),
                            state=ball_position.state,
                            confidence=ball_position.confidence,
                            bbox=BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2),
                            center={
                                "x": ball_position.center[0],
                                "y": ball_position.center[1],
                            },
                        )
                    )
                    self._annotate_ball_trajectory(
                        frame, ball_position, self.ball_tracker.trajectory
                    )

                if frame_analyzed:
                    if self.keep_extracted_frames:
                        cv2.imwrite(
                            str(frames_dir / f"frame_{frame_index:08d}.jpg"), frame
                        )
                    if not preview_written:
                        preview_written = cv2.imwrite(str(preview_path), frame)

                writer.write(frame)
                frame_index += 1
                if (
                    self.max_processing_seconds > 0
                    and time.monotonic() - started_at > self.max_processing_seconds
                ):
                    raise TimeoutError("Durée maximale de traitement vidéo dépassée.")
                if frame_index % max(1, int(metadata.fps * 2)) == 0:
                    ratio = min(frame_index / metadata.frame_count, 1)
                    progress(20 + ratio * 75, "detecting_objects")
        finally:
            capture.release()
            writer.release()

        if frame_index == 0:
            raise RuntimeError("Aucune frame n'a pu être traitée.")

        warnings = [
            (
                "Les personnes sont des player_candidate : joueur, arbitre, entraîneur ou "
                "personne en bord de terrain restent possibles."
            )
        ]
        if not detector_metadata.get("ball_detection"):
            warnings.append(
                "Ce détecteur ne prend pas en charge le ballon ; aucune position de ballon "
                "n'est inférée."
            )
        if not preview_written:
            warnings.append("La génération de l'image de prévisualisation a échoué.")
        if tracker_metadata["enabled"]:
            warnings.append(
                "Les track IDs sont expérimentaux et peuvent changer après une occlusion."
            )
        if backend.ffmpeg_available:
            if self.preserve_audio:
                ffmpeg_path = shutil.which("ffmpeg")
                assert ffmpeg_path
                try:
                    run_command(
                        build_audio_remux_command(
                            ffmpeg_path, silent_path, source, annotated_path
                        ),
                        timeout=max(30, metadata.duration_seconds * 2),
                    )
                    silent_path.unlink(missing_ok=True)
                except (OSError, subprocess.SubprocessError):
                    shutil.move(silent_path, annotated_path)
                    warnings.append(
                        "FFmpeg n'a pas pu préserver l'audio ; vidéo silencieuse conservée."
                    )
            else:
                shutil.move(silent_path, annotated_path)
        else:
            shutil.move(silent_path, annotated_path)
            warnings.append(
                "FFmpeg absent : fallback OpenCV actif, la vidéo annotée est sans audio."
            )

        duration = time.monotonic() - started_at
        average_fps = frames_analyzed / duration if duration else 0
        ball_count = len(ball_confidences)
        ball_rate = len(frames_with_ball) / frames_analyzed if frames_analyzed else 0
        observed_coverage = ball_observed_frames / frame_index
        effective_coverage = (
            ball_observed_frames + ball_predicted_frames
        ) / frame_index
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
                detector_name=detector_metadata.get("name"),
                detector_version=detector_metadata.get("version"),
                tracker_name=tracker_metadata["name"],
                tracker_version=tracker_metadata.get("version"),
                tracking_enabled=tracker_metadata["enabled"],
                ffmpeg_version=backend.ffmpeg_version,
                video_backend=backend.video_backend,
                frame_sample_rate=self.frame_interval,
            ),
            detections=detections,
            ball_trajectory=ball_trajectory,
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
            average_processing_fps=round(average_fps, 3),
            class_summary={
                "person_detections": person_count,
                "ball_detections": ball_count,
                "frames_with_ball": len(frames_with_ball),
                "ball_apparent_detection_rate": round(ball_rate, 6),
                "ball_average_confidence": (
                    round(sum(ball_confidences) / ball_count, 6) if ball_count else 0
                ),
                "longest_sequence_without_ball": longest_ball_gap,
            },
            tracking_summary={
                "unique_person_tracks": len(unique_tracks),
                "tracked_person_detections": sum(
                    1
                    for item in detections
                    if item.class_name == "person" and item.track_id is not None
                ),
                "observed_frames": ball_observed_frames,
                "predicted_frames": ball_predicted_frames,
                "missing_frames": ball_missing_frames,
                "observed_coverage": round(observed_coverage, 6),
                "effective_coverage": round(effective_coverage, 6),
                "longest_missing_gap": longest_tracking_gap,
                "reset_count": self.ball_tracker.reset_count,
            },
        )

    @staticmethod
    def _annotate(frame, detection: Detection) -> None:
        box = detection.bbox
        is_ball = detection.class_name == "sports ball"
        color = (58, 83, 255) if is_ball else (199, 255, 61)
        cv2.rectangle(frame, (box.x1, box.y1), (box.x2, box.y2), color, 2)
        track = f" ID {detection.track_id}" if detection.track_id is not None else ""
        label = f"{detection.football_role}{track} {detection.confidence:.2f}"
        cv2.putText(
            frame,
            label,
            (box.x1, max(18, box.y1 - 7)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            1,
            cv2.LINE_AA,
        )

    @staticmethod
    def _annotate_ball_trajectory(
        frame,
        current: BallTrackPosition,
        trajectory: tuple[BallTrackPosition, ...],
    ) -> None:
        for previous, following in pairwise(trajectory):
            color = (0, 165, 255) if following.state == "predicted" else (0, 255, 255)
            cv2.line(
                frame,
                (round(previous.center[0]), round(previous.center[1])),
                (round(following.center[0]), round(following.center[1])),
                color,
                2,
                cv2.LINE_AA,
            )

        center = (round(current.center[0]), round(current.center[1]))
        color = (0, 165, 255) if current.state == "predicted" else (0, 255, 255)
        if current.state == "predicted":
            cv2.drawMarker(
                frame,
                center,
                color,
                markerType=cv2.MARKER_CROSS,
                markerSize=10,
                thickness=2,
            )
        else:
            cv2.circle(frame, center, 5, color, 2, cv2.LINE_AA)
        cv2.putText(
            frame,
            f"{current.class_name} {current.state}",
            (center[0] + 7, max(18, center[1] - 7)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            color,
            1,
            cv2.LINE_AA,
        )
