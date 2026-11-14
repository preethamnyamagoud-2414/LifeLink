"""
LifeLink - Standalone Database Diagnostic Utility
Tests MySQL connectivity, credentials, and schema readiness safely.
Usage: python test_db_connection.py
"""

import sys
import os

# Ensure the root directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import Config
from app.database.connection import test_db_connection, PYMYSQL_AVAILABLE


def print_header(title: str):
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def run_diagnostics():
    print_header("LifeLink Database Diagnostic Check")
    
    print("\n[1] Checking Python Environment & Drivers:")
    print(f"    • Python Executable : {sys.executable}")
    print(f"    • Python Version    : {sys.version.split()[0]}")
    
    if PYMYSQL_AVAILABLE:
        import pymysql
        print(f"    • PyMySQL Driver    : [OK] Version {pymysql.__version__}")
    else:
        print("    • PyMySQL Driver    : [MISSING]")
        print("\n[!] FATAL: PyMySQL is not installed.")
        print("    Run: pip install -r requirements.txt")
        return 1

    print("\n[2] Loaded Configuration (from .env or Defaults):")
    print(f"    • Host              : {Config.DB_HOST}")
    print(f"    • Port              : {Config.DB_PORT}")
    print(f"    • Database          : {Config.DB_NAME}")
    print(f"    • User              : {Config.DB_USER}")
    print(f"    • Password          : {'*' * len(Config.DB_PASSWORD) if Config.DB_PASSWORD else '(empty/none)'}")
    print(f"    • Charset           : {Config.DB_CHARSET}")

    print("\n[3] Testing MySQL Connection:")
    success, message, details = test_db_connection()

    if success:
        print(f"    • Result            : [SUCCESS]")
        print(f"    • Status Message    : {message}")
        print(f"    • MySQL Version     : {details.get('mysql_version')}")
        print(f"    • Target Database   : {details.get('database_name')}")
        print(f"    • Server Timestamp  : {details.get('server_time')}")
        print(f"    • Total Tables      : {details.get('table_count', 0)}")
        
        tables = details.get("tables", [])
        if tables:
            print("\n[4] Existing Tables Verified in Database:")
            for tbl in tables:
                print(f"      - {tbl}")
        else:
            print("\n[!] NOTICE: Database exists but contains 0 tables.")
            print("    To initialize schema and fictional demo data, run:")
            print("    mysql -u root -p lifelink_db < database/schema.sql")
            print("    mysql -u root -p lifelink_db < database/seed.sql")
        
        print("\n" + "-" * 70)
        print(" [OK] Database layer is ready for LifeLink!")
        print("-" * 70 + "\n")
        return 0
    else:
        print(f"    • Result            : [FAILED]")
        print(f"    • Diagnosis         : {message}")
        if details.get("mysql_version"):
            print(f"    • MySQL Version     : {details.get('mysql_version')}")
        
        print("\n" + "-" * 70)
        print(" Troubleshooting Steps for Windows:")
        print(" 1. Ensure MySQL Server is started:")
        print("    - Windows Service: Run 'services.msc' and start 'MySQL80' / 'MySQL'")
        print("    - Or XAMPP: Open XAMPP Control Panel and start MySQL")
        print(" 2. Verify your credentials in .env file (DB_USER, DB_PASSWORD, DB_PORT)")
        print(" 3. If MySQL is working but database doesn't exist, create it with:")
        print("    mysql -u root -p -e 'CREATE DATABASE lifelink_db CHARACTER SET utf8mb4;'")
        print("    mysql -u root -p lifelink_db < database/schema.sql")
        print("-" * 70 + "\n")
        return 2


if __name__ == "__main__":
    sys.exit(run_diagnostics())
