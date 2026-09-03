from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PROJECT_NAME = "VISION-BALLING Golden Benchmark V1"
EXPECTED_TASK_COUNT = 12
QA_FIELDS = (
    "task_id",
    "frame_uid",
    "object_or_event_id",
    "issue_type",
    "annotator",
    "reviewer",
    "review_date",
    "resolution",
    "status",
)


class WorkflowPreparationError(RuntimeError):
    """Raised when the private CVAT import workspace cannot be prepared safely."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise WorkflowPreparationError(f"Cannot read {path}: {error}") from error
    if not isinstance(payload, dict):
        raise WorkflowPreparationError(f"Expected a JSON object in {path}")
    return payload


def load_csv(path: Path) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except OSError as error:
        raise WorkflowPreparationError(f"Cannot read {path}: {error}") from error
    if not rows:
        raise WorkflowPreparationError(f"CSV is empty: {path}")
    return rows


def _attribute(name: str, input_type: str, values: list[str], default: str) -> dict[str, Any]:
    return {
        "name": name,
        "input_type": input_type,
        "mutable": True,
        "values": values,
        "default_value": default,
    }


def build_cvat_label_reference(schema: dict[str, Any]) -> list[dict[str, Any]]:
    """Translate the frozen schema into a CVAT label reference without inventing classes."""
    labels: list[dict[str, Any]] = []
    for source in schema["object_labels"]:
        team_values = list(source["team_values"])
        labels.append(
            {
                "name": source["name"],
                "type": source["geometry"],
                "attributes": [
                    _attribute("team", "select", team_values, team_values[-1]),
                    _attribute("truncated", "checkbox", ["false"], "false"),
                    _attribute("uncertain", "checkbox", ["false"], "false"),
                    _attribute("qa_notes", "text", [""], ""),
                ],
            }
        )

    event_schema = schema["events"]
    labels.append(
        {
            "name": "event",
            "type": "tag",
            "schema_entity": "events",
            "attributes": [
                _attribute("event_type", "select", list(event_schema["values"]), "pass"),
                _attribute(
                    "team",
                    "select",
                    list(event_schema["attributes"]["team"]),
                    "unknown",
                ),
                _attribute("actor_track_id", "text", [""], ""),
                _attribute("target_track_id", "text", [""], ""),
                _attribute("notes", "text", [""], ""),
                _attribute("uncertain", "checkbox", ["false"], "false"),
            ],
        }
    )
    labels.extend(
        [
            {
                "name": "pitch_line",
                "type": "polyline",
                "schema_entity": "calibration.pitch_line",
                "attributes": [
                    _attribute(
                        "line_type",
                        "select",
                        list(schema["calibration"]["pitch_line"]["line_type"]),
                        "other_marking",
                    ),
                    _attribute("uncertain", "checkbox", ["false"], "false"),
                    _attribute("qa_notes", "text", [""], ""),
                ],
            },
            {
                "name": "pitch_keypoint",
                "type": "points",
                "schema_entity": "calibration.pitch_keypoint",
                "attributes": [
                    _attribute(
                        "keypoint_type",
                        "select",
                        list(schema["calibration"]["pitch_keypoint"]["keypoint_type"]),
                        "other_known_landmark",
                    ),
                    _attribute("uncertain", "checkbox", ["false"], "false"),
                    _attribute("qa_notes", "text", [""], ""),
                ],
            },
        ]
    )
    return labels


def build_annotation_metadata(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "metadata_version": "1.0.0",
        "dataset_role": "golden_eval",
        "project_name": PROJECT_NAME,
        "annotation_status": "ANNOTATIONS_PENDING",
        "tasks": [
            {
                "task_id": task["task_id"],
                "expected_frames": task["frame_references"],
                "visited_frame_uids": [],
                "reviewed_frame_uids": [],
                "status": "PENDING",
                "annotator_id": None,
                "reviewer_id": None,
            }
            for task in tasks
        ],
        "qa": {
            "sparse_second_review": {
                "GOLDEN-01-BROADCAST": {"required_frames": 24, "reviewed_frame_uids": []},
                "GOLDEN-02-TACTICAL-WIDE": {"required_frames": 24, "reviewed_frame_uids": []},
                "GOLDEN-03-DIFFICULT": {"required_frames": 18, "reviewed_frame_uids": []},
            },
            "ball": {"total_objects": None, "reviewed_objects": 0},
            "tracking": {"reviewed_tasks": []},
            "calibration": {"reviewed_tasks": []},
            "events": {"total_events": None, "reviewed_events": 0},
            "unresolved_issue_count": None,
        },
        "freeze": {
            "package_version": None,
            "package_sha256": None,
            "frozen_at": None,
        },
    }


def _ensure_private_root(root: Path, output_dir: Path) -> None:
    expected = (root / "data/golden/annotations").resolve()
    try:
        output_dir.resolve().relative_to(expected)
    except ValueError as error:
        raise WorkflowPreparationError(
            f"Output must stay inside the ignored private directory {expected}"
        ) from error


def _ensure_hardlink(source: Path, destination: Path) -> None:
    if destination.exists():
        try:
            if destination.samefile(source):
                return
        except OSError:
            pass
        raise WorkflowPreparationError(f"Refusing to overwrite existing import media: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(source, destination)
    except OSError as error:
        raise WorkflowPreparationError(
            f"Cannot hard-link {source} to {destination}: {error}"
        ) from error


def prepare_workflow(
    root: Path = ROOT,
    media_dir: Path | None = None,
    output_dir: Path | None = None,
    *,
    materialize: bool = True,
) -> dict[str, Any]:
    root = root.resolve()
    media_dir = (media_dir or root / "data/golden/annotation_media").resolve()
    output_dir = (output_dir or root / "data/golden/annotations/cvat").resolve()
    _ensure_private_root(root, output_dir)

    schema = load_json(root / "data/manifests/annotation_schema_v1.json")
    benchmark = load_json(root / "data/manifests/internal_benchmark_v1.json")
    if schema.get("dataset_role") != "golden_eval" or benchmark.get("dataset_role") != "golden_eval":
        raise WorkflowPreparationError("Training role is forbidden for golden annotations")
    if set(benchmark.get("partitions", {})) != {"golden_eval"}:
        raise WorkflowPreparationError("Golden benchmark must contain only golden_eval")

    tasks = benchmark.get("cvat_tasks", [])
    if len(tasks) != EXPECTED_TASK_COUNT:
        raise WorkflowPreparationError(f"Expected 12 tasks, got {len(tasks)}")
    task_ids = [task.get("task_id") for task in tasks]
    if len(set(task_ids)) != EXPECTED_TASK_COUNT:
        raise WorkflowPreparationError("CVAT task IDs must be unique")

    task_plans: list[dict[str, Any]] = []
    all_sources: set[Path] = set()
    for order, task in enumerate(tasks, start=1):
        task_id = str(task["task_id"])
        rows = load_csv(media_dir / "tasks" / f"{task_id}.csv")
        if len(rows) != int(task["frame_references"]):
            raise WorkflowPreparationError(
                f"Task count mismatch for {task_id}: expected={task['frame_references']} actual={len(rows)}"
            )
        media: list[dict[str, Any]] = []
        for local_frame, row in enumerate(rows):
            source = (media_dir / row["relative_path"]).resolve()
            try:
                source.relative_to(media_dir)
            except ValueError as error:
                raise WorkflowPreparationError(f"Media escapes private root: {source}") from error
            if not source.is_file() or source.stat().st_size <= 0:
                raise WorkflowPreparationError(f"Missing or empty media: {source}")
            destination = output_dir / "import" / task_id / "images" / source.name
            if materialize:
                _ensure_hardlink(source, destination)
            all_sources.add(source)
            media.append(
                {
                    "local_frame": local_frame,
                    "frame_uid": row["frame_uid"],
                    "filename": source.name,
                }
            )
        task_plans.append(
            {
                "order": order,
                "task_id": task_id,
                "group": task["group"],
                "expected_frames": len(rows),
                "upload_directory": f"import/{task_id}/images",
                "media": media,
                "annotation_status": "PENDING",
            }
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    labels_path = output_dir / "cvat_label_reference_v1.json"
    plan_path = output_dir / "cvat_import_plan_v1.json"
    metadata_path = output_dir / "annotation_metadata_v1.json"
    labels_path.write_text(
        json.dumps(
            {
                "schema_version": schema["schema_version"],
                "project_name": PROJECT_NAME,
                "visibility": "private",
                "labels": build_cvat_label_reference(schema),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    plan_path.write_text(
        json.dumps(
            {
                "workflow_version": "1.0.0",
                "dataset_role": "golden_eval",
                "project_name": PROJECT_NAME,
                "task_count": len(task_plans),
                "unique_media_count": len(all_sources),
                "tasks": task_plans,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    if not metadata_path.exists():
        metadata_path.write_text(
            json.dumps(build_annotation_metadata(tasks), indent=2) + "\n",
            encoding="utf-8",
        )

    qa_path = root / "data/golden/annotations/qa/qa_log_v1.csv"
    qa_path.parent.mkdir(parents=True, exist_ok=True)
    if not qa_path.exists():
        with qa_path.open("w", encoding="utf-8", newline="") as handle:
            csv.writer(handle).writerow(QA_FIELDS)

    return {
        "project_name": PROJECT_NAME,
        "task_count": len(task_plans),
        "task_references": sum(task["expected_frames"] for task in task_plans),
        "unique_media_count": len(all_sources),
        "materialized_links": sum(task["expected_frames"] for task in task_plans)
        if materialize
        else 0,
        "output_dir": str(output_dir),
        "qa_log": str(qa_path),
        "tasks": [
            {"task_id": task["task_id"], "frames": task["expected_frames"]}
            for task in task_plans
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare the private, annotation-empty CVAT workspace for the golden benchmark."
    )
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--media-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--no-materialize",
        action="store_true",
        help="Validate and write plans without creating per-task hard links.",
    )
    args = parser.parse_args()
    try:
        result = prepare_workflow(
            args.root,
            args.media_dir,
            args.output_dir,
            materialize=not args.no_materialize,
        )
        print(
            f"CVAT_IMPORT_READY project={result['project_name']} "
            f"tasks={result['task_count']} unique_media={result['unique_media_count']} "
            f"task_references={result['task_references']} links={result['materialized_links']}"
        )
        for task in result["tasks"]:
            print(f"TASK_READY {task['task_id']} frames={task['frames']}")
        print(f"QA_LOG_READY {result['qa_log']}")
        print("ANNOTATIONS_PENDING")
        print("BLOCKED — CVAT INSTANCE REQUIRED")
        return 0
    except (WorkflowPreparationError, KeyError, OSError, ValueError) as error:
        print(f"FAIL — {error}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
