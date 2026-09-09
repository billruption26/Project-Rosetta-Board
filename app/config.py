"""Configuration settings and environment loaders for Project Rosetta Board."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
APP_DIR = BASE_DIR / "app"
DATA_DIR = APP_DIR / "data"
TAXONOMY_PATH = DATA_DIR / "taxonomy_rules.json"
SAMPLES_DIR = DATA_DIR / "sample_storyboards"
OUTPUTS_DIR = BASE_DIR / "outputs"

# Ensure runtime directories exist
OUTPUTS_DIR.mkdir(exist_ok=True, parents=True)
SAMPLES_DIR.mkdir(exist_ok=True, parents=True)

# Load environment variables
load_dotenv(BASE_DIR / ".env")


class Config:
    """Project-wide configuration."""
    
    # Gemini / Google GenAI
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))
    
    # Robust project and location extraction
    _raw_project = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
    if " " in _raw_project:
        _parts = _raw_project.split()
        GCP_PROJECT: str = _parts[0]
        for _part in _parts[1:]:
            if "=" in _part:
                _k, _v = _part.split("=", 1)
                os.environ.setdefault(_k, _v)
    else:
        GCP_PROJECT: str = _raw_project

    USE_VERTEXAI: bool = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "True" if GCP_PROJECT else "False").lower() in ("true", "1", "yes")
    GCP_LOCATION: str = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1").strip().split()[0]
    
    # Model Selection (defaults to gemini-2.5-flash for fast multimodal reasoning)
    DEFAULT_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip().split()[0]
    PRO_MODEL: str = os.getenv("GEMINI_PRO_MODEL", "gemini-2.5-pro").strip().split()[0]
    
    # ClickHouse Configuration
    CLICKHOUSE_HOST: str = os.getenv("CLICKHOUSE_HOST", "localhost")
    CLICKHOUSE_PORT: int = int(os.getenv("CLICKHOUSE_PORT", "8123"))
    CLICKHOUSE_USER: str = os.getenv("CLICKHOUSE_USER", "default")
    CLICKHOUSE_PASSWORD: str = os.getenv("CLICKHOUSE_PASSWORD", "")
    CLICKHOUSE_DATABASE: str = os.getenv("CLICKHOUSE_DATABASE", "rosetta_board")
    CLICKHOUSE_SECURE: bool = os.getenv("CLICKHOUSE_SECURE", "False").lower() in ("true", "1", "yes")
    
    # Parallel API
    PARALLEL_API_KEY: str = os.getenv("PARALLEL_API_KEY", "")


config = Config()
