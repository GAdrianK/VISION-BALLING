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
) -> list[str]:
    """Build a shell-free command. Paths remain separate argv entries on Windows."""
    return [
        ffmpeg_path,
        "-y",
        "-i",
        str(silent_video),
        "-i",
        str(source_video),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0?",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-shortest",
        "-map_metadata",
        "1",
        str(destination),
    ]


def run_command(command: Sequence[str], timeout: float | None = None) -> None:
    subprocess.run(
        list(command),
        capture_output=True,
        text=True,
        check=True,
        timeout=timeout,
        shell=False,
    )
