from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROJECT_NAME = "VISION-BALLING Golden Benchmark V1"
OBJECT_LABELS = {
    "player",
    "goalkeeper",
    "referee",
    "ball",
    "ignore_person",
    "ignore_region",
}
TRACK_LABELS = {"player", "goalkeeper", "referee", "ball"}
CALIBRATION_LABELS = {"pitch_line", "pitch_keypoint"}
EVENT_TYPES = {"pass", "shot", "ball_out", "restart"}
BOOLEAN_VALUES = {"true", "false", "0", "1"}
EXPECTED_TASK_COUNT = 12


class AnnotationValidationError(ValueError):
    """Raised when human annotation exports violate the frozen V1 contract."""


class MissingExportsError(AnnotationValidationError):
    """Raised while the human CVAT export set is incomplete."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AnnotationValidationError(message)


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise AnnotationValidationError(f"Cannot read {path}: {error}") from error
    require(isinstance(payload, dict), f"Expected JSON object in {path}")
    return payload


def load_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError as error:
        raise AnnotationValidationError(f"Cannot read {path}: {error}") from error


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_task_specs(root: Path, media_dir: Path | None = None) -> dict[str, dict[str, Any]]:
    manifests = root / "data/manifests"
    benchmark = load_json(manifests / "internal_benchmark_v1.json")
    require(benchmark.get("dataset_role") == "golden_eval", "Golden dataset role changed")
    require(set(benchmark.get("partitions", {})) == {"golden_eval"}, "Training partition detected")

    inventory = {
        row["frame_uid"]: row for row in load_csv(manifests / "golden_frames_v1.csv")
    }
    media_dir = media_dir or root / "data/golden/annotation_media"
    task_specs: dict[str, dict[str, Any]] = {}
    for task in benchmark.get("cvat_tasks", []):
        task_id = task["task_id"]
        rows = load_csv(media_dir / "tasks" / f"{task_id}.csv")
        require(
            len(rows) == int(task["frame_references"]),
            f"Task media count mismatch: {task_id}",
        )
        frames: list[dict[str, Any]] = []
        for local_frame, row in enumerate(rows):
            source = inventory.get(row["frame_uid"])
            require(source is not None, f"Task frame outside inventory: {row['frame_uid']}")
            frames.append(
                {
                    "local_frame": local_frame,
                    "frame_uid": row["frame_uid"],
                    "golden_id": source["golden_id"],
                    "width": int(source["width"]),
                    "height": int(source["height"]),
                    "filename": Path(row["relative_path"]).name,
                }
            )
        sequence_id = None
        if task["group"] == "tracking":
            sequence_id = task_id.removeprefix("CVAT-")
        task_specs[task_id] = {
            "task_id": task_id,
            "group": task["group"],
            "sequence_id": sequence_id,
            "frames": frames,
        }
    require(len(task_specs) == EXPECTED_TASK_COUNT, "Exactly 12 CVAT tasks are required")
    return task_specs


def _safe_xml_from_bytes(content: bytes, source: str) -> ET.Element:
    require(b"<!DOCTYPE" not in content.upper(), f"DOCTYPE is forbidden in {source}")
    try:
        return ET.fromstring(content)
    except ET.ParseError as error:
        raise AnnotationValidationError(f"Invalid CVAT XML in {source}: {error}") from error


def load_cvat_export(path: Path) -> ET.Element:
    if path.suffix.lower() == ".xml":
        return _safe_xml_from_bytes(path.read_bytes(), str(path))
    if path.suffix.lower() == ".zip":
        try:
            with zipfile.ZipFile(path) as archive:
                candidates = [
                    name
                    for name in archive.namelist()
                    if Path(name).name.lower() == "annotations.xml"
                ]
                require(len(candidates) == 1, f"Expected one annotations.xml in {path}")
                return _safe_xml_from_bytes(archive.read(candidates[0]), str(path))
        except (OSError, zipfile.BadZipFile) as error:
            raise AnnotationValidationError(f"Invalid CVAT archive {path}: {error}") from error
    raise AnnotationValidationError(f"Unsupported CVAT export format: {path}")


def find_exports(exports_dir: Path, task_ids: set[str]) -> dict[str, Path]:
    exports: dict[str, Path] = {}
    for task_id in sorted(task_ids):
        candidates = [
            path
            for suffix in (".xml", ".zip")
            for path in exports_dir.glob(f"{task_id}{suffix}")
            if path.is_file()
        ]
        if len(candidates) != 1:
            raise MissingExportsError(
                f"{task_id}: expected one native export named {task_id}.xml or {task_id}.zip"
            )
        exports[task_id] = candidates[0]
    unexpected = {
        path.stem
        for path in exports_dir.glob("CVAT-*")
        if path.is_file() and path.suffix.lower() in {".xml", ".zip"}
    } - task_ids
    require(not unexpected, "Unexpected CVAT exports: " + ", ".join(sorted(unexpected)))
    return exports


def _attributes(node: ET.Element) -> dict[str, str]:
    values: dict[str, str] = {}
    for attribute in node.findall("attribute"):
        name = attribute.get("name", "")
        require(name and name not in values, f"Duplicate or unnamed attribute on {node.tag}")
        values[name] = (attribute.text or "").strip()
    return values


def _merged_attributes(parent: dict[str, str], node: ET.Element) -> dict[str, str]:
    values = dict(parent)
    values.update(_attributes(node))
    return values


def _validate_boolean_attributes(attributes: dict[str, str], context: str) -> None:
    for name in ("truncated", "uncertain"):
        value = attributes.get(name)
        if value is not None:
            require(value.lower() in BOOLEAN_VALUES, f"Invalid {name} on {context}")


def _validate_object_attributes(
    label: str,
    attributes: dict[str, str],
    team_values: dict[str, set[str]],
    context: str,
) -> None:
    allowed = {"team", "truncated", "uncertain", "qa_notes"}
    require(set(attributes) <= allowed, f"Unknown object attribute on {context}")
    require("team" in attributes, f"Missing team attribute on {context}")
    require(attributes["team"] in team_values[label], f"Invalid team value on {context}")
    _validate_boolean_attributes(attributes, context)


def _number(value: str | None, context: str) -> float:
    try:
        result = float(value or "")
    except ValueError as error:
        raise AnnotationValidationError(f"Invalid coordinate on {context}") from error
    require(math.isfinite(result), f"Non-finite coordinate on {context}")
    return result


def _validate_box(node: ET.Element, width: int, height: int, context: str) -> None:
    xtl = _number(node.get("xtl"), context)
    ytl = _number(node.get("ytl"), context)
    xbr = _number(node.get("xbr"), context)
    ybr = _number(node.get("ybr"), context)
    require(0 <= xtl < xbr <= width, f"Box outside image on {context}")
    require(0 <= ytl < ybr <= height, f"Box outside image on {context}")
    for native in ("occluded", "outside"):
        value = node.get(native)
        if value is not None:
            require(value.lower() in BOOLEAN_VALUES, f"Invalid native {native} on {context}")


def _validate_points(
    value: str | None,
    width: int,
    height: int,
    context: str,
    *,
    minimum: int,
) -> None:
    raw_points = [item for item in (value or "").split(";") if item]
    require(len(raw_points) >= minimum, f"Not enough points on {context}")
    for raw in raw_points:
        parts = raw.split(",")
        require(len(parts) == 2, f"Invalid point on {context}")
        x = _number(parts[0], context)
        y = _number(parts[1], context)
        require(0 <= x <= width and 0 <= y <= height, f"Point outside image on {context}")


def _validate_calibration_shape(
    node: ET.Element,
    label: str,
    width: int,
    height: int,
    schema: dict[str, Any],
    context: str,
) -> None:
    attributes = _attributes(node)
    allowed = {"uncertain", "qa_notes", "line_type", "keypoint_type"}
    require(set(attributes) <= allowed, f"Unknown calibration attribute on {context}")
    _validate_boolean_attributes(attributes, context)
    if label == "pitch_line":
        require(node.tag == "polyline", f"pitch_line must be a polyline on {context}")
        require(
            attributes.get("line_type") in schema["calibration"]["pitch_line"]["line_type"],
            f"Invalid line_type on {context}",
        )
        _validate_points(node.get("points"), width, height, context, minimum=2)
    else:
        require(node.tag == "points", f"pitch_keypoint must use points on {context}")
        require(
            attributes.get("keypoint_type")
            in schema["calibration"]["pitch_keypoint"]["keypoint_type"],
            f"Invalid keypoint_type on {context}",
        )
        _validate_points(node.get("points"), width, height, context, minimum=1)


def _validate_event(
    node: ET.Element,
    frame: dict[str, Any],
    track_ids: set[int],
    schema: dict[str, Any],
    context: str,
) -> str:
    require(node.get("label") == "event", f"Unknown event label on {context}")
    attributes = _attributes(node)
    allowed = {"event_type", "team", "actor_track_id", "target_track_id", "notes", "uncertain"}
    require(set(attributes) <= allowed, f"Unknown event attribute on {context}")
    event_type = attributes.get("event_type", "")
    require(event_type in EVENT_TYPES, f"Invalid event_type on {context}")
    require(attributes.get("team") in schema["events"]["attributes"]["team"], f"Invalid event team on {context}")
    _validate_boolean_attributes(attributes, context)
    for field in ("actor_track_id", "target_track_id"):
        value = attributes.get(field, "")
        if value:
            try:
                track_id = int(value)
            except ValueError as error:
                raise AnnotationValidationError(f"Invalid {field} on {context}") from error
            require(track_id in track_ids, f"Unknown {field} on {context}")
    require(frame["frame_uid"].startswith(frame["golden_id"]), f"Invalid event frame on {context}")
    return event_type


def validate_task_export(
    task: dict[str, Any],
    root_node: ET.Element,
    schema: dict[str, Any],
) -> dict[str, Any]:
    task_id = task["task_id"]
    group = task["group"]
    frames = task["frames"]
    by_filename = {frame["filename"]: frame for frame in frames}
    by_local_frame = {frame["local_frame"]: frame for frame in frames}
    team_values = {
        label["name"]: set(label["team_values"]) for label in schema["object_labels"]
    }
    counts: Counter[str] = Counter()
    event_counts: Counter[str] = Counter()
    annotated_uids: set[str] = set()
    image_uids: set[str] = set()

    tracks = root_node.findall("track")
    track_ids: set[int] = set()
    track_lengths: list[int] = []
    track_class_counts: Counter[str] = Counter()
    if tracks:
        require(group == "tracking", f"Tracks are only allowed in tracking tasks: {task_id}")
    for track in tracks:
        try:
            track_id = int(track.get("id", ""))
        except ValueError as error:
            raise AnnotationValidationError(f"Invalid track ID in {task_id}") from error
        require(track_id >= 0 and track_id not in track_ids, f"Duplicate or negative track ID in {task_id}")
        track_ids.add(track_id)
        label = track.get("label", "")
        require(label in TRACK_LABELS, f"Invalid tracking label {label} in {task_id}")
        inherited = _attributes(track)
        visible_length = 0
        for shape in list(track):
            if shape.tag == "attribute":
                continue
            require(shape.tag == "box", f"Tracking geometry must be box in {task_id}")
            try:
                local_frame = int(shape.get("frame", ""))
            except ValueError as error:
                raise AnnotationValidationError(f"Invalid track frame in {task_id}") from error
            require(local_frame in by_local_frame, f"Track frame outside sequence in {task_id}")
            frame = by_local_frame[local_frame]
            context = f"{task_id}:{track_id}:{frame['frame_uid']}"
            _validate_box(shape, frame["width"], frame["height"], context)
            attributes = _merged_attributes(inherited, shape)
            _validate_object_attributes(label, attributes, team_values, context)
            outside = shape.get("outside", "0").lower() in {"1", "true"}
            if not outside:
                counts[label] += 1
                visible_length += 1
                annotated_uids.add(frame["frame_uid"])
                if shape.get("occluded", "0").lower() in {"1", "true"}:
                    counts["occlusion"] += 1
                if attributes.get("uncertain", "false").lower() in {"1", "true"}:
                    counts["uncertain"] += 1
        track_lengths.append(visible_length)
        track_class_counts[label] += 1

    pending_events: list[tuple[ET.Element, dict[str, Any], str]] = []
    images = root_node.findall("image")
    for image in images:
        filename = Path(image.get("name", "")).name
        require(filename in by_filename, f"Frame outside task {task_id}: {filename}")
        frame = by_filename[filename]
        require(frame["frame_uid"] not in image_uids, f"Duplicate image in {task_id}: {filename}")
        image_uids.add(frame["frame_uid"])
        require(int(image.get("width", "-1")) == frame["width"], f"Image width mismatch: {filename}")
        require(int(image.get("height", "-1")) == frame["height"], f"Image height mismatch: {filename}")
        for shape in list(image):
            context = f"{task_id}:{frame['frame_uid']}"
            if shape.tag == "tag":
                require(group == "tracking", f"Events are only allowed in tracking tasks: {task_id}")
                pending_events.append((shape, frame, context))
                annotated_uids.add(frame["frame_uid"])
                continue
            label = shape.get("label", "")
            if label in OBJECT_LABELS:
                require(group in {"sparse_detection", "tracking"}, f"Object outside object task: {context}")
                expected_geometry = "polygon" if label == "ignore_region" else "box"
                require(shape.tag == expected_geometry, f"Invalid geometry for {label} on {context}")
                attributes = _attributes(shape)
                _validate_object_attributes(label, attributes, team_values, context)
                if shape.tag == "box":
                    _validate_box(shape, frame["width"], frame["height"], context)
                    counts[label] += 1
                    if shape.get("occluded", "0").lower() in {"1", "true"}:
                        counts["occlusion"] += 1
                else:
                    _validate_points(
                        shape.get("points"),
                        frame["width"],
                        frame["height"],
                        context,
                        minimum=3,
                    )
                    counts[label] += 1
                if attributes.get("uncertain", "false").lower() in {"1", "true"}:
                    counts["uncertain"] += 1
                annotated_uids.add(frame["frame_uid"])
            elif label in CALIBRATION_LABELS:
                require(group == "calibration", f"Calibration outside subset: {context}")
                _validate_calibration_shape(
                    shape, label, frame["width"], frame["height"], schema, context
                )
                counts[label] += 1
                annotated_uids.add(frame["frame_uid"])
            else:
                raise AnnotationValidationError(f"Unknown annotation class {label} on {context}")

    if images:
        require(
            image_uids == {frame["frame_uid"] for frame in frames},
            f"CVAT export does not contain every task frame: {task_id}",
        )
    elif group != "tracking":
        raise AnnotationValidationError(f"Image task export contains no images: {task_id}")

    for tag in root_node.findall("tag"):
        require(group == "tracking", f"Events are only allowed in tracking tasks: {task_id}")
        try:
            local_frame = int(tag.get("frame", ""))
        except ValueError as error:
            raise AnnotationValidationError(f"Invalid event frame in {task_id}") from error
        require(local_frame in by_local_frame, f"Event frame outside sequence in {task_id}")
        frame = by_local_frame[local_frame]
        pending_events.append((tag, frame, f"{task_id}:{frame['frame_uid']}"))
        annotated_uids.add(frame["frame_uid"])

    for tag, frame, context in pending_events:
        event_counts[_validate_event(tag, frame, track_ids, schema, context)] += 1

    return {
        "task_id": task_id,
        "group": group,
        "golden_id": frames[0]["golden_id"],
        "expected_frames": len(frames),
        "annotated_uids": annotated_uids,
        "counts": counts,
        "event_counts": event_counts,
        "track_stats": {
            "sequence_id": task["sequence_id"],
            "frames": len(frames),
            "unique_tracks": len(track_ids),
            "player_tracks": track_class_counts["player"],
            "goalkeeper_tracks": track_class_counts["goalkeeper"],
            "referee_tracks": track_class_counts["referee"],
            "ball_tracks": track_class_counts["ball"],
            "average_track_length": round(sum(track_lengths) / len(track_lengths), 6)
            if track_lengths
            else 0.0,
            "occlusion_count": counts["occlusion"],
            "uncertain_count": counts["uncertain"],
        }
        if group == "tracking"
        else None,
    }


def validate_metadata(
    metadata: dict[str, Any],
    task_specs: dict[str, dict[str, Any]],
    results: dict[str, dict[str, Any]],
) -> None:
    require(metadata.get("metadata_version") == "1.0.0", "Metadata version must be 1.0.0")
    require(metadata.get("dataset_role") == "golden_eval", "Annotation training role is forbidden")
    require(metadata.get("project_name") == PROJECT_NAME, "CVAT project name mismatch")
    require(
        metadata.get("annotation_status") in {"READY_TO_FREEZE", "FROZEN"},
        "Human annotations are not READY_TO_FREEZE",
    )
    task_metadata = {item.get("task_id"): item for item in metadata.get("tasks", [])}
    require(set(task_metadata) == set(task_specs), "Annotation metadata task set mismatch")
    for task_id, task in task_specs.items():
        item = task_metadata[task_id]
        expected_uids = {frame["frame_uid"] for frame in task["frames"]}
        require(item.get("expected_frames") == len(expected_uids), f"Expected count mismatch: {task_id}")
        require(set(item.get("visited_frame_uids", [])) == expected_uids, f"Unvisited frames: {task_id}")
        require(set(item.get("reviewed_frame_uids", [])) <= expected_uids, f"Invalid review frame: {task_id}")
        require(item.get("status") == "QA_PASS", f"Task is not QA_PASS: {task_id}")

    qa = metadata.get("qa", {})
    sparse = qa.get("sparse_second_review", {})
    detection_by_golden = {
        task["frames"][0]["golden_id"]: {
            frame["frame_uid"] for frame in task["frames"]
        }
        for task in task_specs.values()
        if task["group"] == "sparse_detection"
    }
    for golden_id, expected_uids in detection_by_golden.items():
        review = sparse.get(golden_id, {})
        minimum = math.ceil(len(expected_uids) * 0.10)
        reviewed = set(review.get("reviewed_frame_uids", []))
        require(review.get("required_frames") == minimum, f"Sparse QA minimum mismatch: {golden_id}")
        require(reviewed <= expected_uids and len(reviewed) >= minimum, f"Sparse QA below 10%: {golden_id}")

    total_ball = sum(result["counts"]["ball"] for result in results.values())
    ball_qa = qa.get("ball", {})
    require(ball_qa.get("total_objects") == total_ball, "Ball QA total mismatch")
    require(ball_qa.get("reviewed_objects") == total_ball, "Ball QA is not 100%")

    tracking_ids = {task_id for task_id, task in task_specs.items() if task["group"] == "tracking"}
    calibration_ids = {
        task_id for task_id, task in task_specs.items() if task["group"] == "calibration"
    }
    require(set(qa.get("tracking", {}).get("reviewed_tasks", [])) == tracking_ids, "Tracking QA is not 100%")
    require(
        set(qa.get("calibration", {}).get("reviewed_tasks", [])) == calibration_ids,
        "Calibration QA is not 100%",
    )
    total_events = sum(sum(result["event_counts"].values()) for result in results.values())
    events_qa = qa.get("events", {})
    require(events_qa.get("total_events") == total_events, "Event QA total mismatch")
    require(events_qa.get("reviewed_events") == total_events, "Event QA is not 100%")
    require(qa.get("unresolved_issue_count") == 0, "QA has unresolved issues")


def _serializable_statistics(results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    per_golden: dict[str, Counter[str]] = defaultdict(Counter)
    event_per_golden: dict[str, Counter[str]] = defaultdict(Counter)
    annotated_by_golden: dict[str, set[str]] = defaultdict(set)
    for result in results.values():
        golden_id = result["golden_id"]
        per_golden[golden_id].update(result["counts"])
        event_per_golden[golden_id].update(result["event_counts"])
        annotated_by_golden[golden_id].update(result["annotated_uids"])

    output_per_golden: dict[str, dict[str, Any]] = {}
    for golden_id in sorted(per_golden):
        counts = per_golden[golden_id]
        output_per_golden[golden_id] = {
            "annotated_frames": len(annotated_by_golden[golden_id]),
            "player_boxes": counts["player"],
            "goalkeeper_boxes": counts["goalkeeper"],
            "referee_boxes": counts["referee"],
            "ball_boxes": counts["ball"],
            "ignore_person_boxes": counts["ignore_person"],
            "ignore_regions": counts["ignore_region"],
            "pitch_lines": counts["pitch_line"],
            "pitch_keypoints": counts["pitch_keypoint"],
            "events": dict(sorted(event_per_golden[golden_id].items())),
        }

    unique_expected = {
        frame["frame_uid"]
        for result in results.values()
        for frame in result.get("expected_frame_records", [])
    }
    annotated = set().union(*(result["annotated_uids"] for result in results.values()))
    total_counts: Counter[str] = Counter()
    total_events: Counter[str] = Counter()
    for result in results.values():
        total_counts.update(result["counts"])
        total_events.update(result["event_counts"])
    return {
        "total_frames": len(unique_expected),
        "annotated_frames": len(annotated),
        "empty_frames": len(unique_expected - annotated),
        "boxes": {
            label: total_counts[label]
            for label in ("player", "goalkeeper", "referee", "ball", "ignore_person")
        },
        "ignore_regions": total_counts["ignore_region"],
        "events": {event: total_events[event] for event in sorted(EVENT_TYPES)},
        "calibration": {
            "pitch_lines": total_counts["pitch_line"],
            "pitch_keypoints": total_counts["pitch_keypoint"],
        },
        "per_golden": output_per_golden,
        "tracking": [
            result["track_stats"]
            for result in results.values()
            if result["track_stats"] is not None
        ],
    }


def validate_freeze_manifest(
    benchmark: dict[str, Any],
    metadata: dict[str, Any],
    package_path: Path,
    statistics: dict[str, Any],
) -> None:
    require(package_path.is_file() and package_path.suffix.lower() == ".zip", "Private package ZIP missing")
    package = benchmark.get("annotation_package", {})
    require(benchmark.get("annotation_status") == "FROZEN", "Benchmark manifest is not FROZEN")
    require(package.get("status") == "FROZEN", "Annotation package is not FROZEN")
    version = package.get("version")
    require(isinstance(version, str) and version.count(".") == 2, "Package version is invalid")
    actual_sha = sha256_file(package_path)
    require(package.get("sha256") == actual_sha, "Package SHA-256 mismatch")
    require(package.get("task_count") == EXPECTED_TASK_COUNT, "Frozen task count mismatch")
    require(package.get("qa_status") == "QA_PASS", "Frozen QA status mismatch")
    require(package.get("annotation_statistics") == statistics, "Frozen statistics mismatch")
    require(metadata.get("annotation_status") == "FROZEN", "Private metadata is not FROZEN")
    freeze = metadata.get("freeze", {})
    require(freeze.get("package_version") == version, "Private package version mismatch")
    require(freeze.get("package_sha256") == actual_sha, "Private package SHA mismatch")
    require(bool(freeze.get("frozen_at")), "Private frozen_at is missing")


def verify_annotations(
    root: Path = ROOT,
    exports_dir: Path | None = None,
    metadata_path: Path | None = None,
    media_dir: Path | None = None,
    *,
    require_qa: bool = True,
) -> dict[str, Any]:
    root = root.resolve()
    exports_dir = exports_dir or root / "data/golden/annotations/cvat"
    metadata_path = metadata_path or exports_dir / "annotation_metadata_v1.json"
    task_specs = load_task_specs(root, media_dir)
    exports = find_exports(exports_dir, set(task_specs))
    schema = load_json(root / "data/manifests/annotation_schema_v1.json")
    results: dict[str, dict[str, Any]] = {}
    for task_id, task in task_specs.items():
        result = validate_task_export(task, load_cvat_export(exports[task_id]), schema)
        result["expected_frame_records"] = task["frames"]
        results[task_id] = result
    metadata = load_json(metadata_path)
    if require_qa:
        validate_metadata(metadata, task_specs, results)
    statistics = _serializable_statistics(results)
    require(statistics["total_frames"] == 950, "Golden frame coverage must total 950")
    return {"status": "READY_TO_FREEZE", "statistics": statistics, "tasks": results}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate human CVAT exports and QA before freezing golden ground truth."
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--exports-dir", type=Path)
    parser.add_argument("--metadata", type=Path)
    parser.add_argument("--media-dir", type=Path)
    parser.add_argument("--package", type=Path)
    parser.add_argument("--require-frozen", action="store_true")
    args = parser.parse_args()
    try:
        result = verify_annotations(
            args.root,
            args.exports_dir,
            args.metadata,
            args.media_dir,
        )
        if args.require_frozen:
            require(args.package is not None, "--package is required with --require-frozen")
            root = args.root.resolve()
            exports_dir = args.exports_dir or root / "data/golden/annotations/cvat"
            metadata_path = args.metadata or exports_dir / "annotation_metadata_v1.json"
            validate_freeze_manifest(
                load_json(root / "data/manifests/internal_benchmark_v1.json"),
                load_json(metadata_path),
                args.package,
                result["statistics"],
            )
            result["status"] = "FROZEN"
        print("ANNOTATION_EXPORTS_PASS")
        print(json.dumps(result["statistics"], indent=2, sort_keys=True))
        print(result["status"])
        return 0
    except MissingExportsError as error:
        print(f"BLOCKED — CVAT EXPORTS REQUIRED — {error}")
        return 2
    except (AnnotationValidationError, KeyError, OSError, ValueError) as error:
        print(f"FAIL — {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
