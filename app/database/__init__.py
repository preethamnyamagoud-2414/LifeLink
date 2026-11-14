"""
LifeLink - Database Package
Exposes core connection, query execution, and diagnostic utilities.
"""

from app.database.connection import (
    get_db,
    get_db_connection,
    close_db,
    db_cursor,
    execute_query,
    test_db_connection,
    PYMYSQL_AVAILABLE,
)

__all__ = [
    "get_db",
    "get_db_connection",
    "close_db",
    "db_cursor",
    "execute_query",
    "test_db_connection",
    "PYMYSQL_AVAILABLE",
]
