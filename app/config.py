from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env from repository root
_root_env = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(_root_env)


def _resolve_face_database_path() -> Path:
    env_val = os.getenv("FACE_DATABASE_PATH")
    if env_val:
        return Path(env_val)
    # Default to existing face_database.json if present
    repo_root = Path(__file__).resolve().parents[1]
    nested_path = repo_root / "face_recognition" / "face_data" / "face_database.json"
    if nested_path.exists():
        return nested_path
    local_path = repo_root / "face_data" / "face_database.json"
    return local_path


def _resolve_anomaly_model_path() -> Path:
    env_val = os.getenv("ANOMALY_MODEL_PATH")
    if env_val:
        return Path(env_val)
    repo_root = Path(__file__).resolve().parents[1]
    artifact_path = repo_root / "ml" / "monitoring" / "artifacts" / "monitoring_isolation_forest.joblib"
    return artifact_path


class Settings(BaseSettings):
    app_name: str = "ai-services-api"
    app_version: str = "1.0.0"
    project_name: str = "Secure Digital Document Management System"

    # Anomaly Detection
    anomaly_model_path: Path = Field(
        default_factory=_resolve_anomaly_model_path
    )

    # Authentication
    ai_services_api_key: str | None = Field(
        default_factory=lambda: os.getenv("AI_SERVICES_API_KEY")
    )

    # Face Recognition
    face_encryption_key: str | None = Field(
        default_factory=lambda: os.getenv("FACE_ENCRYPTION_KEY")
    )
    face_database_path: Path = Field(
        default_factory=_resolve_face_database_path
    )
    face_max_upload_size_mb: int = Field(
        default_factory=lambda: int(os.getenv("FACE_MAX_UPLOAD_SIZE_MB", "5"))
    )
    face_similarity_threshold: float = Field(
        default_factory=lambda: float(os.getenv("FACE_SIMILARITY_THRESHOLD", "0.5"))
    )

    # Semantic Search
    qdrant_url: str = Field(
        default_factory=lambda: os.getenv("QDRANT_URL", "http://localhost:6333")
    )
    collection_name: str = Field(
        default_factory=lambda: os.getenv("COLLECTION_NAME", "document_chunks")
    )
    model_name: str = Field(
        default_factory=lambda: os.getenv("MODEL_NAME", "BAAI/bge-m3")
    )
    vector_dimension: int = Field(
        default_factory=lambda: int(os.getenv("VECTOR_DIMENSION", "1024"))
    )
    chunk_size: int = Field(
        default_factory=lambda: int(os.getenv("CHUNK_SIZE", "500"))
    )
    chunk_overlap: int = Field(
        default_factory=lambda: int(os.getenv("CHUNK_OVERLAP", "100"))
    )
    max_top_k: int = Field(
        default_factory=lambda: int(os.getenv("MAX_TOP_K", "10"))
    )
    allowed_file_extensions: str = Field(
        default_factory=lambda: os.getenv(
            "ALLOWED_FILE_EXTENSIONS",
            ".pdf,.docx,.doc,.txt,.csv,.xlsx,.pptx,.jpg,.jpeg,.png,.webp,.tif,.tiff",
        )
    )
    max_file_size_mb: int = Field(
        default_factory=lambda: int(os.getenv("MAX_FILE_SIZE_MB", "20"))
    )

    # CORS configuration (empty list by default, disabling permissive CORS)
    cors_origins: List[str] = Field(
        default_factory=lambda: [
            origin.strip()
            for origin in os.getenv("CORS_ORIGINS", "").split(",")
            if origin.strip()
        ]
    )

    # Twilio SMS Provider
    twilio_account_sid: str | None = Field(
        default_factory=lambda: os.getenv("TWILIO_ACCOUNT_SID")
    )
    twilio_auth_token: str | None = Field(
        default_factory=lambda: os.getenv("TWILIO_AUTH_TOKEN")
    )
    twilio_from_number: str | None = Field(
        default_factory=lambda: os.getenv("TWILIO_FROM_NUMBER")
    )

    # SMTP Email Provider
    smtp_host: str | None = Field(
        default_factory=lambda: os.getenv("SMTP_HOST")
    )
    smtp_port: int = Field(
        default_factory=lambda: int(os.getenv("SMTP_PORT", "587"))
    )
    smtp_username: str | None = Field(
        default_factory=lambda: os.getenv("SMTP_USERNAME")
    )
    smtp_password: str | None = Field(
        default_factory=lambda: os.getenv("SMTP_PASSWORD")
    )
    smtp_from_email: str | None = Field(
        default_factory=lambda: os.getenv("SMTP_FROM_EMAIL")
    )
    smtp_use_tls: bool = Field(
        default_factory=lambda: os.getenv("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes")
    )

    # Twilio Voice / AI Voice Agent Settings
    voice_agent_enabled: bool = Field(
        default_factory=lambda: os.getenv("VOICE_AGENT_ENABLED", "false").lower() in ("true", "1", "yes")
    )
    voice_twiml_url: str | None = Field(
        default_factory=lambda: os.getenv("VOICE_TWIML_URL")
    )

    model_config = SettingsConfigDict(
        env_prefix="",
        case_sensitive=False,
        protected_namespaces=("settings_",),
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
