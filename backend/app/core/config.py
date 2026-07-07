import warnings

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Money Manager"
    database_url: str = "sqlite:///./money_manager.db"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60 * 24 * 7
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    cors_origin_regex: str = r"https?://(localhost|127\.0\.0\.1)(:\d+)?$"
    frontend_url: str = "http://localhost:3000"
    upload_dir: str = "uploads"
    resend_api_key: str = ""
    resend_from_email: str = "Finlio <onboarding@resend.dev>"
    finnhub_api_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

if settings.secret_key == "change-me-in-production":
    warnings.warn(
        "SECRET_KEY is using the development default. Set a unique value before deployment.",
        RuntimeWarning,
        stacklevel=2,
    )
