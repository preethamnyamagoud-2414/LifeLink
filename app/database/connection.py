"""
LifeLink - Database Connection & Query Execution Layer
Provides safe connection pooling, Flask context integration, and strictly
parameterized query execution using PyMySQL.
"""

import logging
from contextlib import contextmanager
from typing import Any, Dict, List, Optional, Tuple, Union
from flask import current_app, g

try:
    import pymysql
    import pymysql.cursors
    from pymysql.err import MySQLError, OperationalError
    PYMYSQL_AVAILABLE = True
except ImportError:
    PYMYSQL_AVAILABLE = False
    MySQLError = Exception
    OperationalError = Exception

logger = logging.getLogger(__name__)


def get_db_connection(database: Optional[str] = None) -> "pymysql.Connection":
    """
    Establishes and returns a direct PyMySQL connection.
    
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

    params = {
        "host": db_cfg.get("host", "127.0.0.1"),
        "port": db_cfg.get("port", 3306),
        "user": db_cfg.get("user", "root"),
        "password": db_cfg.get("password", ""),
        "charset": db_cfg.get("charset", "utf8mb4"),
        "connect_timeout": db_cfg.get("connect_timeout", 10),
        "autocommit": db_cfg.get("autocommit", False),
        "cursorclass": pymysql.cursors.DictCursor,
    }

    if database is not None:
        if database:
            params["database"] = database
    elif db_cfg.get("database"):
        params["database"] = db_cfg.get("database")

    return pymysql.connect(**params)


def get_db():
    """
    Retrieves or establishes the request-scoped database connection stored in Flask 'g'.
    Automatically reused during a single request lifecycle.
    """
    if "db" not in g:
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
            logger.warning(f"Error while closing database connection: {err}")


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
        logger.error(f"Database query transaction failed: {exc}", exc_info=True)
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
    
    :param query: SQL statement with '%s' or '%(name)s' placeholders.
    :param params: Tuple, list, or dictionary of bound parameters.
    :param fetchone: If True, returns a single row dictionary or None.
    :param fetchall: If True, returns a list of row dictionaries.
    :param commit: If True, commits the transaction (INSERT, UPDATE, DELETE).
    :return: Query results (dict, list of dicts, or lastrowid/rowcount for mutations).
    """
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


def test_db_connection() -> Tuple[bool, str, Dict[str, Any]]:
    """
    Safely tests database connectivity without crashing the application.
    
    :return: A tuple of (success: bool, message: str, details: dict)
    """
    if not PYMYSQL_AVAILABLE:
        return False, "PyMySQL driver is missing. Please run: pip install -r requirements.txt", {}

    details = {}
    try:
        # First attempt: Connect directly to the specific database
        conn = get_db_connection()
        with conn.cursor() as cursor:
            cursor.execute("SELECT VERSION() AS version, DATABASE() AS current_db, NOW() AS server_time;")
            row = cursor.fetchone()
            details["mysql_version"] = row.get("version")
            details["database_name"] = row.get("current_db")
            details["server_time"] = str(row.get("server_time"))
            
            # Check existing tables
            cursor.execute("SHOW TABLES;")
            tables = [list(t.values())[0] for t in cursor.fetchall()]
            details["tables"] = tables
            details["table_count"] = len(tables)

        conn.close()
        return True, "Successfully connected to MySQL database 'lifelink_db'.", details

    except OperationalError as oe:
        err_code, err_msg = (oe.args[0], oe.args[1]) if len(oe.args) >= 2 else (0, str(oe))
        
        # MySQL error 1049: Unknown database (Server is running, but database needs creation)
        if err_code == 1049:
            try:
                # Test connection to server without database
                server_conn = get_db_connection(database="")
                with server_conn.cursor() as cursor:
                    cursor.execute("SELECT VERSION() AS version;")
                    row = cursor.fetchone()
                    details["mysql_version"] = row.get("version")
                server_conn.close()
                return False, (
                    f"MySQL Server is RUNNING (Version: {details.get('mysql_version')}), "
                    f"but database 'lifelink_db' has not been created yet. "
                    f"Run: 'mysql -u root -p < database/schema.sql' to initialize."
                ), details
            except Exception as inner_err:
                return False, f"MySQL connection error: {inner_err}", details

        # MySQL error 2003: Can't connect to MySQL server on host (MySQL service is stopped)
        if err_code == 2003:
            return False, (
                "Cannot connect to MySQL server at the specified host/port. "
                "Ensure MySQL Server service is running (e.g. through Windows Services, XAMPP, or command line)."
            ), details

        # MySQL error 1045: Access denied for user
        if err_code == 1045:
            return False, (
                "MySQL authentication failed (Access Denied). "
                "Check DB_USER and DB_PASSWORD in your .env configuration file."
            ), details

        return False, f"MySQL Operational Error ({err_code}): {err_msg}", details

    except Exception as exc:
        return False, f"Unexpected database connection failure: {exc}", details
