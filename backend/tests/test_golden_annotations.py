from __future__ import annotations

import copy
import hashlib
import json
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.prepare_golden_cvat_workflow import (  # noqa: E402
    PROJECT_NAME,
    build_annotation_metadata,
    build_cvat_label_reference,
)
from scripts.verify_golden_annotations import (  # noqa: E402
    AnnotationValidationError,
    load_json,
    load_task_specs,
    validate_freeze_manifest,
    verify_annotations,
)


def _attribute(parent: ET.Element, name: str, value: str) -> None:
    node = ET.SubElement(parent, "attribute", name=name)
    node.text = value


def _add_valid_content(root: ET.Element, task: dict, images: list[ET.Element]) -> None:
    if task["group"] == "sparse_detection":
        player = ET.SubElement(
            images[0],
            "box",
            label="player",
            xtl="10",
            ytl="10",
            xbr="30",
            ybr="50",
            occluded="0",
        )
        _attribute(player, "team", "team_a")
        ball = ET.SubElement(
            images[0],
            "box",
            label="ball",
            xtl="40",
            ytl="40",
            xbr="45",
            ybr="45",
            occluded="0",
        )
        _attribute(ball, "team", "not_applicable")
        ignore = ET.SubElement(
            images[0],
            "polygon",
            label="ignore_region",
            points="0,0;5,0;5,5",
        )
        _attribute(ignore, "team", "not_applicable")
    elif task["group"] == "tracking":
        track = ET.SubElement(root, "track", id="0", label="player")
        _attribute(track, "team", "team_b")
        ET.SubElement(
            track,
            "box",
            frame="0",
            xtl="10",
            ytl="10",
            xbr="30",
            ybr="50",
            occluded="1",
            outside="0",
        )
        event = ET.SubElement(root, "tag", frame="0", label="event")
        _attribute(event, "event_type", "pass")
        _attribute(event, "team", "team_b")
        _attribute(event, "actor_track_id", "0")
        _attribute(event, "target_track_id", "")
        _attribute(event, "uncertain", "false")
    else:
        line = ET.SubElement(
            images[0],
            "polyline",
            label="pitch_line",
            points="0,0;100,100",
        )
        _attribute(line, "line_type", "touchline")
        point = ET.SubElement(
            images[0],
            "points",
            label="pitch_keypoint",
            points="50,50",
        )
        _attribute(point, "keypoint_type", "line_intersection")


def _write_exports(exports_dir: Path) -> tuple[dict[str, dict], dict]:
    specs = load_task_specs(ROOT)
    exports_dir.mkdir(parents=True, exist_ok=True)
    for task_id, task in specs.items():
        root = ET.Element("annotations")
        images: list[ET.Element] = []
        for frame in task["frames"]:
            images.append(
                ET.SubElement(
                    root,
                    "image",
                    id=str(frame["local_frame"]),
                    name=frame["filename"],
                    width=str(frame["width"]),
                    height=str(frame["height"]),
                )
            )
        _add_valid_content(root, task, images)
        ET.ElementTree(root).write(
            exports_dir / f"{task_id}.xml",
            encoding="utf-8",
            xml_declaration=True,
        )

    benchmark = load_json(ROOT / "data/manifests/internal_benchmark_v1.json")
    metadata = build_annotation_metadata(benchmark["cvat_tasks"])
    metadata["annotation_status"] = "READY_TO_FREEZE"
    metadata_by_task = {task["task_id"]: task for task in metadata["tasks"]}
    for task_id, spec in specs.items():
        item = metadata_by_task[task_id]
        item["visited_frame_uids"] = [frame["frame_uid"] for frame in spec["frames"]]
        item["status"] = "QA_PASS"

    for golden_id, review in metadata["qa"]["sparse_second_review"].items():
        task = next(
            spec
            for spec in specs.values()
            if spec["group"] == "sparse_detection"
            and spec["frames"][0]["golden_id"] == golden_id
        )
        review["reviewed_frame_uids"] = [
            frame["frame_uid"] for frame in task["frames"][: review["required_frames"]]
        ]
    metadata["qa"]["ball"] = {"total_objects": 3, "reviewed_objects": 3}
    metadata["qa"]["tracking"]["reviewed_tasks"] = [
        task_id for task_id, spec in specs.items() if spec["group"] == "tracking"
    ]
    metadata["qa"]["calibration"]["reviewed_tasks"] = [
        task_id for task_id, spec in specs.items() if spec["group"] == "calibration"
    ]
    metadata["qa"]["events"] = {"total_events": 6, "reviewed_events": 6}
    metadata["qa"]["unresolved_issue_count"] = 0
    (exports_dir / "annotation_metadata_v1.json").write_text(
        json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
    )
    return specs, metadata


def _rewrite(path: Path, mutate) -> None:
    tree = ET.parse(path)
    mutate(tree.getroot())
    tree.write(path, encoding="utf-8", xml_declaration=True)


def test_cvat_label_reference_matches_frozen_schema_entities() -> None:
    schema = load_json(ROOT / "data/manifests/annotation_schema_v1.json")
    labels = build_cvat_label_reference(schema)

    assert [label["name"] for label in labels] == [
        "player",
        "goalkeeper",
        "referee",
        "ball",
        "ignore_person",
        "ignore_region",
        "event",
        "pitch_line",
        "pitch_keypoint",
    ]
    assert schema["dataset_role"] == "golden_eval"
    assert all("train" not in label["name"] for label in labels)


