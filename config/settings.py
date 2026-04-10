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

    # Hiring Cafe scrape pacing (helps when rate-limited)
    # Random "human" pauses (seconds) — each call picks a new value in [min, max] (e.g. 16s then 25s)
    HIRING_CAFE_RANDOM_PAUSE_MIN_SEC: float = 10.0
    HIRING_CAFE_RANDOM_PAUSE_MAX_SEC: float = 50.0
    # Between infinite-scroll steps (each scroll gets a new random wait; keep < random pause above or runs get very long)
    HIRING_CAFE_SCROLL_STEP_MIN_SEC: float = 1.5
    HIRING_CAFE_SCROLL_STEP_MAX_SEC: float = 8.0
    # Step 2: random pause after each job (many pages — defaults shorter than Step 1; set 10–50 to match Step 1)
    HIRING_CAFE_STEP2_PAUSE_MIN_SEC: float = 2.0
    HIRING_CAFE_STEP2_PAUSE_MAX_SEC: float = 8.0
    # After driver.get(viewjob/...) — random settle before DOM reads (new draw each job)
    HIRING_CAFE_STEP2_PAGE_SETTLE_MIN_SEC: float = 2.0
    HIRING_CAFE_STEP2_PAGE_SETTLE_MAX_SEC: float = 5.5
    # Process remaining jobs in random order (same checkpoint/resume; reduces strict ID order)
    HIRING_CAFE_STEP2_SHUFFLE_PENDING: bool = False
    # Every N completed jobs, take a longer pause (0 = disabled). Helps mimic breaks + spread load.
    HIRING_CAFE_STEP2_BREAK_EVERY_N: int = 0
    HIRING_CAFE_STEP2_LONG_BREAK_MIN_SEC: float = 30.0
    HIRING_CAFE_STEP2_LONG_BREAK_MAX_SEC: float = 120.0
    HIRING_CAFE_STEP2_MOUSE_JITTER: bool = True
    # Full pipeline: sleep random 0..max seconds before pre-flight (stagger scheduled runs)
    HIRING_CAFE_PIPELINE_START_JITTER_MAX_SEC: float = 0.0

    # Email Reporting Setup
    SMTP_SERVER: str | None = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    REPORT_RECEIVER_EMAIL: str | None = None
    SENDER_EMAIL: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def chrome_profile_path(self) -> str:
        return str(Path(self.CHROME_USER_DATA_DIR).resolve())

settings = Settings()
