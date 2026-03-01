# src/sab_core/config.py
import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    SABR v2 Configuration Management.
    Loads variables from .env file or environment variables.
    """
    # --- AI & Engine ---
    ENGINE_TYPE: str = os.getenv("SABR_ENGINE_TYPE", "")
    DEPS_CLASS: str = os.getenv("SABR_DEPS_CLASS", "")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "your-key-here")
    DEFAULT_MODEL: str = os.getenv("SABR_DEFAULT_MODEL", "gemini-3-flash-preview")
    GEMINI_API_VERSION: str = os.getenv("SABR_GEMINI_API_VERSION", "v1beta")
    GEMINI_MAX_OUTPUT_TOKENS: int = int(os.getenv("GEMINI_MAX_OUTPUT_TOKENS", "32768"))
    GEMINI_UNAVAILABLE_RETRIES: int = int(os.getenv("SABR_GEMINI_UNAVAILABLE_RETRIES", "2"))
    GEMINI_UNAVAILABLE_RETRY_BACKOFF_SECONDS: float = float(
        os.getenv("SABR_GEMINI_UNAVAILABLE_RETRY_BACKOFF_SECONDS", "2.0")
    )
    SABR_MEMORY_DIR: str = os.getenv("SABR_MEMORY_DIR",  "default")

    # --- Observability ---
    SABR_DEBUG_LEVEL: str = os.getenv("SABR_DEBUG_LEVEL",  "default")
    PRODUCTION_MODE: bool = os.getenv("PRODUCTION_MODE", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    # 📡 Network Configuration (If you need a proxy)
    HTTPS_PROXY: str = os.getenv("HTTPS_PROXY", "")
    HTTP_PROXY: str = os.getenv("HTTP_PROXY", "")
    SABR_USE_OUTBOUND_PROXY: bool = os.getenv("SABR_USE_OUTBOUND_PROXY", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    SABR_FRONTEND_ORIGINS: str = os.getenv(
        "SABR_FRONTEND_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,https://sabr.yiming-zhang.com",
    )
    FRONTEND_DIST_DIR: str = os.getenv(
        "SABR_FRONTEND_DIST_DIR",
        os.path.join(os.getcwd(), "frontend", "dist"),
    )
    FRONTEND_ASSETS_DIR: str = os.getenv(
        "SABR_FRONTEND_ASSETS_DIR",
        os.path.join(os.getcwd(), "frontend", "dist", "assets"),
    )
    FRONTEND_INDEX_FILE: str = os.getenv(
        "SABR_FRONTEND_INDEX_FILE",
        os.path.join(os.getcwd(), "frontend", "dist", "index.html"),
    )

    # Tell pydantic to look for these in the .env file
    model_config = SettingsConfigDict(
        env_file=".env", 
        extra="ignore",
        env_file_encoding='utf-8'
    )

# Initialize a global settings instance
settings = Settings()
