from app.video_analysis.schemas import (
    AnalysisJob,
    AnalysisResult,
    BallTrajectoryPoint,
    BoundingBox,
    JobStatus,
    PipelineMetadata,
    VideoMetadata,
)


def test_analysis_contract_serialization():
    result = AnalysisResult(
        analysis_id="analysis_test",
        match_id="match_test",
        status=JobStatus.COMPLETED,
        video=VideoMetadata(
            filename="match.mp4",
            duration_seconds=1,
            fps=25,
            width=640,
            height=360,
            frame_count=25,
        ),
        pipeline=PipelineMetadata(
            detector="fake-detector",
            frame_interval=5,
            device="cpu",
        ),
    )
    payload = result.model_dump(mode="json")
    assert payload["schema_version"] == "1.2.0"
    assert payload["status"] == "completed"
    assert payload["detections"] == []
    assert payload["ball_trajectory"] == []

    other = AnalysisResult.model_validate(
        result.model_dump(exclude={"ball_trajectory"})
    )
    assert result.ball_trajectory is not other.ball_trajectory


def test_ball_trajectory_point_contains_source_position_and_state():
    point = BallTrajectoryPoint(
        frame_index=5,
        timestamp_seconds=0.5,
        state="predicted",
        bbox=BoundingBox(x1=10, y1=20, x2=18, y2=28),
        center={"x": 14, "y": 24},
    )

    payload = point.model_dump()
    assert payload["frame_index"] == 5
    assert payload["timestamp_seconds"] == 0.5
    assert payload["bbox"] == {"x1": 10, "y1": 20, "x2": 18, "y2": 28}
    assert payload["center"] == {"x": 14.0, "y": 24.0}
    assert payload["state"] == "predicted"
    assert payload["confidence"] is None


def test_sprint_one_payload_remains_readable():
    payload = {
        "schema_version": "1.0.0",
        "analysis_id": "legacy",
        "match_id": "legacy-match",
        "status": "completed",
        "video": {
            "filename": "legacy.mp4",
            "duration_seconds": 1,
            "fps": 25,
            "width": 640,
            "height": 360,
            "frame_count": 25,
        },
        "pipeline": {
            "version": "0.1.0",
            "detector": "opencv-hog",
            "frame_interval": 10,
            "device": "cpu",
        },
    }
    restored = AnalysisResult.model_validate(payload)
    assert restored.schema_version == "1.0.0"
    assert restored.pipeline.pipeline_version == "0.1.0"
    assert restored.pipeline.tracker_name == "none"
    assert restored.ball_trajectory == []


def test_legacy_job_without_analysis_key_remains_readable():
    restored = AnalysisJob.model_validate(
        {
            "schema_version": "1.1.0",
            "analysis_id": "analysis_legacy",
            "match_id": "match_legacy",
            "status": "completed",
            "source_sha256": "legacy-source-sha",
        }
    )

    assert restored.source_sha256 == "legacy-source-sha"
    assert restored.analysis_key is None
    assert restored.pipeline is None
