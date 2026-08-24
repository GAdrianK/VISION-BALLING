import pytest
from app.core.config import Settings, settings
from pydantic import ValidationError


def test_config_loading():
    assert settings.OPENAI_API_KEY is not None
    assert len(settings.OPENAI_API_KEY) > 0
    assert settings.HOST == "0.0.0.0"
    assert settings.PORT == 8000


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("VIDEO_BALL_TRACK_MAX_MISSING_FRAMES", -1),
        ("VIDEO_BALL_TRAJECTORY_LENGTH", 0),
        ("VIDEO_BALL_TRACK_MAX_DISTANCE_RATIO", 0),
        ("VIDEO_BALL_TRACK_MAX_DISTANCE_RATIO", 1.01),
    ],
)
def test_invalid_ball_tracking_settings_are_rejected(field: str, value: float):
    with pytest.raises(ValidationError) as error:
        Settings(**{field: value})

    assert field in str(error.value)
