"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://f1user:f1pass@localhost:5432/f1data")
    #ERGAST_BASE_URL: str = os.getenv("ERGAST_BASE_URL", "https://ergast.com/api/f1") # Old API, replaced with below as it was depricated
    ERGAST_BASE_URL: str = os.getenv("ERGAST_BASE_URL", "https://api.jolpi.ca/ergast/f1/")
    OPENF1_BASE_URL: str = os.getenv("OPENF1_BASE_URL", "https://api.openf1.org/v1")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    BATCH_SIZE: int = int(os.getenv("BATCH_SIZE", "500"))
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    RETRY_BACKOFF: float = float(os.getenv("RETRY_BACKOFF", "2.0"))


settings = Settings()
