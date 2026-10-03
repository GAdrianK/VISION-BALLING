import pytest
from app.core.config import Settings, settings
from pydantic import ValidationError


def test_config_loading():
    assert settings.OPENAI_API_KEY is not None
    assert len(settings.OPENAI_API_KEY) > 0
    assert settings.HOST == "0.0.0.0"
    assert settings.PORT == 8000
    assert settings.VIDEO_RETAIN_SOURCE is True
    assert settings.VIDEO_MODE == "QUALITY"
    assert settings.VIDEO_DETECTOR == "rfdetr"
    assert settings.VIDEO_DEVICE == "cuda"
    assert settings.VIDEO_TRACKER == "botsort"
    assert settings.VIDEO_FRAME_SAMPLE_RATE == 1
    assert settings.VIDEO_MODEL == "rf-detr-small"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("VIDEO_FRAME_SAMPLE_RATE", 0),
        ("VIDEO_BALL_TRACK_MAX_MISSING_SECONDS", -0.01),
        ("VIDEO_BALL_TRACK_MAX_MISSING_SECONDS", float("inf")),
        ("VIDEO_BALL_TRAJECTORY_SECONDS", 0),
        ("VIDEO_BALL_TRAJECTORY_SECONDS", float("inf")),
        ("VIDEO_BALL_TRACK_MAX_DISTANCE_RATIO", 0),
        ("VIDEO_BALL_TRACK_MAX_DISTANCE_RATIO", 1.01),
    ],
)
def test_invalid_video_settings_are_rejected(field: str, value: float):
    with pytest.raises(ValidationError) as error:
        Settings(**{field: value})

    assert field in str(error.value)
