from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Any

GOLDEN_DATA_DIR_ENV = "VISION_BALLING_GOLDEN_DATA_DIR"
EXPECTED_IDS = (
    "GOLDEN-01-BROADCAST",
    "GOLDEN-02-TACTICAL-WIDE",
    "GOLDEN-03-DIFFICULT",
)
ASSET_STATUSES = {
    "READY",
    "BLOCKED_MISSING",
    "BLOCKED_LICENSE",
    "BLOCKED_INTEGRITY",
    "BLOCKED_PIPELINE",
}
OUTCOMES = {"PASS", "FAIL", "BLOCKED"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REQUIRED_VIDEO_FIELDS = {
    "id",
    "status",
    "version",
    "filename",
    "sha256",
    "source_sha256",
    "source_dataset",
    "source_reference",
    "license",
    "usage_conditions",
    "camera_type",
    "difficulty_tags",
    "start_timestamp",
    "end_timestamp",
    "duration_seconds",
    "fps",
    "width",
    "height",
    "codec",
    "container",
    "file_size_bytes",
    "pipeline_validation",
}


class ManifestValidationError(ValueError):
    """Raised when the committed golden manifest is structurally invalid."""


class VideoProbeError(RuntimeError):
    """Raised when ffprobe cannot inspect an available video."""


class VideoProbeUnavailableError(VideoProbeError):
    """Raised when ffprobe is not installed or not on PATH."""


@dataclass(frozen=True)
class VideoMetadata:
    duration_seconds: float
    fps: float
    width: int
    height: int
    codec: str
    container: str
    file_size_bytes: int


@dataclass(frozen=True)
class VerificationResult:
    golden_id: str
    outcome: str
    asset_status: str
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.outcome not in OUTCOMES:
            raise ValueError(f"Résultat inconnu : {self.outcome}")
        if self.asset_status not in ASSET_STATUSES:
            raise ValueError(f"Statut d'asset inconnu : {self.asset_status}")


def _require_string(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ManifestValidationError(f"{field} doit être une chaîne non vide")


def _validate_optional_sha256(value: Any, field: str) -> None:
    if value is not None and (
        not isinstance(value, str) or SHA256_RE.fullmatch(value) is None
    ):
        raise ManifestValidationError(f"{field} doit être un SHA-256 hexadécimal")


def _validate_positive_number(value: Any, field: str, *, integer: bool = False) -> None:
    if value is None:
        return
    expected_type = int if integer else (int, float)
    if isinstance(value, bool) or not isinstance(value, expected_type) or value <= 0:
        raise ManifestValidationError(f"{field} doit être strictement positif")


def validate_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    required_top_level = {"manifest_version", "created_at", "description", "videos"}
    missing_top_level = required_top_level - manifest.keys()
    if missing_top_level:
        raise ManifestValidationError(
            "Champs racine manquants : " + ", ".join(sorted(missing_top_level))
        )
    for field in ("manifest_version", "created_at", "description"):
        _require_string(manifest[field], field)
    videos = manifest["videos"]
    if not isinstance(videos, list):
        raise ManifestValidationError("videos doit être une liste")

    seen_ids: set[str] = set()
    checksums: dict[str, list[dict[str, Any]]] = {}
    for index, video in enumerate(videos):
        if not isinstance(video, dict):
            raise ManifestValidationError(f"videos[{index}] doit être un objet")
        missing_fields = REQUIRED_VIDEO_FIELDS - video.keys()
        if missing_fields:
            raise ManifestValidationError(
                f"videos[{index}] champs manquants : "
                + ", ".join(sorted(missing_fields))
            )

        golden_id = video["id"]
        _require_string(golden_id, f"videos[{index}].id")
        if golden_id in seen_ids:
            raise ManifestValidationError(f"ID golden dupliqué : {golden_id}")
        seen_ids.add(golden_id)
        if golden_id not in EXPECTED_IDS:
            raise ManifestValidationError(f"ID golden inattendu : {golden_id}")

        status = video["status"]
        if status not in ASSET_STATUSES:
            raise ManifestValidationError(f"Statut invalide pour {golden_id} : {status}")
        _require_string(video["version"], f"{golden_id}.version")
        filename = video["filename"]
        _require_string(filename, f"{golden_id}.filename")
        if filename != Path(filename).name or "/" in filename or "\\" in filename:
            raise ManifestValidationError(
                f"{golden_id}.filename doit être un nom de fichier sans chemin"
            )

        _validate_optional_sha256(video["sha256"], f"{golden_id}.sha256")
        _validate_optional_sha256(
            video["source_sha256"], f"{golden_id}.source_sha256"
        )
        _validate_positive_number(
            video["duration_seconds"], f"{golden_id}.duration_seconds"
        )
        _validate_positive_number(video["fps"], f"{golden_id}.fps")
        _validate_positive_number(video["width"], f"{golden_id}.width", integer=True)
        _validate_positive_number(video["height"], f"{golden_id}.height", integer=True)
        _validate_positive_number(
            video["file_size_bytes"], f"{golden_id}.file_size_bytes", integer=True
        )
        if not isinstance(video["difficulty_tags"], list) or not all(
            isinstance(tag, str) and tag for tag in video["difficulty_tags"]
        ):
            raise ManifestValidationError(
                f"{golden_id}.difficulty_tags doit être une liste de chaînes"
            )
        if not isinstance(video["pipeline_validation"], dict):
            raise ManifestValidationError(
                f"{golden_id}.pipeline_validation doit être un objet"
            )

        checksum = video["sha256"]
        if checksum is not None:
            checksums.setdefault(checksum, []).append(video)

        if status == "READY":
            ready_fields = (
                "sha256",
                "source_dataset",
                "source_reference",
                "license",
                "usage_conditions",
                "duration_seconds",
                "fps",
                "width",
                "height",
                "codec",
                "container",
                "file_size_bytes",
            )
            missing_ready = [field for field in ready_fields if not video[field]]
            if missing_ready:
                raise ManifestValidationError(
                    f"{golden_id} ne peut pas être READY, champs absents : "
                    + ", ".join(missing_ready)
                )
            if video["pipeline_validation"].get("status") != "PASS":
                raise ManifestValidationError(
                    f"{golden_id} ne peut pas être READY sans pipeline PASS"
                )

    if seen_ids != set(EXPECTED_IDS):
        missing_ids = set(EXPECTED_IDS) - seen_ids
        raise ManifestValidationError(
            "IDs golden manquants : " + ", ".join(sorted(missing_ids))
        )

    for checksum, colliding in checksums.items():
        if len(colliding) < 2:
            continue
        reasons = {item.get("checksum_collision_reason") for item in colliding}
        if len(reasons) != 1 or None in reasons or "" in reasons:
            ids = ", ".join(item["id"] for item in colliding)
            raise ManifestValidationError(
                f"Collision SHA-256 non expliquée ({checksum}) : {ids}"
            )
    return manifest


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ManifestValidationError(f"Manifeste illisible : {error}") from error
    if not isinstance(payload, dict):
        raise ManifestValidationError("La racine du manifeste doit être un objet")
    return validate_manifest(payload)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _fraction_to_float(value: str) -> float:
    try:
        fps = float(Fraction(value))
    except (ValueError, ZeroDivisionError) as error:
        raise VideoProbeError(f"FPS ffprobe invalide : {value}") from error
    if fps <= 0:
        raise VideoProbeError(f"FPS ffprobe non positif : {value}")
    return fps


def probe_video(path: Path) -> VideoMetadata:
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        raise VideoProbeUnavailableError("ffprobe est absent du PATH")
    try:
        completed = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=avg_frame_rate,width,height,codec_name:format=duration,format_name,size",
                "-of",
                "json",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
            shell=False,
        )
        payload = json.loads(completed.stdout)
        stream = payload["streams"][0]
        format_data = payload["format"]
        return VideoMetadata(
            duration_seconds=float(format_data["duration"]),
            fps=_fraction_to_float(stream["avg_frame_rate"]),
            width=int(stream["width"]),
            height=int(stream["height"]),
            codec=str(stream["codec_name"]).lower(),
            container=str(format_data["format_name"]).lower(),
            file_size_bytes=int(format_data["size"]),
        )
    except (
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
        json.JSONDecodeError,
        KeyError,
        IndexError,
        TypeError,
        ValueError,
    ) as error:
        raise VideoProbeError(f"ffprobe ne peut pas lire {path.name} : {error}") from error


def _metadata_mismatches(
    expected: dict[str, Any], actual: VideoMetadata
) -> list[str]:
    mismatches: list[str] = []
    duration_tolerance = max(0.05, 1 / actual.fps)
    if abs(actual.duration_seconds - float(expected["duration_seconds"])) > duration_tolerance:
        mismatches.append(
            "duration_seconds "
            f"attendue={expected['duration_seconds']} réelle={actual.duration_seconds}"
        )
    if abs(actual.fps - float(expected["fps"])) > max(0.001, actual.fps * 0.001):
        mismatches.append(f"fps attendue={expected['fps']} réelle={actual.fps}")
    for field in ("width", "height", "codec", "file_size_bytes"):
        if getattr(actual, field) != expected[field]:
            mismatches.append(
                f"{field} attendu={expected[field]} réel={getattr(actual, field)}"
            )
    expected_container = str(expected["container"]).lower()
    actual_containers = {part.strip() for part in actual.container.split(",")}
    if expected_container not in actual_containers:
        mismatches.append(
            f"container attendu={expected_container} réel={actual.container}"
        )
    return mismatches


def verify_video(
    video: dict[str, Any],
    data_dir: Path | None,
    *,
    probe: Callable[[Path], VideoMetadata] = probe_video,
) -> VerificationResult:
    golden_id = video["id"]
    if data_dir is None:
        return VerificationResult(
            golden_id,
            "BLOCKED",
            "BLOCKED_MISSING",
            (f"{GOLDEN_DATA_DIR_ENV} non défini et --data-dir absent",),
        )
    path = data_dir / video["filename"]
    if not path.is_file():
        return VerificationResult(
            golden_id,
            "BLOCKED",
            "BLOCKED_MISSING",
            (f"fichier absent : {video['filename']}",),
        )
    if path.stat().st_size == 0:
        return VerificationResult(
            golden_id,
            "FAIL",
            "BLOCKED_INTEGRITY",
            ("fichier vide",),
        )

    expected_checksum = video["sha256"]
    expected_size = video["file_size_bytes"]
    if expected_checksum is None or expected_size is None:
        return VerificationResult(
            golden_id,
            "BLOCKED",
            "BLOCKED_INTEGRITY",
            ("checksum ou taille attendue non enregistré",),
        )
    actual_size = path.stat().st_size
    actual_checksum = sha256_file(path)
    integrity_errors = []
    if actual_checksum != expected_checksum:
        integrity_errors.append(
            f"SHA-256 attendu={expected_checksum} réel={actual_checksum}"
        )
    if actual_size != expected_size:
        integrity_errors.append(
            f"taille attendue={expected_size} réelle={actual_size}"
        )
    if integrity_errors:
        return VerificationResult(
            golden_id,
            "FAIL",
            "BLOCKED_INTEGRITY",
            tuple(integrity_errors),
        )

    if not video["license"] or not video["usage_conditions"]:
        return VerificationResult(
            golden_id,
            "BLOCKED",
            "BLOCKED_LICENSE",
            ("licence ou conditions d'usage non renseignées",),
        )

    metadata_fields = (
        "duration_seconds",
        "fps",
        "width",
        "height",
        "codec",
        "container",
    )
    missing_metadata = [field for field in metadata_fields if video[field] is None]
    if missing_metadata:
        return VerificationResult(
            golden_id,
            "BLOCKED",
            "BLOCKED_INTEGRITY",
            ("métadonnées absentes : " + ", ".join(missing_metadata),),
        )
    try:
        actual_metadata = probe(path)
    except VideoProbeUnavailableError as error:
        return VerificationResult(
            golden_id,
            "BLOCKED",
            "BLOCKED_PIPELINE",
            (str(error),),
        )
    except VideoProbeError as error:
        return VerificationResult(
            golden_id,
            "FAIL",
            "BLOCKED_INTEGRITY",
            (str(error),),
        )
    metadata_errors = _metadata_mismatches(video, actual_metadata)
    if metadata_errors:
        return VerificationResult(
            golden_id,
            "FAIL",
            "BLOCKED_INTEGRITY",
            tuple(metadata_errors),
        )

    pipeline_validation = video["pipeline_validation"]
    if pipeline_validation.get("status") != "PASS" or video["status"] != "READY":
        return VerificationResult(
            golden_id,
            "BLOCKED",
            "BLOCKED_PIPELINE",
            ("validation du pipeline Chapitre 2 non enregistrée",),
        )
    return VerificationResult(golden_id, "PASS", "READY", ("asset vérifié",))


def verify_manifest_assets(
    manifest: dict[str, Any],
    data_dir: Path | None,
    *,
    probe: Callable[[Path], VideoMetadata] = probe_video,
) -> list[VerificationResult]:
    validate_manifest(manifest)
    return [verify_video(video, data_dir, probe=probe) for video in manifest["videos"]]


def _resolve_data_dir(argument: Path | None) -> Path | None:
    if argument is not None:
        return argument.expanduser().resolve()
    configured = os.getenv(GOLDEN_DATA_DIR_ENV)
    if not configured:
        return None
    return Path(configured).expanduser().resolve()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Vérifie le manifeste et les trois médias golden hors Git."
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument(
        "--data-dir",
        type=Path,
        help=f"Répertoire local des médias (sinon {GOLDEN_DATA_DIR_ENV})",
    )
    args = parser.parse_args()
    try:
        manifest = load_manifest(args.manifest)
    except ManifestValidationError as error:
        print(f"MANIFEST: FAIL — {error}")
        return 1

    results = verify_manifest_assets(manifest, _resolve_data_dir(args.data_dir))
    for result in results:
        print(
            f"{result.golden_id}: {result.outcome} [{result.asset_status}] — "
            + "; ".join(result.reasons)
        )
    counts = {
        outcome: sum(result.outcome == outcome for result in results)
        for outcome in ("PASS", "FAIL", "BLOCKED")
    }
    print(
        f"SUMMARY PASS={counts['PASS']} FAIL={counts['FAIL']} "
        f"BLOCKED={counts['BLOCKED']}"
    )
    if counts["FAIL"]:
        return 1
    if counts["BLOCKED"]:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
