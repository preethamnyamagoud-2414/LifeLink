"""
LifeLink - Standalone Database Diagnostic Utility
Tests MySQL connectivity, cloud credentials, SSL configuration, and schema readiness safely.
Usage: python test_db_connection.py
"""

import sys
import os

# Ensure the root directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import Config
from app.database.connection import test_db_connection, PYMYSQL_AVAILABLE, sanitize_db_error


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

    db_cfg = Config.get_db_config()
    raw_url = os.getenv("DATABASE_URL") or os.getenv("MYSQL_URL")
    
    print("\n[2] Loaded Configuration:")
    if raw_url:
        print(f"    • Source            : DATABASE_URL / MYSQL_URL (Cloud Connection String)")
    else:
        print(f"    • Source            : Environment Variables (DB_HOST, DB_USER, etc.)")
        
    print(f"    • Host              : {db_cfg.get('host')}")
    print(f"    • Port              : {db_cfg.get('port')}")
    print(f"    • Database          : {db_cfg.get('database')}")
    print(f"    • User              : {db_cfg.get('user')}")
    print(f"    • Password          : {'*' * len(db_cfg.get('password')) if db_cfg.get('password') else '(empty/none)'}")
    print(f"    • Charset           : {db_cfg.get('charset')}")
    print(f"    • Connect Timeout   : {db_cfg.get('connect_timeout')}s")
    print(f"    • SSL Mode          : {db_cfg.get('ssl_mode')}")

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
            print("    To initialize schema, run:")
            print("    mysql -h <host> -u <user> -p <database> < database/schema.sql")
        
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
        print(" Troubleshooting Recommendations:")
        if db_cfg.get("host") in ("127.0.0.1", "localhost"):
            print(" For Local Development:")
            print("   1. Ensure local MySQL server is started (via XAMPP or Windows Service).")
            print("   2. Run 'services.msc' -> Start 'MySQL80' or open XAMPP Control Panel.")
            print(" For Production (Vercel):")
            print("   1. Do not use localhost on Vercel. Set DB_HOST or DATABASE_URL in Vercel.")
            print("   2. Use a free cloud MySQL provider like Aiven, TiDB Cloud, or Railway.")
        else:
            print(" For Cloud MySQL Provider:")
            print("   1. Verify your cloud host, port, username, and password in Vercel settings.")
            print("   2. Ensure inbound traffic from 0.0.0.0/0 is allowed in your cloud firewall.")
            print("   3. If SSL is required, ensure DB_SSL_MODE=REQUIRED (enabled by default).")
            print("   4. Verify database has been initialized with database/schema.sql.")
        print("-" * 70 + "\n")
        return 2


if __name__ == "__main__":
    sys.exit(run_diagnostics())
