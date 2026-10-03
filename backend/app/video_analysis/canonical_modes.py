from __future__ import annotations

import hashlib
import logging
import os
import shutil
from pathlib import Path
from typing import Any

import yaml

from app.core.config import settings

logger = logging.getLogger("football.canonical_modes")

PROJECT_ROOT = Path(__file__).resolve().parents[3]
CONFIG_YAML_PATH = PROJECT_ROOT / "configs" / "vision_balling_rc1.yaml"

LOCKED_RFDETR_SHA256 = (
    "c1a1d88b74edc5ddefa7da4581e2848c4c58c3938d88ad4a1b615f071752ffff"
)
LOCKED_YOLO_CHECKPOINT_PATH = PROJECT_ROOT / "yolo11n.pt"


def resolve_rfdetr_checkpoint_path() -> Path:
    """Resolves the canonical RF-DETR checkpoint path via settings/environment."""
    return settings.get_rfdetr_checkpoint_path()


LOCKED_RFDETR_CHECKPOINT_PATH = resolve_rfdetr_checkpoint_path()

_sha_cache: dict[str, str] = {}


def compute_file_sha256(path: Path) -> str:
    path_str = str(path)
    if path_str in _sha_cache:
        return _sha_cache[path_str]
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            h.update(chunk)
    digest = h.hexdigest()
    _sha_cache[path_str] = digest
    return digest


def load_canonical_yaml_config() -> dict[str, Any]:
    if CONFIG_YAML_PATH.is_file():
        try:
            with open(CONFIG_YAML_PATH, encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as exc:
            logger.warning("Could not parse %s: %s", CONFIG_YAML_PATH, exc)
    return {}


def check_environment_preflight(mode: str) -> None:
    """Validates hardware and dependencies for the selected product mode.

    Fails loudly with an informative exception if prerequisites are unmet.
    Never silently falls back to an obsolete detector or device.
    """
    mode_upper = mode.strip().upper()
    if mode_upper not in ("QUALITY", "LOW_LATENCY"):
        raise ValueError(
            f"Mode inconnu '{mode}'. Modes autorisés : 'QUALITY', 'LOW_LATENCY'."
        )

    # 1. FFmpeg validation (required in both modes for browser-compatible video delivery)
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise RuntimeError(
            "FFmpeg non trouvé dans le PATH. FFmpeg est obligatoire pour encoder les flux vidéo H.264/avc1."
        )

    # 2. PyTorch and CUDA validation
    try:
        import torch
    except ImportError as exc:
        raise RuntimeError("PyTorch n'est pas installé dans l'environnement actif.") from exc

    if not torch.cuda.is_available():
        raise RuntimeError(
            f"{mode_upper} mode unavailable: GPU CUDA indisponible sur ce système (CUDA requis pour les deux modes RC1)."
        )

    # 3. Mode-specific preflight
    if mode_upper == "QUALITY":
        # Check rfdetr package
        try:
            import rfdetr  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "QUALITY mode unavailable: le paquet 'rfdetr' n'est pas installé. Activez l'environnement approprié."
            ) from exc

        # Check checkpoint path
        ckpt = resolve_rfdetr_checkpoint_path()
        if not ckpt.is_file():
            raise RuntimeError(
                f"QUALITY mode unavailable: RF-DETR checkpoint not configured or missing at {ckpt}. "
                "Configure VIDEO_MODEL_PATH or RFDETR_CHECKPOINT_PATH to the valid checkpoint_best_total.pth."
            )

        # Check SHA-256 integrity
        actual_sha = compute_file_sha256(ckpt)
        if actual_sha != LOCKED_RFDETR_SHA256:
            raise RuntimeError(
                f"QUALITY mode unavailable: Checkpoint SHA-256 mismatch. Attendu {LOCKED_RFDETR_SHA256}, obtenu {actual_sha}."
            )

    elif mode_upper == "LOW_LATENCY":
        # Check ultralytics package
        try:
            import ultralytics  # noqa: F401
        except ImportError as exc:
            raise RuntimeError(
                "LOW_LATENCY mode unavailable: le paquet 'ultralytics' n'est pas installé."
            ) from exc

        yolo_path = LOCKED_YOLO_CHECKPOINT_PATH
        if not yolo_path.is_file():
            raise RuntimeError(
                f"LOW_LATENCY mode unavailable: modèle YOLO non trouvé à {yolo_path}."
            )


def resolve_detector_for_mode(mode: str, device: str = "cuda") -> Any:
    """Instantiates the exact detector specified by RC1 canonical configuration."""
    from app.video_analysis.detectors import RFDETRDetector, UltralyticsYOLODetector

    mode_upper = mode.strip().upper()
    if mode_upper == "QUALITY":
        ckpt = resolve_rfdetr_checkpoint_path()
        return RFDETRDetector(
            model_path=str(ckpt),
            device=device,
            resolution=960,
            person_threshold=0.35,
            ball_threshold=0.25,
        )
    elif mode_upper == "LOW_LATENCY":
        return UltralyticsYOLODetector(
            model_path=str(LOCKED_YOLO_CHECKPOINT_PATH),
            device=device,
            person_threshold=0.40,
            ball_threshold=0.25,
            model_profile="coco",
        )
    else:
        raise ValueError(f"Mode inconnu : {mode}")
