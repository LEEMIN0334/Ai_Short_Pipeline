from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables."""

    postgres_url: str = Field(default="", alias="POSTGRES_URL")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    storage_backend: str = Field(default="local", alias="STORAGE_BACKEND")
    local_storage_root: str = Field(default=".local_storage", alias="LOCAL_STORAGE_ROOT")
    r2_account_id: str = Field(default="", alias="R2_ACCOUNT_ID")
    r2_access_key_id: str = Field(default="", alias="R2_ACCESS_KEY_ID")
    r2_secret_access_key: str = Field(default="", alias="R2_SECRET_ACCESS_KEY")
    r2_bucket: str = Field(default="ai-shorts-media", alias="R2_BUCKET")
    youtube_api_key: str = Field(default="", alias="YOUTUBE_API_KEY")

    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), extra="ignore")


def get_settings() -> Settings:
    return Settings()
