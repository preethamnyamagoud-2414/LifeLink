"""
LifeLink - Configuration Module
Supports environment-driven configuration for development, testing, and production.
Fully compatible with cloud-hosted MySQL databases (Aiven, TiDB Cloud, PlanetScale, AWS RDS, Railway, etc.)
"""

import os
import re
import urllib.parse
from pathlib import Path
from dotenv import load_dotenv

# Locate and load the root .env file
BASE_DIR = Path(__file__).resolve().parent.parent
env_file_path = BASE_DIR / ".env"
if env_file_path.exists():
    load_dotenv(dotenv_path=env_file_path)
else:
    load_dotenv()  # Fallback to system environment


def parse_database_url(url: str) -> dict:
    """
    Parses standard database connection strings:
    e.g. mysql://user:password@host:port/database?ssl-mode=REQUIRED
    Supports mysql://, mysql+pymysql://, and mariadb:// schemes.
    """
    if not url or not isinstance(url, str):
        return {}
    
    clean_url = url.strip()
    if clean_url.startswith("mysql+pymysql://"):
        clean_url = "mysql://" + clean_url[len("mysql+pymysql://"):]
    
    try:
        parsed = urllib.parse.urlparse(clean_url)
    except Exception:
        return {}

    if parsed.scheme not in ("mysql", "mysqls", "mariadb"):
        return {}

    db_name = parsed.path.lstrip("/") if parsed.path else None
    query_params = urllib.parse.parse_qs(parsed.query)

    cfg = {
        "host": parsed.hostname or "127.0.0.1",
        "port": parsed.port or 3306,
        "user": urllib.parse.unquote(parsed.username) if parsed.username else "root",
        "password": urllib.parse.unquote(parsed.password) if parsed.password else "",
        "database": db_name or "lifelink_db",
    }

    # SSL Mode inference from URL
    if parsed.scheme == "mysqls" or "ssl-mode" in query_params or "sslmode" in query_params:
        mode = query_params.get("ssl-mode", query_params.get("sslmode", ["REQUIRED"]))[0]
        cfg["ssl_mode"] = mode.upper()
    elif "ssl" in query_params:
        val = query_params["ssl"][0].lower()
        cfg["ssl_mode"] = "REQUIRED" if val in ("1", "true", "required") else "DISABLED"

    if "ssl_ca" in query_params:
        cfg["ssl_ca"] = query_params["ssl_ca"][0]
    
    return cfg


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

    # Database Configuration (MySQL / Cloud Database)
    # Check for DATABASE_URL / MYSQL_URL first (standard across cloud providers)
    _raw_db_url = (
        os.getenv("DATABASE_URL")
        or os.getenv("MYSQL_URL")
        or os.getenv("JAWSDB_URL")
        or os.getenv("CLEARDB_DATABASE_URL")
    )
    _url_cfg = parse_database_url(_raw_db_url) if _raw_db_url else {}

    DB_HOST = _url_cfg.get("host") or os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = int(_url_cfg.get("port") or os.getenv("DB_PORT", 3306))
    DB_NAME = _url_cfg.get("database") or os.getenv("DB_NAME", "lifelink_db")
    DB_USER = _url_cfg.get("user") or os.getenv("DB_USER", "root")
    DB_PASSWORD = _url_cfg.get("password") or os.getenv("DB_PASSWORD", "")
    DB_CHARSET = os.getenv("DB_CHARSET", "utf8mb4")
    DB_CONNECT_TIMEOUT = int(os.getenv("DB_CONNECT_TIMEOUT", 10))
    DB_AUTOCOMMIT = os.getenv("DB_AUTOCOMMIT", "false").lower() in ("true", "1", "yes")

    # Cloud SSL / TLS Configuration
    DB_SSL_MODE = _url_cfg.get("ssl_mode") or os.getenv("DB_SSL_MODE", "AUTO").upper()
    DB_SSL_CA = _url_cfg.get("ssl_ca") or os.getenv("DB_SSL_CA", None)
    DB_SSL_CERT = os.getenv("DB_SSL_CERT", None)
    DB_SSL_KEY = os.getenv("DB_SSL_KEY", None)

    @classmethod
    def get_db_config(cls) -> dict:
        """
        Returns MySQL connection parameters as a dictionary for PyMySQL.
        Evaluates environment variables dynamically to support serverless runtime changes.
        """
        raw_db_url = (
            os.getenv("DATABASE_URL")
            or os.getenv("MYSQL_URL")
            or os.getenv("JAWSDB_URL")
            or os.getenv("CLEARDB_DATABASE_URL")
        )
        url_cfg = parse_database_url(raw_db_url) if raw_db_url else {}

        host = url_cfg.get("host") or os.getenv("DB_HOST", "127.0.0.1")
        port_val = url_cfg.get("port") or os.getenv("DB_PORT", 3306)
        try:
            port = int(port_val)
        except (ValueError, TypeError):
            port = 3306

        database = url_cfg.get("database") or os.getenv("DB_NAME", "lifelink_db")
        user = url_cfg.get("user") or os.getenv("DB_USER", "root")
        password = url_cfg.get("password") or os.getenv("DB_PASSWORD", "")
        charset = os.getenv("DB_CHARSET", "utf8mb4")

        try:
            connect_timeout = int(os.getenv("DB_CONNECT_TIMEOUT", 10))
        except (ValueError, TypeError):
            connect_timeout = 10

        autocommit = os.getenv("DB_AUTOCOMMIT", "false").lower() in ("true", "1", "yes")
        ssl_mode = str(url_cfg.get("ssl_mode") or os.getenv("DB_SSL_MODE", "AUTO")).strip().upper()
        ssl_ca = url_cfg.get("ssl_ca") or os.getenv("DB_SSL_CA", None)
        ssl_cert = os.getenv("DB_SSL_CERT", None)
        ssl_key = os.getenv("DB_SSL_KEY", None)

        return {
            "host": host,
            "port": port,
            "user": user,
            "password": password,
            "database": database,
            "charset": charset,
            "connect_timeout": connect_timeout,
            "autocommit": autocommit,
            "ssl_mode": ssl_mode,
            "ssl_ca": ssl_ca,
            "ssl_cert": ssl_cert,
            "ssl_key": ssl_key,
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
        """Enforces critical security checks with resilient cloud fallbacks."""
        import secrets
        import logging
        log = logging.getLogger(__name__)
        if not cls.SECRET_KEY or cls.SECRET_KEY == "lifelink-fallback-dev-secret-key-32chars-min":
            cls.SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))
            log.warning("Production SECRET_KEY was not explicitly provided; generated a secure runtime key.")
        
        # Check if production is inadvertently pointing to localhost
        is_vercel = bool(os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"))
        if is_vercel and cls.DB_HOST in ("127.0.0.1", "localhost"):
            log.warning(
                "Vercel Serverless environment detected, but DB_HOST is set to '%s'. "
                "Localhost is not reachable from serverless containers. "
                "Please configure DB_HOST, DB_USER, DB_PASSWORD or DATABASE_URL in Vercel settings.",
                cls.DB_HOST
            )


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
