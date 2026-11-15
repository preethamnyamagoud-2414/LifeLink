"""
LifeLink - Database Connection & Query Execution Layer
Provides safe connection pooling, Flask context integration, strictly
parameterized query execution, and cloud SSL compatibility using PyMySQL.
"""

import os
import re
import ssl
import logging
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple, Union
from flask import current_app, g

try:
    import pymysql
    import pymysql.cursors
    from pymysql.err import MySQLError, OperationalError, InternalError, IntegrityError, ProgrammingError
    PYMYSQL_AVAILABLE = True
except ImportError:
    PYMYSQL_AVAILABLE = False
    MySQLError = Exception
    OperationalError = Exception
    InternalError = Exception
    IntegrityError = Exception
    ProgrammingError = Exception

logger = logging.getLogger(__name__)


def sanitize_db_error(error_msg: str) -> str:
    """Removes sensitive credentials, passwords, and tokens from error messages."""
    if not error_msg:
        return ""
    # Mask password in connection URIs: mysql://user:password@host
    sanitized = re.sub(r'(://[^:]+:)[^@]+(@)', r'\1*****\2', str(error_msg))
    # Mask password parameters in strings
    sanitized = re.sub(r'(password[\'\"]?\s*[:=]\s*[\'\"]?)[^\s,\'\"]+', r'\1*****', sanitized, flags=re.IGNORECASE)
    return sanitized


def build_ssl_context(
    ssl_mode: str = "AUTO",
    host: str = "127.0.0.1",
    ca_file: Optional[str] = None,
    cert_file: Optional[str] = None,
    key_file: Optional[str] = None
) -> Optional[ssl.SSLContext]:
    """
    Builds an ssl.SSLContext compatible with cloud MySQL providers
    (Aiven, TiDB Cloud, PlanetScale, AWS RDS, Azure Database for MySQL, Railway, etc.).
    """
    mode = str(ssl_mode or "AUTO").strip().upper()
    is_local = host in ("127.0.0.1", "localhost", "::1")

    # Explicitly disabled
    if mode in ("DISABLED", "FALSE", "NONE", "0"):
        return None

    # In AUTO mode, only enable SSL for non-local (cloud) hosts
    if mode == "AUTO" and is_local:
        return None

    try:
        ctx = ssl.create_default_context()
        if ca_file and os.path.exists(ca_file):
            ctx.load_verify_locations(cafile=ca_file)

        if cert_file and key_file and os.path.exists(cert_file) and os.path.exists(key_file):
            ctx.load_cert_chain(certfile=cert_file, keyfile=key_file)

        if mode in ("REQUIRED", "AUTO"):
            # Encryption enforced; hostname check relaxed to support cloud connection poolers/proxies
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        elif mode == "VERIFY_CA":
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_REQUIRED
        elif mode == "VERIFY_IDENTITY":
            ctx.check_hostname = True
            ctx.verify_mode = ssl.CERT_REQUIRED

        return ctx
    except Exception as ssl_err:
        logger.warning(f"Could not initialize SSL context for database: {sanitize_db_error(str(ssl_err))}")
        return None


def get_db_connection(database: Optional[str] = None) -> "pymysql.Connection":
    """
    Establishes and returns a direct PyMySQL connection.
    Configured for 10-second serverless timeout and cloud SSL support.
    
    :param database: Optional database name override. If None, uses DB_NAME from config.
                     Pass empty string or False if connecting to server before DB creation.
    :return: A pymysql.Connection object with DictCursor.
    :raises RuntimeError: If pymysql is not installed or connection fails.
    """
    if not PYMYSQL_AVAILABLE:
        raise RuntimeError(
            "PyMySQL package is not installed. Run 'pip install -r requirements.txt' to install dependencies."
        )

    # Resolve settings from Flask current_app if available, else from Config
    if current_app:
        db_cfg = current_app.config.get("DB_CONFIG", {})
    else:
        from app.config import Config
        db_cfg = Config.get_db_config()

    host = db_cfg.get("host", "127.0.0.1")
    port = int(db_cfg.get("port", 3306))
    user = db_cfg.get("user", "root")
    password = db_cfg.get("password", "")
    charset = db_cfg.get("charset", "utf8mb4")
    connect_timeout = int(db_cfg.get("connect_timeout", 10))
    autocommit = bool(db_cfg.get("autocommit", False))

    params = {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "charset": charset,
        "connect_timeout": connect_timeout,
        "autocommit": autocommit,
        "cursorclass": pymysql.cursors.DictCursor,
    }

    # Resolve database name
    if database is not None:
        if database:
            params["database"] = database
    elif db_cfg.get("database"):
        params["database"] = db_cfg.get("database")

    # Attach SSL configuration
    ssl_mode = db_cfg.get("ssl_mode", "AUTO")
    ssl_ca = db_cfg.get("ssl_ca")
    ssl_cert = db_cfg.get("ssl_cert")
    ssl_key = db_cfg.get("ssl_key")

    ssl_ctx = build_ssl_context(
        ssl_mode=ssl_mode,
        host=host,
        ca_file=ssl_ca,
        cert_file=ssl_cert,
        key_file=ssl_key
    )
    if ssl_ctx is not None:
        params["ssl"] = ssl_ctx

    return pymysql.connect(**params)


