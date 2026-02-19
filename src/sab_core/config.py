import os
from dotenv import load_dotenv

# Load variables from .env file into os.environ
load_dotenv()

class Config:
    # Use os.getenv with a fallback default for safety
    MEMORY_DIR = os.getenv("SABR_MEMORY_DIR", "data/memories")
    DEBUG_LEVEL = os.getenv("SABR_DEBUG_LEVEL", "INFO")

settings = Config()