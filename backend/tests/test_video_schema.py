from app.video_analysis.schemas import (
    AnalysisResult,
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
    assert payload["schema_version"] == "1.1.0"
    assert payload["status"] == "completed"
    assert payload["detections"] == []


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
    assert restored.pipeline.tracker_name == "none"