def get_db():
    """
    Retrieves or establishes the request-scoped database connection stored in Flask 'g'.
    Verifies connection liveness with ping(reconnect=True) for serverless resilience.
    """
    if "db" not in g:
        g.db = get_db_connection()
    else:
        try:
            g.db.ping(reconnect=True)
        except Exception:
            g.db = get_db_connection()
    return g.db


def close_db(e=None):
    """
    Closes the request-scoped database connection when application context tears down.
    Registered in app factory via app.teardown_appcontext(close_db).
    """
    db = g.pop("db", None)
    if db is not None:
        try:
            db.close()
        except Exception as err:
            logger.debug(f"Database connection cleanup: {err}")


@contextmanager
def db_cursor(commit: bool = False):
    """
    Context manager for safe transactional database operations.
    Automatically commits on success or rolls back on exception.
    """
    conn = get_db()
    cursor = conn.cursor()
    try:
        yield cursor
        if commit:
            conn.commit()
    except Exception as exc:
        if commit:
            try:
                conn.rollback()
            except Exception:
                pass
        clean_msg = sanitize_db_error(str(exc))
        logger.error(f"Database query transaction failed: {clean_msg}")
        raise
    finally:
        cursor.close()


def execute_query(
    query: str,
    params: Optional[Union[Tuple, List, Dict[str, Any]]] = None,
    fetchone: bool = False,
    fetchall: bool = False,
    commit: bool = False
) -> Any:
    """
    Executes a strictly parameterized SQL query.
    Never concatenate unvalidated user input into the query parameter.
    Safely sanitizes error messages and prevents cascading crashes on read failures.
    """
    try:
        with db_cursor(commit=commit) as cursor:
            cursor.execute(query, params or ())
            if fetchone:
                return cursor.fetchone()
            if fetchall:
                return cursor.fetchall()
            if commit:
                return {
                    "last_insert_id": cursor.lastrowid,
                    "row_count": cursor.rowcount
                }
            return cursor
    except Exception as exc:
        clean_msg = sanitize_db_error(str(exc))
        logger.error(f"Database query execution failed: {clean_msg}")
        if commit:
            raise
        if fetchone:
            return None
        if fetchall:
            return []
        return None


def test_db_connection() -> Tuple[bool, str, Dict[str, Any]]:
    """
    Safely tests database connectivity without crashing the application
    or exposing sensitive credentials.
    
    :return: A tuple of (success: bool, message: str, details: dict)
    """
    if not PYMYSQL_AVAILABLE:
        return False, "PyMySQL driver is missing. Please run: pip install -r requirements.txt", {}

    details = {}
    try:
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT VERSION() AS version, DATABASE() AS current_db, NOW() AS server_time;")
            row = cursor.fetchone() or {}
            details["mysql_version"] = row.get("version")
            details["database_name"] = row.get("current_db")
            details["server_time"] = str(row.get("server_time"))
            
            # Check existing tables
            cursor.execute("SHOW TABLES;")
            tables = [list(t.values())[0] for t in cursor.fetchall()]
            details["tables"] = tables
            details["table_count"] = len(tables)

        conn.close()
        return True, f"Successfully connected to MySQL database '{details.get('database_name')}'.", details

    except OperationalError as oe:
        err_code, err_msg = (oe.args[0], oe.args[1]) if len(oe.args) >= 2 else (0, str(oe))
        clean_msg = sanitize_db_error(str(err_msg))

        if err_code == 1049:
            try:
                # Test connection to server without database
                server_conn = get_db_connection(database="")
                with server_conn.cursor() as cursor:
                    cursor.execute("SELECT VERSION() AS version;")
                    row = cursor.fetchone() or {}
                    details["mysql_version"] = row.get("version")
                server_conn.close()
                return False, (
                    f"MySQL Server is RUNNING (Version: {details.get('mysql_version')}), "
                    f"but database '{details.get('database_name', 'lifelink_db')}' has not been created yet. "
                    f"Import 'database/schema.sql' to initialize."
                ), details
            except Exception as inner_err:
                clean_inner = sanitize_db_error(str(inner_err))
                return False, f"MySQL connection error: {clean_inner}", details

        if err_code == 2003:
            return False, (
                "Cannot connect to MySQL server at the specified host/port (connection timed out or unreachable). "
                "For cloud MySQL, verify DB_HOST, DB_PORT, and allow-list inbound IP addresses."
            ), details

        if err_code == 1045:
            return False, (
                "MySQL authentication failed (Access Denied). "
                "Check DB_USER and DB_PASSWORD credentials."
            ), details

        if err_code == 3159:
            return False, (
                "Connections using insecure transport are prohibited by the MySQL server. "
                "Set DB_SSL_MODE=REQUIRED in your environment."
            ), details

        return False, f"MySQL Operational Error ({err_code}): {clean_msg}", details

    except Exception as exc:
        clean_exc = sanitize_db_error(str(exc))
        return False, f"Database connection failure: {clean_exc}", details
