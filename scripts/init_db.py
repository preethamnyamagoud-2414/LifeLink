"""
LifeLink - Remote Database Initializer
Creates all tables (database/schema.sql) in the database configured by
DATABASE_URL or DB_* env vars / .env. Works with cloud MySQL such as TiDB Cloud.

WARNING: schema.sql DROPS existing LifeLink tables first. Run once on a fresh DB.

Usage:
    python scripts/init_db.py            # schema only
    python scripts/init_db.py --seed     # schema + demo data (database/seed.sql)
"""

import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


def load_statements(path: Path):
    sql = path.read_text(encoding="utf-8")
    # Drop full-line comments, then CREATE DATABASE / USE (the cloud DB already exists).
    sql = "\n".join(l for l in sql.splitlines() if not l.strip().startswith("--"))
    sql = re.sub(r"CREATE DATABASE[^;]*;", "", sql, flags=re.I)
    sql = re.sub(r"^\s*USE\s+[^;]*;", "", sql, flags=re.I | re.M)
    # Split on ';' but ignore semicolons inside quoted strings
    stmts, buf, quote = [], [], None
    for i, ch in enumerate(sql):
        if quote:
            if ch == quote and sql[i - 1] != "\\":
                quote = None
        elif ch in ("'", '"', "`"):
            quote = ch
        elif ch == ";":
            stmts.append("".join(buf).strip())
            buf = []
            continue
        buf.append(ch)
    stmts.append("".join(buf).strip())
    return [s for s in stmts if s]


def main():
    from app.config import Config
    from app.database.connection import get_db_connection

    files = [BASE_DIR / "database" / "schema.sql"]
    if "--seed" in sys.argv:
        files.append(BASE_DIR / "database" / "seed.sql")

    print(f"Connecting to {Config.DB_HOST}:{Config.DB_PORT}/{Config.DB_NAME} (SSL={Config.DB_SSL_MODE}) ...")
    # Create the database itself if it does not exist yet (cloud clusters start empty)
    server = get_db_connection(database="")
    with server.cursor() as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{Config.DB_NAME}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    server.commit()
    server.close()

    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            for f in files:
                stmts = load_statements(f)
                print(f"Running {f.name}: {len(stmts)} statements")
                for s in stmts:
                    cur.execute(s)
        conn.commit()
        with conn.cursor() as cur:
            cur.execute("SHOW TABLES")
            print("Tables:", ", ".join(list(r.values())[0] for r in cur.fetchall()))
        print("Done.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
