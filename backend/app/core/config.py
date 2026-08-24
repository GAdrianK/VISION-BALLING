import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Chemin vers la racine du dossier backend
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
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
    VIDEO_FRAME_INTERVAL: int = 10
    VIDEO_FRAME_SAMPLE_RATE: int = 0
    VIDEO_DETECTOR: str = "hog"
    VIDEO_MODEL_PATH: str = "yolo11n.pt"
    VIDEO_MODEL_PROFILE: str = "coco"
    VIDEO_CONFIDENCE_THRESHOLD: float = 0.45
    VIDEO_PERSON_CONFIDENCE_THRESHOLD: float = 0.45
    VIDEO_BALL_CONFIDENCE_THRESHOLD: float = 0.25
    VIDEO_MODEL: str = "opencv-hog"
    VIDEO_DEVICE: str = "cpu"
    VIDEO_TRACKING_ENABLED: bool = True
    VIDEO_TRACKER: str = "iou"
    VIDEO_PRESERVE_AUDIO: bool = True
    VIDEO_MAX_PROCESSING_SECONDS: float = 0
    VIDEO_KEEP_TEMPORARY_FILES: bool = False

    @property
    def video_frame_sample_rate(self) -> int:
        return self.VIDEO_FRAME_SAMPLE_RATE or self.VIDEO_FRAME_INTERVAL

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

    # Recherche le fichier .env dans le dossier racine du backend
    model_config = SettingsConfigDict(
        env_file=os.path.join(BASE_DIR, ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
