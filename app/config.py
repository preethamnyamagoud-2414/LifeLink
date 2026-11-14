"""
LifeLink - Configuration Module
Supports environment-driven configuration for development, testing, and production.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Locate and load the root .env file
BASE_DIR = Path(__file__).resolve().parent.parent
env_file_path = BASE_DIR / ".env"
if env_file_path.exists():
    load_dotenv(dotenv_path=env_file_path)
else:
    load_dotenv()  # Fallback to system environment


class Config:
    """Base configuration shared across environments."""
    
    # Core Application Settings
    SECRET_KEY = os.getenv("SECRET_KEY", "lifelink-fallback-dev-secret-key-32chars-min")
    APP_NAME = os.getenv("APP_NAME", "LifeLink")
    APP_TAGLINE = os.getenv("APP_TAGLINE", "Smart Blood Donor and Emergency Blood Availability Portal")
    APP_URL = os.getenv("APP_URL", "http://127.0.0.1:5000")
    
    # Session Security Defaults
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours in seconds

    # Database Configuration (MySQL)
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.getenv("DB_PORT", 3306))
    DB_NAME = os.getenv("DB_NAME", "lifelink_db")
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    DB_CHARSET = os.getenv("DB_CHARSET", "utf8mb4")
    DB_CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", 2))
    DB_AUTOCOMMIT = os.getenv("DB_AUTOCOMMIT", "false").lower() in ("true", "1", "yes")

    @classmethod
    def get_db_config(cls) -> dict:
        """Returns MySQL connection parameters as a dictionary for PyMySQL."""
        return {
            "host": cls.DB_HOST,
            "port": cls.DB_PORT,
            "user": cls.DB_USER,
            "password": cls.DB_PASSWORD,
            "database": cls.DB_NAME,
            "charset": cls.DB_CHARSET,
            "connect_timeout": cls.DB_CONNECT_TIMEOUT,
            "autocommit": cls.DB_AUTOCOMMIT,
        }


class DevelopmentConfig(Config):
    """Configuration for local development."""
    DEBUG = True
    TESTING = False
    SESSION_COOKIE_SECURE = False  # Allows HTTP on localhost


class ProductionConfig(Config):
    """Configuration for production deployment."""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() in ("true", "1")

    @classmethod
    def validate(cls):
        """Enforces critical security checks with resilient serverless fallbacks."""
        import secrets
        import logging
        log = logging.getLogger(__name__)
        if not cls.SECRET_KEY or cls.SECRET_KEY == "lifelink-fallback-dev-secret-key-32chars-min":
            cls.SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))
            log.warning("Production SECRET_KEY was not explicitly provided; generated a secure runtime key.")
        if not cls.DB_PASSWORD:
            log.warning("DB_PASSWORD is empty in production configuration. Running in demo/fallback mode if DB is unreachable.")


class TestingConfig(Config):
    """Configuration for unit and integration testing."""
    TESTING = True
    DEBUG = True
    DB_NAME = os.getenv("TEST_DB_NAME", "lifelink_test_db")
    SESSION_COOKIE_SECURE = False


# Configuration lookup map
config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
