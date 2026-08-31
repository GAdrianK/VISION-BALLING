from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.video_analysis.schemas import PIPELINE_VERSION

GIT_SHA_ENV = "VIDEO_GIT_SHA"
_FULL_GIT_SHA = re.compile(r"^[0-9a-fA-F]{40}$")


@dataclass(frozen=True)
class ModelIdentity:
    detector_name: str
    detector_version: str
    model_id: str
    model_checksum: str


def canonical_config_json(config: dict[str, Any]) -> str:
    return json.dumps(
        config,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def build_analysis_key(
    source_sha256: str,
    model_checksum: str,
    canonical_config: dict[str, Any],
    *,
    pipeline_version: str = PIPELINE_VERSION,
) -> str:
    payload = (
        source_sha256
        + model_checksum
        + pipeline_version
        + canonical_config_json(canonical_config)
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_canonical_config(
    settings: Any,
    model: ModelIdentity,
    *,
    tracker_name: str,
    tracker_version: str,
    pipeline_version: str = PIPELINE_VERSION,
    video_backend: str = "ffmpeg",
    ffmpeg_version: str | None = None,
) -> dict[str, Any]:
    configured_detector = settings.VIDEO_DETECTOR.strip().lower()
    detector: dict[str, Any] = {
        "name": model.detector_name,
        "version": model.detector_version,
        "model_id": model.model_id,
        "model_checksum": model.model_checksum,
    }
    if configured_detector in {"yolo", "ultralytics"}:
        detector["model_profile"] = settings.VIDEO_MODEL_PROFILE.strip().lower()
        detector["device"] = settings.VIDEO_DEVICE.strip().lower()
        thresholds = {
            "ball": settings.VIDEO_BALL_CONFIDENCE_THRESHOLD,
            "person": settings.VIDEO_PERSON_CONFIDENCE_THRESHOLD,
        }
    else:
        thresholds = {"global": settings.VIDEO_CONFIDENCE_THRESHOLD}

    tracking_enabled = bool(settings.VIDEO_TRACKING_ENABLED) and tracker_name != "none"
    effective_tracker = tracker_name if tracking_enabled else "none"
    effective_tracker_version = tracker_version if tracking_enabled else "1"
    return {
        "detector": detector,
        "pipeline_version": pipeline_version,
        "sampling": {"frame_sample_rate": settings.video_frame_sample_rate},
        "thresholds": thresholds,
        "tracking": {
            "ball": {
                "max_distance_ratio": settings.VIDEO_BALL_TRACK_MAX_DISTANCE_RATIO,
                "max_missing_frames": settings.VIDEO_BALL_TRACK_MAX_MISSING_FRAMES,
                "trajectory_length": settings.VIDEO_BALL_TRAJECTORY_LENGTH,
            },
            "enabled": tracking_enabled,
            "name": effective_tracker,
            "version": effective_tracker_version,
        },
        "video_output": {
            "codec": "libx264",
            "codec_tag": "avc1",
            "constant_frame_rate": True,
            "faststart": True,
            "fps": "validated_source_fps",
            "normalizer": video_backend,
            "normalizer_version": ffmpeg_version or "unavailable",
            "pixel_format": "yuv420p",
            "preserve_audio": bool(settings.VIDEO_PRESERVE_AUDIO),
        },
    }


def resolve_model_identity(
    settings: Any,
    detector_metadata: dict[str, Any],
    *,
    backend_root: Path,
    checksum_cache: dict[tuple[str, int, int], str] | None = None,
) -> ModelIdentity:
    configured_detector = settings.VIDEO_DETECTOR.strip().lower()
    detector_name = str(
        detector_metadata.get("name") or configured_detector or "unknown"
    ).lower()
    detector_version = str(detector_metadata.get("version") or "unknown")
    if detector_version == "unknown" and detector_name in {"yolo", "ultralytics"}:
        detector_version = _package_version("ultralytics")

    raw_model_id = detector_metadata.get("model_id")
    if not raw_model_id:
        raw_model_id = (
            settings.VIDEO_MODEL_PATH
            if configured_detector in {"yolo", "ultralytics"}
            else settings.VIDEO_MODEL
        )
    model_id = _path_free_model_id(str(raw_model_id))

    model_path = Path(settings.VIDEO_MODEL_PATH).expanduser()
    if not model_path.is_absolute():
        model_path = backend_root / model_path
    if configured_detector in {"yolo", "ultralytics"} and model_path.is_file():
        checksum = sha256_file(model_path, checksum_cache=checksum_cache)
    else:
        fallback = {
            "backend": detector_name,
            "model_id": model_id,
            "profile": (
                settings.VIDEO_MODEL_PROFILE.strip().lower()
                if configured_detector in {"yolo", "ultralytics"}
                else None
            ),
            "version": detector_version,
        }
        checksum = hashlib.sha256(
            canonical_config_json(fallback).encode("utf-8")
        ).hexdigest()
    return ModelIdentity(
        detector_name=detector_name,
        detector_version=detector_version,
        model_id=model_id,
        model_checksum=checksum,
    )


def sha256_file(
    path: Path,
    *,
    checksum_cache: dict[tuple[str, int, int], str] | None = None,
) -> str:
    resolved = path.resolve()
    stat = resolved.stat()
    key = (str(resolved), stat.st_size, stat.st_mtime_ns)
    if checksum_cache is not None and key in checksum_cache:
        return checksum_cache[key]
    digest = hashlib.sha256()
    with resolved.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    checksum = digest.hexdigest()
    if checksum_cache is not None:
        checksum_cache.clear()
        checksum_cache[key] = checksum
    return checksum


def resolve_tracker_identity(
    settings: Any, tracker_metadata: dict[str, Any] | None = None
) -> tuple[str, str]:
    if not settings.VIDEO_TRACKING_ENABLED:
        return ("none", "1")
    configured = settings.VIDEO_TRACKER.strip().lower()
    if configured == "none":
        return ("none", "1")
    if tracker_metadata:
        return (
            str(tracker_metadata.get("name") or configured).lower(),
            str(tracker_metadata.get("version") or "unknown"),
        )
    if configured == "iou":
        return ("iou", "1.0")
    if configured == "bytetrack":
        return ("bytetrack", _package_version("supervision"))
    return (configured, "unknown")


def resolve_git_sha(
    explicit: str | None = None,
    *,
    repository_root: Path | None = None,
) -> str:
    injected = (explicit or os.environ.get(GIT_SHA_ENV, "")).strip()
    if _FULL_GIT_SHA.fullmatch(injected):
        return injected.lower()

    root = repository_root or Path(__file__).resolve().parents[3]
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
            shell=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    candidate = completed.stdout.strip()
    return candidate.lower() if _FULL_GIT_SHA.fullmatch(candidate) else "unknown"


def _package_version(distribution: str) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def _path_free_model_id(value: str) -> str:
    normalized = value.replace("\\", "/").rstrip("/")
    return normalized.rsplit("/", maxsplit=1)[-1] or "unknown"
