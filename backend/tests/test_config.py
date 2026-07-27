from app.core.config import settings

def test_config_loading():
    assert settings.OPENAI_API_KEY is not None
    assert len(settings.OPENAI_API_KEY) > 0
    assert settings.HOST == "0.0.0.0"
    assert settings.PORT == 8000
