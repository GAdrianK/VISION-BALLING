from __future__ import annotations

import argparse
import csv
import hashlib
import json
import struct
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_IDS = (
    "GOLDEN-01-BROADCAST",
    "GOLDEN-02-TACTICAL-WIDE",
    "GOLDEN-03-DIFFICULT",
)
EXPECTED_SEQUENCE_IDS = (
    "TRACK-G01-01",
    "TRACK-G01-02",
    "TRACK-G02-01",
    "TRACK-G02-02",
    "TRACK-G03-01",
    "TRACK-G03-02",
)
SPARSE_STRIDES = {
    "GOLDEN-01-BROADCAST": 25,
    "GOLDEN-02-TACTICAL-WIDE": 25,
    "GOLDEN-03-DIFFICULT": 8,
}
EXPECTED_SPARSE_COUNTS = {
    "GOLDEN-01-BROADCAST": 240,
    "GOLDEN-02-TACTICAL-WIDE": 240,
    "GOLDEN-03-DIFFICULT": 176,
}
EXPECTED_UNIQUE_COUNTS = {
    "GOLDEN-01-BROADCAST": 336,
    "GOLDEN-02-TACTICAL-WIDE": 336,
    "GOLDEN-03-DIFFICULT": 278,
}
EXPECTED_CLASSES = {
    "player",
    "goalkeeper",
    "referee",
    "ball",
    "ignore_person",
    "ignore_region",
}
EXPECTED_TEAMS = {"team_a", "team_b", "unknown", "official", "not_applicable"}
EXPECTED_EVENTS = {"pass", "shot", "ball_out", "restart"}
INVENTORY_FIELDS = {
    "frame_uid",
    "golden_id",
    "golden_sha256",
    "frame_index",
    "timestamp_seconds",
    "width",
    "height",
    "camera_type",
    "selection_role",
    "tracking_sequence_id",
    "annotation_status",
    "dataset_role",
}


