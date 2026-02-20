# src/sab_core/config.py
import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    SABR v2 Configuration Management.
    Loads variables from .env file or environment variables.
    """
    # --- AI & Engine ---
    ENGINE_TYPE: str = "aiida" 
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "your-key-here")
    
    # --- AiiDA Specifics (From your .env) ---
    # Used by AiiDADeps to determine the database profile
    SABR_AIIDA_PROFILE: str = os.getenv("SABR_AIIDA_PROFILE",  "default")
    SABR_MEMORY_DIR: str = os.getenv("SABR_MEMORY_DIR",  "default")

    # --- Observability ---
    SABR_DEBUG_LEVEL: str = os.getenv("SABR_DEBUG_LEVEL",  "default")

    # 📡 Network Configuration (If you need a proxy)
    HTTPS_PROXY: str = os.getenv("HTTPS_PROXY", "")
    HTTP_PROXY: str = os.getenv("HTTP_PROXY", "")

    # Tell pydantic to look for these in the .env file
    model_config = SettingsConfigDict(
        env_file=".env", 
        extra="ignore",
        env_file_encoding='utf-8'
    )

# Initialize a global settings instance
settings = Settings()