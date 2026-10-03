from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from h250_dataset import (
    EXPECTED_ARCHIVE_SHA256,
    EXPECTED_YOLO11N_SHA256,
    H250ValidationError,
    sha256_file,
    validate_initial_weights,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARCHIVE = Path("D:/datasets/h250/YOLO.zip")
DEFAULT_WEIGHTS = ROOT / "yolo11n.pt"
DEFAULT_EXP01_BEST = Path("D:/runs/detect/exp01_yolo11n_h250_640_b4/weights/best.pt")
EXP01_BEST_SHA256 = "590dcb69ee501bddc61de0cded5f40b0bf65c00d83c2ebbe8e5962a646eb9844"


def _git_value(*args: str) -> str | None:
    try:
        return subprocess.run(
            ["git", *args],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def _file_record(path: Path, expected_sha256: str, role: str) -> dict[str, Any]:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise H250ValidationError(f"Fichier de transfert manquant : {path}")
    actual_sha = sha256_file(path)
    if actual_sha != expected_sha256:
        raise H250ValidationError(
            f"SHA-256 invalide pour {path}: expected={expected_sha256} actual={actual_sha}"
        )
    return {
        "role": role,
        "source": str(path),
        "filename": path.name,
        "bytes": path.stat().st_size,
        "sha256": actual_sha,
    }


def build_source_manifest(
    archive: Path,
    weights: Path,
    exp01_best: Path | None = None,
) -> dict[str, Any]:
    validate_initial_weights(weights)
    files = [
        _file_record(archive, EXPECTED_ARCHIVE_SHA256, "h250_dataset_archive"),
        _file_record(weights, EXPECTED_YOLO11N_SHA256, "exp02_initial_weights"),
    ]
    if exp01_best is not None:
        files.append(_file_record(exp01_best, EXP01_BEST_SHA256, "exp01_reference_only"))
    return {
        "manifest_version": "1.0.0",
        "experiment_id": "exp02_yolo11n_h250_960_b4",
        "git": {
            "remote": _git_value("remote", "get-url", "origin"),
            "branch": _git_value("branch", "--show-current"),
            "head": _git_value("rev-parse", "HEAD"),
        },
        "files": files,
        "instructions": {
            "dataset_archive_target": "D:/datasets/h250/YOLO.zip",
            "initial_weights_target": "<VISION-BALLING>/yolo11n.pt",
            "exp01_checkpoint_is_training_input": False,
            "golden_data_included": False,
        },
    }


def _copy_verified(source: Path, destination: Path, expected_sha256: str) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        existing_sha = sha256_file(destination)
        if existing_sha == expected_sha256:
            return
        raise H250ValidationError(f"Refus d'écraser un fichier différent : {destination}")
    shutil.copy2(source, destination)
    copied_sha = sha256_file(destination)
    if copied_sha != expected_sha256:
        raise H250ValidationError(
            f"Copie corrompue : {destination}: expected={expected_sha256} actual={copied_sha}"
        )


def copy_transfer_bundle(manifest: dict[str, Any], destination: Path) -> Path:
    destination = destination.expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    role_targets = {
        "h250_dataset_archive": Path("dataset/YOLO.zip"),
        "exp02_initial_weights": Path("weights/yolo11n.pt"),
        "exp01_reference_only": Path("reference/exp01_best.pt"),
    }
    copied_files: list[dict[str, Any]] = []
    for record in manifest["files"]:
        relative_target = role_targets[record["role"]]
        target = destination / relative_target
        _copy_verified(Path(record["source"]), target, record["sha256"])
        copied_files.append({**record, "bundle_path": relative_target.as_posix()})
    output_manifest = {**manifest, "files": copied_files}
    manifest_path = destination / "exp02_transfer_manifest.json"
    manifest_path.write_text(
        json.dumps(output_manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Préparer sur un disque externe le bundle privé nécessaire à EXP-02."
    )
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--archive", type=Path, default=DEFAULT_ARCHIVE)
    parser.add_argument("--weights", type=Path, default=DEFAULT_WEIGHTS)
    parser.add_argument("--include-exp01-best", action="store_true")
    parser.add_argument("--exp01-best", type=Path, default=DEFAULT_EXP01_BEST)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    try:
        manifest = build_source_manifest(
            args.archive,
            args.weights,
            args.exp01_best if args.include_exp01_best else None,
        )
        if args.check_only:
            print(json.dumps(manifest, indent=2, ensure_ascii=False))
            return 0
        if args.destination is None:
            raise H250ValidationError("--destination est requis hors mode --check-only")
        manifest_path = copy_transfer_bundle(manifest, args.destination)
        print(f"TRANSFER_READY {manifest_path}")
        return 0
    except (H250ValidationError, OSError, ValueError) as error:
        print(f"FAIL — {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
