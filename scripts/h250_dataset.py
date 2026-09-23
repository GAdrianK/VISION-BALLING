from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
H250_DATA_ENV = "VISION_BALLING_H250_DATA"
RUNS_DIR_ENV = "VISION_BALLING_TRAINING_RUNS_DIR"
EXPECTED_SPLIT_COUNTS = {"train": 14368, "valid": 2726, "test": 2692}
EXPECTED_CLASSES = {0: "ball", 1: "person"}
EXPECTED_ARCHIVE_SHA256 = "da2cca388ec51500c5c9ef4d974d7c28cb73b3a75e8c506299d2715028f8bc37"
EXPECTED_YOLO11N_SHA256 = "0ebbc80d4a7680d14987a577cd21342b65ecfd94632bd9a8da63ae6417644ee1"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png"}


class H250ValidationError(ValueError):
    """Raised when an H250 transfer or training input is not reproducible."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_data_yaml(explicit: Path | None = None, root: Path = ROOT) -> Path:
    configured = os.getenv(H250_DATA_ENV)
    candidates = [
        explicit,
        Path(configured) if configured else None,
        Path("/media/adriano/Windows/datasets/h250/YOLO/data.yaml"),
        Path("D:/datasets/h250/YOLO/data.yaml"),
        root / "data/external/h250/YOLO/data.yaml",
        root / "data/external/h250/data.yaml",
    ]
    for candidate in candidates:
        if candidate is not None and candidate.expanduser().is_file():
            return candidate.expanduser().resolve()
    shown = ", ".join(str(path) for path in candidates if path is not None)
    raise H250ValidationError(f"H250 data.yaml introuvable. Chemins vérifiés : {shown}")


def resolve_runs_dir(explicit: Path | None = None, root: Path = ROOT) -> Path:
    configured = os.getenv(RUNS_DIR_ENV)
    if explicit is not None:
        return explicit.expanduser().resolve()
    if configured:
        return Path(configured).expanduser().resolve()
    if Path("D:/").exists():
        return Path("D:/runs/detect")
    if Path("/media/adriano/Windows").exists():
        return Path("/media/adriano/Windows/runs/detect")
    return (root / "runs/detect").resolve()


def _strip_yaml_scalar(value: str) -> str:
    value = value.split(" #", 1)[0].strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_h250_yaml(path: Path) -> dict[str, Any]:
    """Parse only the small scalar subset used by the frozen H250 data.yaml."""
    values: dict[str, str] = {}
    names: dict[int, str] = {}
    in_names = False
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise H250ValidationError(f"Lecture impossible de {path}: {error}") from error

    for raw_line in lines:
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line[:1].isspace() and in_names:
            match = re.match(r"\s*(\d+)\s*:\s*(.+?)\s*$", raw_line)
            if match:
                names[int(match.group(1))] = _strip_yaml_scalar(match.group(2))
            continue
        in_names = False
        match = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*?)\s*$", raw_line)
        if not match:
            continue
        key, value = match.groups()
        if key == "names":
            in_names = True
        elif value:
            values[key] = _strip_yaml_scalar(value)

    required = {"train", "val", "test"}
    missing = required - set(values)
    if missing:
        raise H250ValidationError("Clés H250 manquantes : " + ", ".join(sorted(missing)))
    if names != EXPECTED_CLASSES:
        raise H250ValidationError(f"Classes H250 invalides : {names!r}")
    return {"values": values, "names": names}


def _resolve_dataset_path(value: str, dataset_root: Path) -> Path:
    candidate = Path(value)
    return candidate.resolve() if candidate.is_absolute() else (dataset_root / candidate).resolve()


def _labels_from_images(images_dir: Path) -> Path:
    parts = list(images_dir.parts)
    lowered = [part.lower() for part in parts]
    if "images" not in lowered:
        raise H250ValidationError(f"Le chemin image ne contient pas de dossier images : {images_dir}")
    index = len(lowered) - 1 - lowered[::-1].index("images")
    parts[index] = "labels"
    return Path(*parts)


def _assert_not_golden(path: Path, root: Path) -> None:
    golden_root = (root / "data/golden").resolve()
    try:
        path.resolve().relative_to(golden_root)
    except ValueError:
        return
    raise H250ValidationError(f"Fuite interdite : un golden ne peut pas servir au training ({path})")


def validate_h250_dataset(
    data_yaml: Path,
    *,
    root: Path = ROOT,
    expected_counts: dict[str, int] | None = EXPECTED_SPLIT_COUNTS,
) -> dict[str, Any]:
    data_yaml = data_yaml.resolve()
    _assert_not_golden(data_yaml, root)
    parsed = parse_h250_yaml(data_yaml)
    configured_root = parsed["values"].get("path")
    dataset_root = (
        _resolve_dataset_path(configured_root, data_yaml.parent)
        if configured_root
        else data_yaml.parent.resolve()
    )
    _assert_not_golden(dataset_root, root)

    split_keys = {"train": "train", "valid": "val", "test": "test"}
    split_stats: dict[str, dict[str, Any]] = {}
    for canonical_name, yaml_key in split_keys.items():
        images_dir = _resolve_dataset_path(parsed["values"][yaml_key], dataset_root)
        labels_dir = _labels_from_images(images_dir)
        _assert_not_golden(images_dir, root)
        if not images_dir.is_dir() or not labels_dir.is_dir():
            raise H250ValidationError(
                f"Split {canonical_name} incomplet : images={images_dir} labels={labels_dir}"
            )
        images = [path for path in images_dir.iterdir() if path.suffix.lower() in IMAGE_SUFFIXES]
        labels = list(labels_dir.glob("*.txt"))
        if len(images) != len(labels) or not images:
            raise H250ValidationError(
                f"Split {canonical_name} incohérent : images={len(images)} labels={len(labels)}"
            )
        if expected_counts is not None and len(images) != expected_counts[canonical_name]:
            raise H250ValidationError(
                f"Split {canonical_name} inattendu : {len(images)} au lieu de "
                f"{expected_counts[canonical_name]}"
            )
        split_stats[canonical_name] = {
            "images": len(images),
            "labels": len(labels),
            "images_dir": str(images_dir),
            "labels_dir": str(labels_dir),
        }

    # Isolation stricte des splits
    train_dir = split_stats["train"]["images_dir"]
    valid_dir = split_stats["valid"]["images_dir"]
    test_dir = split_stats["test"]["images_dir"]
    if train_dir == test_dir:
        raise H250ValidationError("Fuite interdite : le split test ne doit jamais servir au training !")
    if valid_dir == test_dir:
        raise H250ValidationError("Fuite interdite : le split test ne doit jamais servir à la validation !")
    if train_dir == valid_dir:
        raise H250ValidationError("Fuite interdite : train et valid ne doivent pas pointer vers le même dossier !")

    summary = {
        "data_yaml": str(data_yaml),
        "data_yaml_sha256": sha256_file(data_yaml),
        "dataset_root": str(dataset_root),
        "classes": {str(key): value for key, value in EXPECTED_CLASSES.items()},
        "splits": split_stats,
        "dataset_role": "training",
    }
    summary["semantic_fingerprint"] = compute_semantic_dataset_fingerprint(summary)
    return summary


def compute_semantic_dataset_fingerprint(summary: dict[str, Any]) -> str:
    """Calcule une empreinte cryptographique canonique et portable de l'identité du dataset.

    Garantit que le dataset est strictement SoccerNet H250 indépendamment du chemin physique.
    """
    payload = {
        "classes": summary["classes"],
        "dataset_role": summary["dataset_role"],
        "split_counts": {
            split: stats["images"] for split, stats in sorted(summary["splits"].items())
        },
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def validate_initial_weights(path: Path, expected_sha256: str = EXPECTED_YOLO11N_SHA256) -> dict[str, Any]:
    path = path.expanduser().resolve()
    if not path.is_file() or path.stat().st_size <= 0:
        raise H250ValidationError(f"Poids initiaux introuvables : {path}")
    actual_sha = sha256_file(path)
    if actual_sha != expected_sha256:
        raise H250ValidationError(
            f"SHA-256 yolo11n.pt invalide : expected={expected_sha256} actual={actual_sha}"
        )
    return {"path": str(path), "bytes": path.stat().st_size, "sha256": actual_sha}
