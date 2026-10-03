from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import cv2
import numpy as np
import pytest

from app.video_analysis.detectors import ObjectDetector, RawDetection
from app.video_analysis.pipeline import VideoPipeline
from app.video_analysis.validation import VideoValidator


class EmptyDetector(ObjectDetector):
    def load(self) -> None:
        pass

    def detect(self, frame: np.ndarray) -> list[RawDetection]:
        del frame
        return []

    def metadata(self) -> dict:
        return {
            "name": "empty",
            "version": "1",
            "model_id": "empty-detector-v1",
            "device": "cpu",
            "ball_detection": False,
        }


def _make_synthetic_video(path: Path, *, fps: float = 12, frames: int = 24) -> Path:
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"MJPG"), fps, (320, 240)
    )
    if not writer.isOpened():
        pytest.skip("Le codec MJPG OpenCV n'est pas disponible.")
    for index in range(frames):
        frame = np.zeros((240, 320, 3), dtype=np.uint8)
        cv2.circle(frame, (30 + index * 4, 120), 10, (255, 255, 255), -1)
        writer.write(frame)
    writer.release()
    return path


@pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="FFmpeg et ffprobe sont requis pour valider réellement le MP4 final.",
)
@pytest.mark.parametrize("preserve_audio", [False, True])
def test_final_video_is_browser_normalized(
    tmp_path: Path, preserve_audio: bool
):
    source = _make_synthetic_video(tmp_path / "source.avi")
    validator = VideoValidator({"avi"}, 10 * 1024 * 1024, 10, 320, 240, 0)
    metadata = validator.validate(source, "source.avi")
    output_dir = tmp_path / "result"
    output_dir.mkdir()
    pipeline = VideoPipeline(
        detector=EmptyDetector(),
        frame_sample_rate=2,
        preserve_audio=preserve_audio,
    )

    result = pipeline.run(
        analysis_id="analysis_smoke",
        match_id="match_smoke",
        source=source,
        output_dir=output_dir,
        metadata=metadata,
        progress=lambda _percent, _step: None,
    )

    final_video = output_dir / "annotated.mp4"
    assert final_video.stat().st_size > 0
    completed = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_name,codec_tag_string,pix_fmt,avg_frame_rate,start_time,duration:format=start_time,duration",
            "-of",
            "json",
            str(final_video),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
        shell=False,
    )
    payload = json.loads(completed.stdout)
    stream = payload["streams"][0]
    numerator, denominator = stream["avg_frame_rate"].split("/")
    output_fps = float(numerator) / float(denominator)
    start_time = float(stream.get("start_time", payload["format"]["start_time"]))
    duration = float(stream.get("duration", payload["format"]["duration"]))

    assert stream["codec_name"] == "h264"
    assert stream["codec_tag_string"] == "avc1"
    assert stream["pix_fmt"] == "yuv420p"
    assert output_fps == pytest.approx(metadata.fps, rel=0.01)
    assert start_time >= 0
    assert duration == pytest.approx(metadata.duration_seconds, rel=0.1)
    assert result.pipeline.video_backend == "ffmpeg-libx264"
