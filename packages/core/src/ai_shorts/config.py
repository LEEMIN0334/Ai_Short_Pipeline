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
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.0-flash", alias="GEMINI_MODEL")
    typecast_api_key: str = Field(default="", alias="TYPECAST_API_KEY")
    typecast_voice_id: str = Field(default="", alias="TYPECAST_VOICE_ID")
    typecast_model: str = Field(default="ssfm-v30", alias="TYPECAST_MODEL")
    youtube_api_key: str = Field(default="", alias="YOUTUBE_API_KEY")
    reddit_client_id: str = Field(default="", alias="REDDIT_CLIENT_ID")
    reddit_client_secret: str = Field(default="", alias="REDDIT_CLIENT_SECRET")
    reddit_user_agent: str = Field(default="ai-shorts-studio/0.1", alias="REDDIT_USER_AGENT")

    model_config = SettingsConfigDict(env_file=(".env", "../../.env"), extra="ignore")


def get_settings() -> Settings:
    return Settings()
