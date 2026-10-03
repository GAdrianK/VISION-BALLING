from __future__ import annotations

import os
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Chemin vers la racine du dossier backend
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    APP_ENV: str = Field(default="development")
    PUBLIC_UPLOAD_ENABLED: bool = Field(default=False)
    REQUIRE_ANALYSIS_TOKEN: bool = Field(default=True)
    ENABLE_LEGACY_SQL_API: bool = Field(default=False)
    ENABLE_DOCS: bool | None = Field(default=None)
    MAX_CONCURRENT_ANALYSES: int = Field(default=1, ge=1)

    OPENAI_API_KEY: str = "mock-local-only"
    GEMINI_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    APISPORTS_KEY: str = ""
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    KNOWLEDGE_BASE_DIR: str = ""

    @property
    def gemini_key(self) -> str:
        # Préférer GEMINI_API_KEY puis GOOGLE_API_KEY
        key = self.GEMINI_API_KEY or self.GOOGLE_API_KEY or ""
        return key.strip()

    @property
    def openrouter_key(self) -> str:
        return self.OPENROUTER_API_KEY.strip()

    ALLOWED_ORIGINS: str = "*"

    @property
    def cors_allowed_origins(self) -> list[str]:
        raw = self.ALLOWED_ORIGINS.strip()
        if not raw:
            return []
        if raw == "*":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]

    @property
    def is_docs_enabled(self) -> bool:
        if self.ENABLE_DOCS is not None:
            return self.ENABLE_DOCS
        return self.APP_ENV != "production"

    RAW_DATA_DIR: str = ""
    PROCESSED_DATA_DIR: str = ""
    QDRANT_URL: str = ":memory:"
    QDRANT_COLLECTION_NAME: str = "football_intelligence"
    SQLITE_DB_PATH: str = ""
    VIDEO_UPLOAD_DIR: str = ""
    VIDEO_RESULT_DIR: str = ""
    VIDEO_ALLOWED_EXTENSIONS: str = "mp4,mov,mkv,avi,webm"
    VIDEO_MAX_SIZE_MB: int = 1024
    VIDEO_MAX_DURATION_SECONDS: float = 900
    VIDEO_MIN_WIDTH: int = 320
    VIDEO_MIN_HEIGHT: int = 240
    VIDEO_MIN_FREE_DISK_MB: int = 256
    VIDEO_FRAME_SAMPLE_RATE: int = Field(default=1, ge=1)
    VIDEO_MODE: str = "QUALITY"
    VIDEO_DETECTOR: str = "rfdetr"
    VIDEO_MODEL_PATH: str = ""
    VIDEO_MODEL_PROFILE: str = "football"
    VIDEO_CONFIDENCE_THRESHOLD: float = 0.35
    VIDEO_PERSON_CONFIDENCE_THRESHOLD: float = 0.35
    VIDEO_BALL_CONFIDENCE_THRESHOLD: float = 0.25
    VIDEO_MODEL: str = "rf-detr-small"
    VIDEO_DEVICE: str = "cuda"
    VIDEO_TRACKING_ENABLED: bool = True
    VIDEO_TRACKER: str = "botsort"
    VIDEO_BALL_TRACK_MAX_MISSING_SECONDS: float = Field(
        default=0.2, ge=0, allow_inf_nan=False
    )
    VIDEO_BALL_TRACK_MAX_DISTANCE_RATIO: float = Field(default=0.15, gt=0, le=1)
    VIDEO_BALL_TRAJECTORY_SECONDS: float = Field(
        default=0.5, gt=0, allow_inf_nan=False
    )
    VIDEO_PRESERVE_AUDIO: bool = True
    VIDEO_MAX_PROCESSING_SECONDS: float = 0
    VIDEO_KEEP_TEMPORARY_FILES: bool = False
    VIDEO_RETAIN_SOURCE: bool = True
    VIDEO_GIT_SHA: str = ""

    def get_kb_dir(self) -> str:
        if self.KNOWLEDGE_BASE_DIR:
            return self.KNOWLEDGE_BASE_DIR
        return os.path.abspath(os.path.join(BASE_DIR.parent, "knowledge_base"))

    def get_raw_data_dir(self) -> str:
        if self.RAW_DATA_DIR:
            return self.RAW_DATA_DIR
        return os.path.abspath(os.path.join(BASE_DIR, "data", "raw"))

    def get_processed_data_dir(self) -> str:
        if self.PROCESSED_DATA_DIR:
            return self.PROCESSED_DATA_DIR
        return os.path.abspath(os.path.join(BASE_DIR, "data", "processed"))

    def get_sqlite_db_path(self) -> str:
        if self.SQLITE_DB_PATH:
            return self.SQLITE_DB_PATH
        return os.path.abspath(os.path.join(BASE_DIR, "data", "parent_store.db"))

    @property
    def video_extensions(self) -> list[str]:
        return [
            extension.strip().lower().lstrip(".")
            for extension in self.VIDEO_ALLOWED_EXTENSIONS.split(",")
            if extension.strip()
        ]

    def get_video_upload_dir(self) -> str:
        return self.VIDEO_UPLOAD_DIR or str(BASE_DIR / "data" / "video_uploads")

    def get_video_result_dir(self) -> str:
        return self.VIDEO_RESULT_DIR or str(BASE_DIR / "data" / "video_results")

    def get_rfdetr_checkpoint_path(self) -> Path:
        if self.VIDEO_MODEL_PATH and self.VIDEO_MODEL_PATH.strip():
            return Path(self.VIDEO_MODEL_PATH.strip())
        env_ckpt = os.getenv("RFDETR_CHECKPOINT_PATH", "").strip()
        if env_ckpt:
            return Path(env_ckpt)
        if self.APP_ENV != "production":
            dev_candidate = Path(
                "/media/adriano/Windows/runs/detect/exp04_rfdetr_small_h250_960/checkpoint_best_total.pth"
            )
            if dev_candidate.is_file():
                return dev_candidate
        return Path("/opt/models/rfdetr/checkpoint_best_total.pth")

    @model_validator(mode="after")
    def validate_production_security(self) -> Settings:
        env = (self.APP_ENV or "").strip().lower()
        if env not in ("development", "test", "production"):
            raise ValueError(
                f"APP_ENV must be one of: 'development', 'test', 'production', got '{self.APP_ENV}'"
            )
        if env == "production":
            allowed = self.ALLOWED_ORIGINS.strip()
            if allowed == "*" or not allowed:
                raise ValueError(
                    "Production security violation: ALLOWED_ORIGINS cannot be '*' or empty in production mode. "
                    "Specify explicit allowed origin(s), e.g. 'https://app.vision-balling.com'."
                )
        return self

    # Recherche le fichier .env dans le dossier racine du backend
    model_config = SettingsConfigDict(
        env_file=os.path.join(BASE_DIR, ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
