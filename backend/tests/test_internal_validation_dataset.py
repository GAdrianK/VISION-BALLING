from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.verify_internal_validation_dataset import (  # noqa: E402
    EXPECTED_CLASSES,
    EXPECTED_EVENTS,
    EXPECTED_IDS,
    EXPECTED_SEQUENCE_IDS,
    EXPECTED_TEAMS,
    verify_structure,
)

MANIFESTS = ROOT / "data/manifests"


def _json(name: str) -> dict:
    return json.loads((MANIFESTS / name).read_text(encoding="utf-8"))


def _inventory() -> list[dict[str, str]]:
    with (MANIFESTS / "golden_frames_v1.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        return list(csv.DictReader(handle))


def _sha256(path: Path) -> str:
    content = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(content).hexdigest()


def test_internal_dataset_verifier_reports_pending_annotations() -> None:
    result = verify_structure(ROOT)

    assert result["status"] == "STRUCTURE_PASS"
    assert result["annotation_status"] == "ANNOTATIONS_PENDING"
    assert result["total_unique"] == 950
    assert result["tracking_sequence_count"] == 6
    assert result["calibration_count"] == 30


def test_golden_manifest_version_ready_count_and_hashes() -> None:
    manifest = _json("golden_videos_v1.json")

    assert manifest["manifest_version"] == "1.1.0"
    assert [video["id"] for video in manifest["videos"]] == list(EXPECTED_IDS)
    assert all(video["status"] == "READY" for video in manifest["videos"])
    assert all(len(video["sha256"]) == 64 for video in manifest["videos"])


def test_frame_inventory_identity_bounds_timestamps_and_eval_role() -> None:
    rows = _inventory()
    videos = {
        video["id"]: video for video in _json("golden_videos_v1.json")["videos"]
    }
    uids = [row["frame_uid"] for row in rows]
    pairs = [(row["golden_id"], int(row["frame_index"])) for row in rows]

    assert len(rows) == 950
    assert len(set(uids)) == len(uids)
    assert len(set(pairs)) == len(pairs)
    assert pairs == sorted(pairs)
    assert all(row["dataset_role"] == "golden_eval" for row in rows)
    assert all(row["annotation_status"] == "PENDING" for row in rows)
    assert all(row["selection_role"] in {"sparse", "tracking", "sparse+tracking"} for row in rows)
    for row in rows:
        video = videos[row["golden_id"]]
        frame_index = int(row["frame_index"])
        assert row["frame_uid"] == f"{row['golden_id']}:{frame_index:08d}"
        assert 0 <= frame_index < video["frame_count"]
        assert abs(float(row["timestamp_seconds"]) - frame_index / video["fps"]) <= 1e-8
        assert row["golden_sha256"] == video["sha256"]


def test_tracking_sequences_count_distribution_non_overlap_and_duration() -> None:
    manifest = _json("tracking_sequences_v1.json")
    sequences = manifest["sequences"]

    assert manifest["dataset_role"] == "golden_eval"
    assert [sequence["sequence_id"] for sequence in sequences] == list(
        EXPECTED_SEQUENCE_IDS
    )
    assert Counter(sequence["golden_id"] for sequence in sequences) == Counter(
        {golden_id: 2 for golden_id in EXPECTED_IDS}
    )
    frames_by_golden: dict[str, set[int]] = defaultdict(set)
    for sequence in sequences:
        frames = set(range(sequence["start_frame"], sequence["end_frame"] + 1))
        assert frames_by_golden[sequence["golden_id"]].isdisjoint(frames)
        frames_by_golden[sequence["golden_id"]].update(frames)
        assert len(frames) == sequence["frame_count"]
        assert abs(sequence["frame_count"] / sequence["fps"] - 2.0) <= (
            1 / sequence["fps"]
        )


def test_calibration_subset_is_inside_inventory() -> None:
    inventory_uids = {row["frame_uid"] for row in _inventory()}
    frames = _json("calibration_frames_v1.json")["frames"]

    assert len(frames) == 30
    assert len({frame["frame_uid"] for frame in frames}) == 30
    assert {frame["frame_uid"] for frame in frames} <= inventory_uids
    assert Counter(frame["golden_id"] for frame in frames) == Counter(
        {golden_id: 10 for golden_id in EXPECTED_IDS}
    )


def test_annotation_schema_class_team_event_and_calibration_enums() -> None:
    schema = _json("annotation_schema_v1.json")
    classes = [label["name"] for label in schema["object_labels"]]

    assert len(classes) == len(set(classes))
    assert set(classes) == EXPECTED_CLASSES
    assert set(schema["attributes"]["team"]["values"]) == EXPECTED_TEAMS
    assert set(schema["events"]["values"]) == EXPECTED_EVENTS
    assert set(schema["calibration"]) >= {"pitch_line", "pitch_keypoint"}


def test_benchmark_is_eval_only_and_references_frozen_versions() -> None:
    benchmark = _json("internal_benchmark_v1.json")
    golden_manifest = _json("golden_videos_v1.json")

    assert benchmark["benchmark_version"] == "1.0.0"
    assert benchmark["dataset_role"] == "golden_eval"
    assert set(benchmark["partitions"]) == {"golden_eval"}
    assert benchmark["golden_manifest"]["version"] == "1.1.0"
    assert benchmark["frame_inventory"]["row_count"] == 950
    assert benchmark["tracking_sequences"]["sequence_count"] == 6
    assert benchmark["calibration_frames"]["frame_count"] == 30
    assert benchmark["annotation_package"]["status"] == "PENDING"
    assert benchmark["annotation_package"]["version"] is None
    assert benchmark["annotation_package"]["sha256"] is None
    assert [asset["golden_id"] for asset in benchmark["golden_assets"]] == list(
        EXPECTED_IDS
    )
    assert [asset["sha256"] for asset in benchmark["golden_assets"]] == [
        video["sha256"] for video in golden_manifest["videos"]
    ]

    for key in (
        "golden_manifest",
        "frame_inventory",
        "tracking_sequences",
        "calibration_frames",
        "annotation_schema",
        "split_policy",
        "qa_policy",
    ):
        reference = benchmark[key]
        assert _sha256(ROOT / reference["path"]) == reference["sha256"]
