from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VideoBackendDiagnostic:
    ffmpeg_available: bool
    ffprobe_available: bool
    ffmpeg_version: str | None
    video_backend: str


def _first_version_line(executable: str) -> str | None:
    path = shutil.which(executable)
    if not path:
        return None
    try:
        result = subprocess.run(
            [path, "-version"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.splitlines()[0] if result.stdout else None


def diagnose_video_backend() -> VideoBackendDiagnostic:
    ffmpeg_version = _first_version_line("ffmpeg")
    ffprobe_available = _first_version_line("ffprobe") is not None
    return VideoBackendDiagnostic(
        ffmpeg_available=ffmpeg_version is not None,
        ffprobe_available=ffprobe_available,
        ffmpeg_version=ffmpeg_version,
        video_backend="ffmpeg" if ffmpeg_version else "opencv",
    )


def build_audio_remux_command(
    ffmpeg_path: str,
    silent_video: Path,
    source_video: Path,
    destination: Path,
    *,
    fps: float = 30,
) -> list[str]:
    """Backward-compatible wrapper for normalized output with optional source audio."""
    return build_video_normalization_command(
        ffmpeg_path=ffmpeg_path,
        intermediate_video=silent_video,
        destination=destination,
        fps=fps,
        preserve_audio=True,
        source_video=source_video,
    )


def build_video_normalization_command(
    ffmpeg_path: str,
    intermediate_video: Path,
    destination: Path,
    *,
    fps: float,
    preserve_audio: bool,
    source_video: Path | None = None,
) -> list[str]:
    """Build a browser-oriented, shell-free FFmpeg normalization command."""
    if fps <= 0:
        raise ValueError("La cadence de normalisation doit être strictement positive.")
    if preserve_audio and source_video is None:
        raise ValueError("La source audio est requise lorsque l'audio doit être préservé.")

    command = [
        ffmpeg_path,
        "-y",
        "-i",
        str(intermediate_video),
    ]
    if preserve_audio:
        command.extend(["-i", str(source_video)])
    command.extend(
        [
            "-map",
            "0:v:0",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-pix_fmt",
            "yuv420p",
            "-tag:v",
            "avc1",
            "-r",
            f"{fps:.6f}".rstrip("0").rstrip("."),
            "-fps_mode",
            "cfr",
        ]
    )
    if preserve_audio:
        command.extend(
            [
                "-map",
                "1:a:0?",
                "-c:a",
                "aac",
                "-shortest",
                "-map_metadata",
                "1",
            ]
        )
    else:
        command.extend(["-an", "-map_metadata", "0"])
    command.extend(
        [
            "-avoid_negative_ts",
            "make_non_negative",
            "-movflags",
            "+faststart",
            str(destination),
        ]
    )
    return command


def run_command(command: Sequence[str], timeout: float | None = None) -> None:
    subprocess.run(
        list(command),
        capture_output=True,
        text=True,
        check=True,
        timeout=timeout,
        shell=False,
    )
