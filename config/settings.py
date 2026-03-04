import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # Database
    DUCKDB_PATH: str = "data/job_engine.duckdb"
    
    # Browser
    CHROME_USER_DATA_DIR: str = "./chrome_profile"
    HEADLESS: bool = False

    # Proxy
    PROXY_URL: str | None = None

    # Safety
    MAX_APPLICATIONS_PER_RUN: int = 200  # Effectively unlimited
    SUBMISSION_COOLDOWN_SECONDS: int = 60
    DRY_RUN: bool = False
    # Keep browser open after run (useful for debugging)
    KEEP_BROWSER_OPEN: bool = False
    # How long to wait after clicking submit for navigation (seconds)
    SUBMIT_POST_CLICK_WAIT: int = 15

    # Authentication
    AUTH_URL: str | None = None
    AUTH_USERNAME: str | None = None
    AUTH_PASSWORD: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def chrome_profile_path(self) -> str:
        return str(Path(self.CHROME_USER_DATA_DIR).resolve())

settings = Settings()
