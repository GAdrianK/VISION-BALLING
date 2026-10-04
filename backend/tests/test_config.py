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


def test_production_security_validation():
    # Production with wildcard origins must fail
    with pytest.raises(ValidationError) as exc:
        Settings(APP_ENV="production", ALLOWED_ORIGINS="*")
    assert "ALLOWED_ORIGINS cannot be '*'" in str(exc.value)

    # Production with empty origins must fail
    with pytest.raises(ValidationError) as exc:
        Settings(APP_ENV="production", ALLOWED_ORIGINS="")
    assert "ALLOWED_ORIGINS" in str(exc.value)

    # Invalid APP_ENV must fail
    with pytest.raises(ValidationError) as exc:
        Settings(APP_ENV="staging_insecure")
    assert "APP_ENV must be one of" in str(exc.value)

    # Production without DATABASE_URL must fail
    with pytest.raises(ValidationError) as exc:
        Settings(
            APP_ENV="production",
            ALLOWED_ORIGINS="https://app.vision-balling.com",
            DATABASE_URL="",
        )
    assert "DATABASE_URL is mandatory in production mode" in str(exc.value)

    # Production with SQLite DATABASE_URL must fail
    with pytest.raises(ValidationError) as exc:
        Settings(
            APP_ENV="production",
            ALLOWED_ORIGINS="https://app.vision-balling.com",
            DATABASE_URL="sqlite:///tmp/test.db",
        )
    assert "SQLite cannot be used in production mode" in str(exc.value)

    # Production with valid PostgreSQL DATABASE_URL and explicit origins succeeds
    prod_settings = Settings(
        APP_ENV="production",
        DATABASE_URL="postgresql://user:secret@ep-host.railway.internal:5432/railway",
        ALLOWED_ORIGINS="https://app.vision-balling.com, https://admin.vision-balling.com",
    )
    assert prod_settings.cors_allowed_origins == [
        "https://app.vision-balling.com",
        "https://admin.vision-balling.com",
    ]
    assert prod_settings.is_docs_enabled is False

    # Normalization of postgres:// to postgresql://
    pg_legacy = Settings(
        APP_ENV="development",
        DATABASE_URL="postgres://user:secret@localhost:5432/db",
    )
    assert pg_legacy.effective_database_url.startswith("postgresql://")


def test_docs_toggle_behavior():
    dev_settings = Settings(APP_ENV="development")
    assert dev_settings.is_docs_enabled is True

    prod_settings = Settings(
        APP_ENV="production",
        DATABASE_URL="postgresql://user:secret@ep-host.railway.internal:5432/railway",
        ALLOWED_ORIGINS="https://app.vision-balling.com",
        ENABLE_DOCS=True,
    )
    assert prod_settings.is_docs_enabled is True
