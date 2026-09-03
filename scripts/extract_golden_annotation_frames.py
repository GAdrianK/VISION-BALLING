from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import cv2

ROOT = Path(__file__).resolve().parents[1]
GOLDEN_DATA_DIR_ENV = "VISION_BALLING_GOLDEN_DATA_DIR"
REQUIRED_INVENTORY_FIELDS = {
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


class ExtractionError(RuntimeError):
    """Raised when canonical inputs or extracted media are inconsistent."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ExtractionError(f"Cannot read {path}: {error}") from error
    if not isinstance(payload, dict):
        raise ExtractionError(f"Expected a JSON object in {path}")
    return payload


def load_inventory(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = set(reader.fieldnames or [])
            missing = REQUIRED_INVENTORY_FIELDS - fields
            if missing:
                raise ExtractionError(
                    "Inventory fields missing: " + ", ".join(sorted(missing))
                )
            rows = list(reader)
    except OSError as error:
        raise ExtractionError(f"Cannot read {path}: {error}") from error
    if not rows:
        raise ExtractionError("Frame inventory is empty")
    return rows


def validate_inputs(
    golden_manifest: dict[str, Any],
    inventory: list[dict[str, str]],
    tracking_manifest: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    videos = {video["id"]: video for video in golden_manifest.get("videos", [])}
    if len(videos) != 3 or any(video.get("status") != "READY" for video in videos.values()):
        raise ExtractionError("Exactly three READY golden videos are required")

    seen_uids: set[str] = set()
    seen_pairs: set[tuple[str, int]] = set()
    previous_sort_key: tuple[str, int] | None = None
    for row in inventory:
        golden_id = row["golden_id"]
        if golden_id not in videos:
            raise ExtractionError(f"Unknown golden ID: {golden_id}")
        frame_index = int(row["frame_index"])
        video = videos[golden_id]
        if not 0 <= frame_index < int(video["frame_count"]):
            raise ExtractionError(f"Frame index out of range: {golden_id}:{frame_index}")
        expected_uid = f"{golden_id}:{frame_index:08d}"
        if row["frame_uid"] != expected_uid:
            raise ExtractionError(f"Invalid frame UID: {row['frame_uid']}")
        if row["frame_uid"] in seen_uids or (golden_id, frame_index) in seen_pairs:
            raise ExtractionError(f"Duplicate frame: {row['frame_uid']}")
        if row["golden_sha256"] != video["sha256"]:
            raise ExtractionError(f"Golden SHA mismatch in inventory: {row['frame_uid']}")
        if row["dataset_role"] != "golden_eval":
            raise ExtractionError(f"Invalid dataset role: {row['frame_uid']}")
        sort_key = (golden_id, frame_index)
        if previous_sort_key is not None and sort_key <= previous_sort_key:
            raise ExtractionError("Inventory is not deterministically sorted")
        previous_sort_key = sort_key
        seen_uids.add(row["frame_uid"])
        seen_pairs.add((golden_id, frame_index))

    if not 500 <= len(inventory) <= 1000:
        raise ExtractionError(f"Unique frame count outside 500-1000: {len(inventory)}")

    sequences = tracking_manifest.get("sequences", [])
    if len(sequences) != 6:
        raise ExtractionError("Exactly six tracking sequences are required")
    for sequence in sequences:
        for index in range(sequence["start_frame"], sequence["end_frame"] + 1):
            if (sequence["golden_id"], index) not in seen_pairs:
                raise ExtractionError(
                    f"Tracking frame absent from inventory: {sequence['sequence_id']}:{index}"
                )
    return videos


def build_task_memberships(
    inventory: list[dict[str, str]],
    tracking_manifest: dict[str, Any],
    calibration_manifest: dict[str, Any],
) -> dict[str, list[str]]:
    tasks: dict[str, list[str]] = defaultdict(list)
    golden_codes = {
        "GOLDEN-01-BROADCAST": "G01",
        "GOLDEN-02-TACTICAL-WIDE": "G02",
        "GOLDEN-03-DIFFICULT": "G03",
    }
    for row in inventory:
        if row["selection_role"] in {"sparse", "sparse+tracking"}:
            code = golden_codes[row["golden_id"]]
            tasks[f"CVAT-{code}-DETECTION"].append(row["frame_uid"])

    for sequence in tracking_manifest["sequences"]:
        task_id = f"CVAT-{sequence['sequence_id'].removeprefix('TRACK-')}"
        task_id = task_id.replace("CVAT-G", "CVAT-TRACK-G")
        for index in range(sequence["start_frame"], sequence["end_frame"] + 1):
            tasks[task_id].append(f"{sequence['golden_id']}:{index:08d}")

    for frame in calibration_manifest["frames"]:
        code = golden_codes[frame["golden_id"]]
        tasks[f"CVAT-{code}-CALIBRATION"].append(frame["frame_uid"])
    return dict(tasks)


def extract_video_frames(
    video: dict[str, Any],
    rows: list[dict[str, str]],
    asset_path: Path,
    frames_root: Path,
    *,
    overwrite: bool,
) -> tuple[list[dict[str, str]], dict[str, float | int | str]]:
    expected_sha = video["sha256"]
    actual_sha = sha256_file(asset_path)
    if actual_sha != expected_sha:
        raise ExtractionError(
            f"Golden SHA mismatch for {video['id']}: expected={expected_sha} actual={actual_sha}"
        )

    requested = {int(row["frame_index"]): row for row in rows}
    destination = frames_root / video["id"]
    destination.mkdir(parents=True, exist_ok=True)
    if not overwrite and any(destination.glob("*.png")):
        raise ExtractionError(
            f"Output already contains PNG files for {video['id']}; use --overwrite"
        )

    capture = cv2.VideoCapture(str(asset_path))
    if not capture.isOpened():
        raise ExtractionError(f"Cannot open golden video: {asset_path}")
    reported_count = int(round(capture.get(cv2.CAP_PROP_FRAME_COUNT)))
    if reported_count != int(video["frame_count"]):
        capture.release()
        raise ExtractionError(
            f"Frame count mismatch for {video['id']}: "
            f"manifest={video['frame_count']} decoder={reported_count}"
        )

    selected: list[dict[str, str]] = []
    started = time.perf_counter()
    frame_index = 0
    last_requested = max(requested)
    try:
        while frame_index <= last_requested:
            ok, frame = capture.read()
            if not ok:
                raise ExtractionError(
                    f"Decoder stopped before requested frame {frame_index} in {video['id']}"
                )
            row = requested.get(frame_index)
            if row is not None:
                height, width = frame.shape[:2]
                if width != int(row["width"]) or height != int(row["height"]):
                    raise ExtractionError(
                        f"Resolution mismatch at {row['frame_uid']}: {width}x{height}"
                    )
                filename = f"{video['id']}__{frame_index:08d}.png"
                output_path = destination / filename
                written = cv2.imwrite(
                    str(output_path),
                    frame,
                    [cv2.IMWRITE_PNG_COMPRESSION, 3],
                )
                if not written or output_path.stat().st_size == 0:
                    raise ExtractionError(f"Cannot write {output_path}")
                selected.append(
                    {
                        **row,
                        "relative_path": output_path.relative_to(frames_root.parent).as_posix(),
                        "file_size_bytes": str(output_path.stat().st_size),
                    }
                )
            frame_index += 1
    finally:
        capture.release()

    if len(selected) != len(requested):
        raise ExtractionError(
            f"Selected frame count mismatch for {video['id']}: "
            f"expected={len(requested)} actual={len(selected)}"
        )
    elapsed = time.perf_counter() - started
    return selected, {
        "golden_id": video["id"],
        "frames_read": frame_index,
        "frames_selected": len(selected),
        "duration_seconds": round(elapsed, 3),
    }


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Extract lossless, original-resolution CVAT media from locked goldens."
    )
    parser.add_argument(
        "--golden-manifest",
        type=Path,
        default=ROOT / "data/manifests/golden_videos_v1.json",
    )
    parser.add_argument(
        "--frame-inventory",
        type=Path,
        default=ROOT / "data/manifests/golden_frames_v1.csv",
    )
    parser.add_argument(
        "--tracking-manifest",
        type=Path,
        default=ROOT / "data/manifests/tracking_sequences_v1.json",
    )
    parser.add_argument(
        "--calibration-manifest",
        type=Path,
        default=ROOT / "data/manifests/calibration_frames_v1.json",
    )
    parser.add_argument("--data-dir", type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "data/golden/annotation_media",
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    golden_manifest = load_json(args.golden_manifest)
    inventory = load_inventory(args.frame_inventory)
    tracking_manifest = load_json(args.tracking_manifest)
    calibration_manifest = load_json(args.calibration_manifest)
    videos = validate_inputs(golden_manifest, inventory, tracking_manifest)

    configured_data_dir = args.data_dir or os.getenv(GOLDEN_DATA_DIR_ENV)
    data_dir = Path(configured_data_dir or ROOT / "data/golden/assets").resolve()
    output_dir = args.output_dir.resolve()
    frames_root = output_dir / "frames"

    rows_by_golden: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in inventory:
        rows_by_golden[row["golden_id"]].append(row)

    mapping_rows: list[dict[str, str]] = []
    summaries: list[dict[str, float | int | str]] = []
    for golden_id in sorted(videos):
        video = videos[golden_id]
        asset_path = data_dir / video["filename"]
        if not asset_path.is_file():
            raise ExtractionError(f"Golden asset missing: {asset_path}")
        selected, summary = extract_video_frames(
            video,
            rows_by_golden[golden_id],
            asset_path,
            frames_root,
            overwrite=args.overwrite,
        )
        mapping_rows.extend(selected)
        summaries.append(summary)
        print(
            f"{golden_id} frames_read={summary['frames_read']} "
            f"frames_selected={summary['frames_selected']} "
            f"duration={summary['duration_seconds']}s",
            flush=True,
        )

    mapping_fields = [
        "frame_uid",
        "golden_id",
        "golden_sha256",
        "frame_index",
        "timestamp_seconds",
        "width",
        "height",
        "selection_role",
        "tracking_sequence_id",
        "annotation_status",
        "dataset_role",
        "relative_path",
        "file_size_bytes",
    ]
    write_csv(output_dir / "frame_mapping.csv", mapping_rows, mapping_fields)

    by_uid = {row["frame_uid"]: row for row in mapping_rows}
    tasks = build_task_memberships(
        inventory,
        tracking_manifest,
        calibration_manifest,
    )
    task_fields = [
        "frame_uid",
        "relative_path",
        "frame_index",
        "timestamp_seconds",
    ]
    for task_id, frame_uids in sorted(tasks.items()):
        task_rows = [by_uid[frame_uid] for frame_uid in frame_uids]
        write_csv(output_dir / "tasks" / f"{task_id}.csv", task_rows, task_fields)

    disk_size = sum(
        path.stat().st_size for path in output_dir.rglob("*") if path.is_file()
    )
    summary_payload = {
        "format": "PNG lossless",
        "png_compression": 3,
        "unique_frames": len(mapping_rows),
        "task_manifests": len(tasks),
        "disk_size_bytes": disk_size,
        "goldens": summaries,
    }
    (output_dir / "extraction_summary.json").write_text(
        json.dumps(summary_payload, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary_payload, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