class DatasetValidationError(ValueError):
    """Raised when the frozen internal benchmark structure is inconsistent."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_canonical_text_file(path: Path) -> str:
    content = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(content).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DatasetValidationError(f"Cannot read {path}: {error}") from error
    if not isinstance(payload, dict):
        raise DatasetValidationError(f"Expected JSON object in {path}")
    return payload


def load_inventory(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            missing = INVENTORY_FIELDS - set(reader.fieldnames or [])
            if missing:
                raise DatasetValidationError(
                    "Inventory fields missing: " + ", ".join(sorted(missing))
                )
            rows = list(reader)
    except OSError as error:
        raise DatasetValidationError(f"Cannot read {path}: {error}") from error
    return rows


def timestamp_to_seconds(value: str) -> float:
    try:
        hours, minutes, seconds = value.split(":")
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except (ValueError, AttributeError) as error:
        raise DatasetValidationError(f"Invalid timestamp: {value}") from error


def require(condition: bool, message: str) -> None:
    if not condition:
        raise DatasetValidationError(message)


def validate_golden_manifest(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    require(manifest.get("manifest_version") == "1.1.0", "Golden manifest must be 1.1.0")
    videos = manifest.get("videos", [])
    require(len(videos) == 3, "Exactly three golden videos are required")
    require(
        [video.get("id") for video in videos] == list(EXPECTED_IDS),
        "Golden IDs or order are invalid",
    )
    require(
        all(video.get("status") == "READY" for video in videos),
        "All golden videos must be READY",
    )
    for video in videos:
        checksum = video.get("sha256", "")
        require(
            isinstance(checksum, str) and len(checksum) == 64,
            f"Invalid golden SHA for {video.get('id')}",
        )
    return {video["id"]: video for video in videos}


def validate_tracking(
    tracking: dict[str, Any],
    videos: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, dict[int, str]]]:
    require(tracking.get("manifest_version") == "1.0.0", "Tracking version must be 1.0.0")
    require(tracking.get("dataset_role") == "golden_eval", "Tracking role must be golden_eval")
    sequences = tracking.get("sequences", [])
    require(len(sequences) == 6, "Exactly six tracking sequences are required")
    require(
        [item.get("sequence_id") for item in sequences] == list(EXPECTED_SEQUENCE_IDS),
        "Tracking sequence IDs or order are invalid",
    )
    per_golden = Counter(item.get("golden_id") for item in sequences)
    require(
        per_golden == Counter({golden_id: 2 for golden_id in EXPECTED_IDS}),
        "Exactly two tracking sequences per golden are required",
    )

    memberships: dict[str, dict[int, str]] = defaultdict(dict)
    for sequence in sequences:
        golden_id = sequence["golden_id"]
        video = videos[golden_id]
        start = int(sequence["start_frame"])
        end = int(sequence["end_frame"])
        count = end - start + 1
        fps = float(sequence["fps"])
        require(start >= 0 and end < int(video["frame_count"]), f"Sequence out of range: {sequence['sequence_id']}")
        require(count == int(sequence["frame_count"]), f"Frame count mismatch: {sequence['sequence_id']}")
        require(abs(count / fps - 2.0) <= 1 / fps, f"Tracking duration is not about 2 seconds: {sequence['sequence_id']}")
        require(abs(timestamp_to_seconds(sequence["start_timestamp"]) - start / fps) <= 1e-8, f"Start timestamp mismatch: {sequence['sequence_id']}")
        require(abs(timestamp_to_seconds(sequence["end_timestamp"]) - end / fps) <= 1e-8, f"End timestamp mismatch: {sequence['sequence_id']}")
        require(sequence["golden_sha256"] == video["sha256"], f"Tracking SHA mismatch: {sequence['sequence_id']}")
        for index in range(start, end + 1):
            require(index not in memberships[golden_id], f"Overlapping tracking sequences for {golden_id}")
            memberships[golden_id][index] = sequence["sequence_id"]
    return sequences, dict(memberships)


def validate_inventory(
    rows: list[dict[str, str]],
    videos: dict[str, dict[str, Any]],
    tracking_memberships: dict[str, dict[int, str]],
) -> dict[str, dict[str, int]]:
    require(500 <= len(rows) <= 1000, f"Unique total outside 500-1000: {len(rows)}")
    require(len(rows) == 950, f"Frozen V1 inventory must contain 950 frames, got {len(rows)}")
    uids: set[str] = set()
    pairs: set[tuple[str, int]] = set()
    actual_indices: dict[str, set[int]] = defaultdict(set)
    sparse_indices: dict[str, set[int]] = defaultdict(set)
    previous: tuple[str, int] | None = None
    for row in rows:
        golden_id = row["golden_id"]
        require(golden_id in videos, f"Unknown golden in inventory: {golden_id}")
        frame_index = int(row["frame_index"])
        video = videos[golden_id]
        require(0 <= frame_index < int(video["frame_count"]), f"Frame out of range: {row['frame_uid']}")
        expected_uid = f"{golden_id}:{frame_index:08d}"
        require(row["frame_uid"] == expected_uid, f"Invalid UID: {row['frame_uid']}")
        require(row["frame_uid"] not in uids, f"Duplicate UID: {row['frame_uid']}")
        require((golden_id, frame_index) not in pairs, f"Duplicate frame index: {expected_uid}")
        require(row["golden_sha256"] == video["sha256"], f"Inventory SHA mismatch: {expected_uid}")
        require(int(row["width"]) == int(video["width"]), f"Width mismatch: {expected_uid}")
        require(int(row["height"]) == int(video["height"]), f"Height mismatch: {expected_uid}")
        require(abs(float(row["timestamp_seconds"]) - frame_index / float(video["fps"])) <= 1e-8, f"Timestamp mismatch: {expected_uid}")
        require(row["selection_role"] in {"sparse", "tracking", "sparse+tracking"}, f"Invalid selection role: {expected_uid}")
        require(row["annotation_status"] == "PENDING", f"Unexpected annotation status: {expected_uid}")
        require(row["dataset_role"] == "golden_eval", f"Training leakage role: {expected_uid}")
        sort_key = (golden_id, frame_index)
        require(previous is None or sort_key > previous, "Inventory order is not deterministic")
        previous = sort_key

        is_sparse = frame_index % SPARSE_STRIDES[golden_id] == 0
        sequence_id = tracking_memberships.get(golden_id, {}).get(frame_index, "")
        expected_role = "sparse+tracking" if is_sparse and sequence_id else "sparse" if is_sparse else "tracking"
        require(row["selection_role"] == expected_role, f"Selection role mismatch: {expected_uid}")
        require(row["tracking_sequence_id"] == sequence_id, f"Tracking sequence mismatch: {expected_uid}")
        if is_sparse:
            sparse_indices[golden_id].add(frame_index)
        actual_indices[golden_id].add(frame_index)
        uids.add(row["frame_uid"])
        pairs.add((golden_id, frame_index))

    summary: dict[str, dict[str, int]] = {}
    for golden_id, video in videos.items():
        expected_sparse = set(range(0, int(video["frame_count"]), SPARSE_STRIDES[golden_id]))
        expected_all = expected_sparse | set(tracking_memberships[golden_id])
        require(sparse_indices[golden_id] == expected_sparse, f"Sparse indices mismatch: {golden_id}")
        require(actual_indices[golden_id] == expected_all, f"Unique inventory mismatch: {golden_id}")
        require(len(expected_sparse) == EXPECTED_SPARSE_COUNTS[golden_id], f"Sparse count mismatch: {golden_id}")
        require(len(expected_all) == EXPECTED_UNIQUE_COUNTS[golden_id], f"Unique count mismatch: {golden_id}")
        overlap = len(expected_sparse & set(tracking_memberships[golden_id]))
        summary[golden_id] = {
            "sparse": len(expected_sparse),
            "tracking": len(tracking_memberships[golden_id]),
            "overlap": overlap,
            "unique": len(expected_all),
        }
    return summary


def validate_calibration(
    calibration: dict[str, Any],
    inventory_rows: list[dict[str, str]],
) -> None:
    require(calibration.get("manifest_version") == "1.0.0", "Calibration version must be 1.0.0")
    require(calibration.get("dataset_role") == "golden_eval", "Calibration role must be golden_eval")
    frames = calibration.get("frames", [])
    require(len(frames) == 30, "Exactly 30 calibration frames are required")
    inventory_uids = {row["frame_uid"] for row in inventory_rows}
    calibration_uids = [frame.get("frame_uid") for frame in frames]
    require(len(set(calibration_uids)) == len(calibration_uids), "Duplicate calibration frame")
    require(set(calibration_uids) <= inventory_uids, "Calibration frame outside inventory")
    counts = Counter(frame.get("golden_id") for frame in frames)
    require(counts == Counter({golden_id: 10 for golden_id in EXPECTED_IDS}), "Expected 10 calibration frames per golden")


def validate_schema(schema: dict[str, Any]) -> None:
    require(schema.get("schema_version") == "1.0.0", "Annotation schema must be 1.0.0")
    require(schema.get("dataset_role") == "golden_eval", "Schema role must be golden_eval")
    classes = [label.get("name") for label in schema.get("object_labels", [])]
    require(len(classes) == len(set(classes)), "Annotation classes must be unique")
    require(set(classes) == EXPECTED_CLASSES, "Annotation class set is invalid")
    teams = set(schema.get("attributes", {}).get("team", {}).get("values", []))
    require(teams == EXPECTED_TEAMS, "Team enum is invalid")
    events = set(schema.get("events", {}).get("values", []))
    require(events == EXPECTED_EVENTS, "Event enum is invalid")
    calibration = schema.get("calibration", {})
    require("pitch_line" in calibration and "pitch_keypoint" in calibration, "Calibration schema is incomplete")


def validate_benchmark_references(benchmark: dict[str, Any], root: Path) -> None:
    require(benchmark.get("benchmark_version") == "1.0.0", "Benchmark version must be 1.0.0")
    require(benchmark.get("dataset_role") == "golden_eval", "Benchmark role must be golden_eval")
    require(benchmark.get("structure_status") == "STRUCTURE_PASS", "Benchmark structure status is invalid")
    require(benchmark.get("annotation_status") == "ANNOTATIONS_PENDING", "Benchmark annotation status is invalid")
    require(set(benchmark.get("partitions", {})) == {"golden_eval"}, "Training partition is forbidden")
    golden_ref = benchmark.get("golden_manifest", {})
    require(golden_ref.get("version") == "1.1.0", "Benchmark must reference golden 1.1.0")
    references = [
        golden_ref,
        benchmark.get("frame_inventory", {}),
        benchmark.get("tracking_sequences", {}),
        benchmark.get("calibration_frames", {}),
        benchmark.get("annotation_schema", {}),
        benchmark.get("split_policy", {}),
        benchmark.get("qa_policy", {}),
    ]
    for reference in references:
        relative_path = reference.get("path")
        expected_sha = reference.get("sha256")
        require(isinstance(relative_path, str), "Benchmark reference path is missing")
        require(isinstance(expected_sha, str) and len(expected_sha) == 64, f"Reference SHA missing: {relative_path}")
        actual_path = root / relative_path
        require(actual_path.is_file(), f"Referenced file missing: {relative_path}")
        require(
            sha256_canonical_text_file(actual_path) == expected_sha,
            f"Reference SHA mismatch: {relative_path}",
        )

    golden_manifest = load_json(root / golden_ref["path"])
    manifest_videos = {
        video["id"]: video for video in golden_manifest.get("videos", [])
    }
    golden_assets = benchmark.get("golden_assets", [])
    require(
        [asset.get("golden_id") for asset in golden_assets] == list(EXPECTED_IDS),
        "Benchmark golden asset IDs or order are invalid",
    )
    for asset in golden_assets:
        golden_id = asset["golden_id"]
        source = manifest_videos[golden_id]
        require(asset.get("sha256") == source.get("sha256"), f"Benchmark golden SHA mismatch: {golden_id}")
        require(asset.get("frame_count") == source.get("frame_count"), f"Benchmark frame count mismatch: {golden_id}")
        require(asset.get("dataset_role") == "golden_eval", f"Benchmark golden role mismatch: {golden_id}")
    annotation_package = benchmark.get("annotation_package", {})
    require(annotation_package.get("status") == "PENDING", "Annotation package must remain PENDING before CVAT")
    require(annotation_package.get("version") is None, "Annotation package version must be null before CVAT")
    require(annotation_package.get("sha256") is None, "Annotation package SHA must be null before CVAT")


def verify_structure(root: Path = ROOT) -> dict[str, Any]:
    manifests = root / "data/manifests"
    golden_manifest = load_json(manifests / "golden_videos_v1.json")
    tracking = load_json(manifests / "tracking_sequences_v1.json")
    calibration = load_json(manifests / "calibration_frames_v1.json")
    schema = load_json(manifests / "annotation_schema_v1.json")
    benchmark = load_json(manifests / "internal_benchmark_v1.json")
    inventory = load_inventory(manifests / "golden_frames_v1.csv")

    videos = validate_golden_manifest(golden_manifest)
    sequences, memberships = validate_tracking(tracking, videos)
    counts = validate_inventory(inventory, videos, memberships)
    validate_calibration(calibration, inventory)
    validate_schema(schema)
    validate_benchmark_references(benchmark, root)
    return {
        "status": "STRUCTURE_PASS",
        "annotation_status": "ANNOTATIONS_PENDING",
        "golden_count": len(videos),
        "tracking_sequence_count": len(sequences),
        "calibration_count": len(calibration["frames"]),
        "total_unique": len(inventory),
        "goldens": counts,
    }


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise DatasetValidationError(f"Invalid PNG: {path}")
    return struct.unpack(">II", header[16:24])


def verify_annotation_media(media_dir: Path, root: Path = ROOT) -> dict[str, int]:
    inventory = load_inventory(root / "data/manifests/golden_frames_v1.csv")
    mapping_path = media_dir / "frame_mapping.csv"
    try:
        with mapping_path.open("r", encoding="utf-8", newline="") as handle:
            mapping = list(csv.DictReader(handle))
    except OSError as error:
        raise DatasetValidationError(f"Cannot read media mapping: {error}") from error
    require(len(mapping) == len(inventory), "Media mapping count mismatch")
    expected = {row["frame_uid"]: row for row in inventory}
    seen: set[str] = set()
    disk_size = 0
    for row in mapping:
        uid = row.get("frame_uid", "")
        require(uid in expected and uid not in seen, f"Unexpected or duplicate media UID: {uid}")
        path = media_dir / row["relative_path"]
        require(path.is_file() and path.stat().st_size > 0, f"Media missing or empty: {uid}")
        width, height = png_dimensions(path)
        require(width == int(expected[uid]["width"]), f"Media width mismatch: {uid}")
        require(height == int(expected[uid]["height"]), f"Media height mismatch: {uid}")
        disk_size += path.stat().st_size
        seen.add(uid)
    task_files = list((media_dir / "tasks").glob("CVAT-*.csv"))
    require(len(task_files) == 12, f"Expected 12 CVAT task manifests, got {len(task_files)}")
    return {"media_count": len(mapping), "media_size_bytes": disk_size, "task_manifest_count": len(task_files)}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the frozen internal validation dataset before CVAT annotation."
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--annotation-media-dir", type=Path)
    args = parser.parse_args()
    try:
        summary = verify_structure(args.root.resolve())
        print("STRUCTURE_PASS")
        print("ANNOTATIONS_PENDING")
        for golden_id, counts in summary["goldens"].items():
            print(
                f"{golden_id} sparse={counts['sparse']} "
                f"tracking_unique={counts['tracking'] - counts['overlap']} "
                f"overlap={counts['overlap']} total_unique={counts['unique']}"
            )
        print(f"TOTAL={summary['total_unique']}")
        if args.annotation_media_dir:
            media = verify_annotation_media(
                args.annotation_media_dir.resolve(),
                args.root.resolve(),
            )
            print(
                "MEDIA_PASS "
                f"count={media['media_count']} "
                f"tasks={media['task_manifest_count']} "
                f"bytes={media['media_size_bytes']}"
            )
        return 0
    except (DatasetValidationError, OSError, ValueError, KeyError) as error:
        print(f"FAIL — {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
