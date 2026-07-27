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
    assert payload["schema_version"] == "1.0.0"
    assert payload["status"] == "completed"
    assert payload["detections"] == []
