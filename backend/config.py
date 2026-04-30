"""
Configuration management for Smart Health Assistant backend
Handles environment variables, settings, and configuration
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
import os
from typing import Optional, List

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables
    
    Usage:
        from config import get_settings
        settings = get_settings()
        print(settings.debug)  # Get debug mode
    """
    
    # ========================================================================
    # FASTAPI & SERVER CONFIGURATION
    # ========================================================================
    
    APP_NAME: str = "Smart Health Assistant"
    APP_VERSION: str = "1.0.0"
    ENV: str = os.getenv("ENV", "development")
    DEBUG: bool = os.getenv("DEBUG", "True").lower() == "true"
    
    # Server URLs
    BACKEND_URL: str = os.getenv("BACKEND_URL", "http://localhost:8000")
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:3000")
    
    # ========================================================================
    # DATABASE CONFIGURATION (Optional)
    # ========================================================================
    
    DATABASE_URL: Optional[str] = os.getenv(
        "DATABASE_URL",
        "sqlite:///./smart_health.db"
    )
    DATABASE_ECHO: bool = os.getenv("DATABASE_ECHO", "False").lower() == "true"
    
    # ========================================================================
    # AI / GOOGLE APIs - OPTIONAL
    # ========================================================================
    
    # Open Source LLM Configuration (e.g., Ollama, LocalAI)
    # Default to localhost Ollama instance
    LLM_API_URL: str = os.getenv("LLM_API_URL", "http://localhost:11434/api/generate")
    LLM_MODEL_NAME: str = os.getenv("LLM_MODEL_NAME", "llama2")  # or mistral, etc.
    
    # Gemini / Google Cloud configuration (optional)
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
    GOOGLE_APPLICATION_CREDENTIALS: Optional[str] = os.getenv(
        "GOOGLE_APPLICATION_CREDENTIALS"
    )
    GOOGLE_CLOUD_PROJECT_ID: Optional[str] = os.getenv(
        "GOOGLE_CLOUD_PROJECT_ID"
    )
    
    # Google Maps API Key (not needed - using OpenStreetMap)
    GOOGLE_MAPS_API_KEY: str = os.getenv("GOOGLE_MAPS_API_KEY", "")
    
    # ========================================================================
    # AUTHENTICATION & SECURITY
    # ========================================================================
    
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY",
        "change-this-in-production-use-random-string"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # ========================================================================
    # EMERGENCY HOTLINES
    # ========================================================================
    
    EMERGENCY_HOTLINE_INDIA: str = os.getenv("EMERGENCY_HOTLINE_INDIA", "108")
    EMERGENCY_HOTLINE_INTERNATIONAL: str = os.getenv(
        "EMERGENCY_HOTLINE_INTERNATIONAL",
        "+911234567890"
    )
    
    # ========================================================================
    # LOGGING CONFIGURATION
    # ========================================================================
    
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "logs/app.log")
    
    # ========================================================================
    # CORS - ALLOWED ORIGINS
    # ========================================================================
    
    ALLOWED_ORIGINS: list = [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://yourdomain.com",
    ]
    
    # ========================================================================
    # REDIS CONFIGURATION (Optional)
    # ========================================================================
    
    REDIS_URL: Optional[str] = os.getenv("REDIS_URL", None)
    REDIS_ENABLED: bool = os.getenv("REDIS_ENABLED", "False").lower() == "true"
    
    # ========================================================================
    # OPENSTREETMAP CONFIGURATION (FREE - No API Key!)
    # ========================================================================
    
    OPENSTREETMAP_ENABLED: bool = os.getenv("OPENSTREETMAP_ENABLED", "True").lower() == "true"
    OVERPASS_API_URL: str = os.getenv(
        "OVERPASS_API_URL",
        "https://overpass-api.de/api/interpreter"
    )
    NOMINATIM_API_URL: str = os.getenv(
        "NOMINATIM_API_URL",
        "https://nominatim.openstreetmap.org"
    )
    
    # ========================================================================
    # HEALTHCARE LOCATOR SETTINGS
    # ========================================================================
    
    DEFAULT_SEARCH_RADIUS_KM: float = float(
        os.getenv("DEFAULT_SEARCH_RADIUS_KM", "5")
    )
    DEFAULT_MAX_RESULTS: int = int(
        os.getenv("DEFAULT_MAX_RESULTS", "10")
    )
    HOSPITAL_SEARCH_ENABLED: bool = os.getenv("HOSPITAL_SEARCH_ENABLED", "True").lower() == "true"
    CLINIC_SEARCH_ENABLED: bool = os.getenv("CLINIC_SEARCH_ENABLED", "True").lower() == "true"
    TELEMEDICINE_ENABLED: bool = os.getenv("TELEMEDICINE_ENABLED", "True").lower() == "true"
    
    class Config:
        """Pydantic configuration"""
        env_file = ".env"
        case_sensitive = True
        # Allow extra fields from .env that aren't defined above
        extra = "ignore"


# Singleton instance - use get_settings() function below
_settings: Optional[Settings] = None


@lru_cache()
def get_settings() -> Settings:
    """
    Get settings instance (singleton pattern)
    This function ensures only one Settings instance is created
    
    Usage:
        from config import get_settings
        settings = get_settings()
    
    Returns:
        Settings: Application configuration object
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# For quick imports
settings = get_settings()


# ============================================================================
# VALIDATION METHODS - Check settings are correct
# ============================================================================

def validate_required_settings() -> dict:
    """
    Validate that required settings are properly configured
    
    Returns:
        dict: Status of each required setting
    
    Note: Most settings are optional now since we use free OpenStreetMap
    """
    
    checks = {
        "SECRET_KEY": settings.SECRET_KEY != "change-this-in-production-use-random-string",
        "OPENSTREETMAP_ENABLED": settings.OPENSTREETMAP_ENABLED,
    }
    
    # Optional checks (don't fail if missing)
    optional_checks = {
        "GEMINI_API_KEY": bool(settings.GEMINI_API_KEY),
        "GOOGLE_MAPS_API_KEY": bool(settings.GOOGLE_MAPS_API_KEY),
    }
    
    missing_required = [key for key, value in checks.items() if not value]
    
    if missing_required:
        raise ValueError(
            f"Missing required settings: {', '.join(missing_required)}. "
            f"Please check your .env file."
        )
    
    return checks


if __name__ == "__main__":
    # Quick test: python config.py
    print("✅ Configuration loaded successfully!")
    print(f"App: {settings.APP_NAME} v{settings.APP_VERSION}")
    print(f"Environment: {settings.ENV}")
    print(f"Debug: {settings.DEBUG}")
    print(f"Database: {settings.DATABASE_URL}")
    print(f"CORS Origins: {settings.ALLOWED_ORIGINS}")
    print(f"OpenStreetMap Enabled: {settings.OPENSTREETMAP_ENABLED}")
    print(f"OpenStreetMap API: {settings.OVERPASS_API_URL}")