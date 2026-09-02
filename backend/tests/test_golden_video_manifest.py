from __future__ import annotations

import hashlib
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.verify_golden_videos import (  # noqa: E402
    EXPECTED_IDS,
    ManifestValidationError,
    VideoMetadata,
    load_manifest,
    validate_manifest,
    verify_video,
)

MANIFEST_PATH = ROOT / "data" / "manifests" / "golden_videos_v1.json"


def _video_entry(golden_id: str, filename: str, content: bytes) -> dict:
    return {
        "id": golden_id,
        "status": "BLOCKED_PIPELINE",
        "version": "1.0.0",
        "filename": filename,
        "sha256": hashlib.sha256(content).hexdigest(),
        "source_sha256": None,
        "source_dataset": "internal-fixture",
        "source_reference": "fixture-reference",
        "license": "Internal benchmark use",
        "usage_conditions": "No redistribution",
        "camera_type": "broadcast",
        "difficulty_tags": ["fixture"],
        "start_timestamp": None,
        "end_timestamp": None,
        "duration_seconds": 10.0,
        "fps": 25.0,
        "width": 1280,
        "height": 720,
        "codec": "h264",
        "container": "mp4",
        "file_size_bytes": len(content),
        "checksum_collision_reason": None,
        "pipeline_validation": {
            "status": "NOT_RUN",
            "validated_at": None,
            "pipeline_version": None,
            "analysis_key": None,
        },
    }


def _manifest(entries: list[dict]) -> dict:
    return {
        "manifest_version": "1.0.0",
        "created_at": "2026-09-01T00:00:00Z",
        "description": "Test manifest",
        "videos": entries,
    }


def _three_entries(content: bytes = b"video-fixture") -> list[dict]:
    return [
        _video_entry(golden_id, f"{golden_id}.mp4", content + bytes([index]))
        for index, golden_id in enumerate(EXPECTED_IDS)
    ]


def _matching_metadata(entry: dict) -> VideoMetadata:
    return VideoMetadata(
        duration_seconds=entry["duration_seconds"],
        fps=entry["fps"],
        width=entry["width"],
        height=entry["height"],
        codec=entry["codec"],
        container=entry["container"],
        file_size_bytes=entry["file_size_bytes"],
    )


def test_committed_manifest_is_valid_and_complete() -> None:
    manifest = load_manifest(MANIFEST_PATH)

    assert manifest["manifest_version"] == "1.1.0"
    assert [video["id"] for video in manifest["videos"]] == list(EXPECTED_IDS)
    assert {video["status"] for video in manifest["videos"]} == {"READY"}
    assert all(video["sha256"] for video in manifest["videos"])
    assert all(
        video["pipeline_validation"]["status"] == "PASS"
        for video in manifest["videos"]
    )


def test_duplicate_golden_id_is_rejected() -> None:
    manifest = _manifest(_three_entries())
    manifest["videos"][1]["id"] = manifest["videos"][0]["id"]

    with pytest.raises(ManifestValidationError, match="dupliqué"):
        validate_manifest(manifest)


def test_invalid_sha256_is_rejected() -> None:
    manifest = _manifest(_three_entries())
    manifest["videos"][0]["sha256"] = "not-a-sha256"

    with pytest.raises(ManifestValidationError, match="SHA-256"):
        validate_manifest(manifest)


def test_unexplained_checksum_collision_is_rejected() -> None:
    manifest = _manifest(_three_entries())
    manifest["videos"][1]["sha256"] = manifest["videos"][0]["sha256"]

    with pytest.raises(ManifestValidationError, match="Collision SHA-256"):
        validate_manifest(manifest)


def test_missing_file_is_blocked(tmp_path: Path) -> None:
    entry = load_manifest(MANIFEST_PATH)["videos"][0]

    result = verify_video(entry, tmp_path)

    assert result.outcome == "BLOCKED"
    assert result.asset_status == "BLOCKED_MISSING"


def test_incorrect_checksum_is_fail(tmp_path: Path) -> None:
    content = b"real-file-content"
    entry = _video_entry(EXPECTED_IDS[0], "golden.mp4", content)
    entry["sha256"] = "0" * 64
    (tmp_path / entry["filename"]).write_bytes(content)

    result = verify_video(entry, tmp_path)

    assert result.outcome == "FAIL"
    assert result.asset_status == "BLOCKED_INTEGRITY"
    assert "SHA-256" in result.reasons[0]


def test_missing_license_is_blocked_license(tmp_path: Path) -> None:
    content = b"licensed-file-placeholder"
    entry = _video_entry(EXPECTED_IDS[0], "golden.mp4", content)
    entry["license"] = None
    (tmp_path / entry["filename"]).write_bytes(content)

    result = verify_video(entry, tmp_path)

    assert result.outcome == "BLOCKED"
    assert result.asset_status == "BLOCKED_LICENSE"


def test_incompatible_metadata_is_fail(tmp_path: Path) -> None:
    content = b"metadata-file-placeholder"
    entry = _video_entry(EXPECTED_IDS[0], "golden.mp4", content)
    (tmp_path / entry["filename"]).write_bytes(content)
    incompatible = replace(_matching_metadata(entry), width=1920)

    result = verify_video(entry, tmp_path, probe=lambda _path: incompatible)

    assert result.outcome == "FAIL"
    assert result.asset_status == "BLOCKED_INTEGRITY"
    assert any("width" in reason for reason in result.reasons)


def test_ready_asset_passes_all_local_checks(tmp_path: Path) -> None:
    content = b"ready-file-placeholder"
    entry = _video_entry(EXPECTED_IDS[0], "golden.mp4", content)
    entry["status"] = "READY"
    entry["pipeline_validation"]["status"] = "PASS"
    entry["pipeline_validation"]["validated_at"] = "2026-09-01T00:00:00Z"
    entry["pipeline_validation"]["pipeline_version"] = "0.4.0"
    entry["pipeline_validation"]["analysis_key"] = "a" * 64
    (tmp_path / entry["filename"]).write_bytes(content)
    metadata = replace(
        _matching_metadata(entry), container="mov,mp4,m4a,3gp,3g2,mj2"
    )

    result = verify_video(entry, tmp_path, probe=lambda _path: metadata)

    assert result.outcome == "PASS"
    assert result.asset_status == "READY"