def test_valid_cvat_exports_cover_parser_labels_tracks_events_calibration_and_qa(
    tmp_path: Path,
) -> None:
    exports_dir = tmp_path / "exports"
    _write_exports(exports_dir)

    result = verify_annotations(ROOT, exports_dir)

    stats = result["statistics"]
    assert result["status"] == "READY_TO_FREEZE"
    assert stats["total_frames"] == 950
    assert stats["boxes"] == {
        "player": 9,
        "goalkeeper": 0,
        "referee": 0,
        "ball": 3,
        "ignore_person": 0,
    }
    assert stats["ignore_regions"] == 3
    assert stats["events"]["pass"] == 6
    assert stats["calibration"] == {"pitch_lines": 3, "pitch_keypoints": 3}
    assert len(stats["tracking"]) == 6
    assert all(item["unique_tracks"] == 1 for item in stats["tracking"])


@pytest.mark.parametrize(
    ("task_id", "mutation", "message"),
    [
        (
            "CVAT-G01-DETECTION",
            lambda root: root.find("image/box").set("label", "coach"),
            "Unknown annotation class",
        ),
        (
            "CVAT-G01-DETECTION",
            lambda root: root.find("image/box/attribute").__setattr__("text", "official"),
            "Invalid team value",
        ),
        (
            "CVAT-G01-DETECTION",
            lambda root: root.find("image/box").set("xbr", "99999"),
            "Box outside image",
        ),
        (
            "CVAT-TRACK-G01-01",
            lambda root: root.find("track/box").set("frame", "999"),
            "Track frame outside sequence",
        ),
    ],
)
def test_invalid_labels_teams_boxes_and_tracks_fail(
    tmp_path: Path,
    task_id: str,
    mutation,
    message: str,
) -> None:
    exports_dir = tmp_path / "exports"
    _write_exports(exports_dir)
    _rewrite(exports_dir / f"{task_id}.xml", mutation)

    with pytest.raises(AnnotationValidationError, match=message):
        verify_annotations(ROOT, exports_dir)


def test_events_and_calibration_are_rejected_outside_allowed_tasks(tmp_path: Path) -> None:
    exports_dir = tmp_path / "exports"
    _write_exports(exports_dir)

    def add_event(root: ET.Element) -> None:
        event = ET.SubElement(root.find("image"), "tag", label="event")
        _attribute(event, "event_type", "shot")
        _attribute(event, "team", "team_a")

    _rewrite(exports_dir / "CVAT-G01-DETECTION.xml", add_event)
    with pytest.raises(AnnotationValidationError, match="Events are only allowed"):
        verify_annotations(ROOT, exports_dir)

    _write_exports(exports_dir)

    def add_line(root: ET.Element) -> None:
        line = ET.SubElement(
            root.find("image"),
            "polyline",
            label="pitch_line",
            points="0,0;10,10",
        )
        _attribute(line, "line_type", "touchline")

    _rewrite(exports_dir / "CVAT-G01-DETECTION.xml", add_line)
    with pytest.raises(AnnotationValidationError, match="Calibration outside subset"):
        verify_annotations(ROOT, exports_dir)


def test_pending_or_training_metadata_cannot_pass_human_gate(tmp_path: Path) -> None:
    exports_dir = tmp_path / "exports"
    _, metadata = _write_exports(exports_dir)
    metadata["dataset_role"] = "training"
    (exports_dir / "annotation_metadata_v1.json").write_text(
        json.dumps(metadata), encoding="utf-8"
    )

    with pytest.raises(AnnotationValidationError, match="training role"):
        verify_annotations(ROOT, exports_dir)

    metadata["dataset_role"] = "golden_eval"
    metadata["annotation_status"] = "ANNOTATIONS_PENDING"
    (exports_dir / "annotation_metadata_v1.json").write_text(
        json.dumps(metadata), encoding="utf-8"
    )
    with pytest.raises(AnnotationValidationError, match="not READY_TO_FREEZE"):
        verify_annotations(ROOT, exports_dir)


def test_freeze_manifest_requires_matching_private_package_metadata(tmp_path: Path) -> None:
    exports_dir = tmp_path / "exports"
    _, metadata = _write_exports(exports_dir)
    result = verify_annotations(ROOT, exports_dir)
    package_path = tmp_path / "golden_annotations_v1.0.0.zip"
    with zipfile.ZipFile(package_path, "w") as archive:
        archive.writestr("task_list.json", "{}\n")
    package_sha = hashlib.sha256(package_path.read_bytes()).hexdigest()

    benchmark = copy.deepcopy(load_json(ROOT / "data/manifests/internal_benchmark_v1.json"))
    benchmark["annotation_status"] = "FROZEN"
    benchmark["annotation_package"] = {
        "status": "FROZEN",
        "version": "1.0.0",
        "sha256": package_sha,
        "task_count": 12,
        "qa_status": "QA_PASS",
        "annotation_statistics": result["statistics"],
    }
    metadata["annotation_status"] = "FROZEN"
    metadata["freeze"] = {
        "package_version": "1.0.0",
        "package_sha256": package_sha,
        "frozen_at": "2026-09-03T12:00:00Z",
    }

    validate_freeze_manifest(
        benchmark,
        metadata,
        package_path,
        result["statistics"],
    )

    benchmark["annotation_package"]["sha256"] = "0" * 64
    with pytest.raises(AnnotationValidationError, match="SHA-256 mismatch"):
        validate_freeze_manifest(
            benchmark,
            metadata,
            package_path,
            result["statistics"],
        )
