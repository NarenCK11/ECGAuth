"""Application settings, loaded from environment variables / `.env`.

No secret has a usable default: JWT_SECRET and admin credentials must be supplied.
"""
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "mysql+pymysql://ecgauth:ecgauth@localhost:3306/ecgauth?charset=utf8mb4"

    # Auth
    jwt_secret: str = Field(min_length=32)
    jwt_algorithm: str = "HS256"
    session_minutes: int = 30
    admin_session_minutes: int = 30
    cookie_secure: bool = False          # set true when served over HTTPS
    cookie_samesite: str = "lax"

    # Bootstrap admin (hashed on first start; never stored in plaintext)
    admin_username: str = ""
    admin_password: str = ""

    # HTTP
    cors_origins: str = "http://localhost:5173"

    # ECG uploads
    max_upload_bytes: int = 5 * 1024 * 1024
    login_max_failures: int = 5          # per user, within the window below
    login_lockout_minutes: int = 15

    # ML
    model_dir: Path = BACKEND_DIR / "app" / "ml" / "artifacts"
    load_model_on_startup: bool = True

    @field_validator("cors_origins")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
