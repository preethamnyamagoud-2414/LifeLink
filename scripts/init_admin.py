"""
LifeLink - Administrator Account Provisioning Utility
Creates or updates the primary system administrator account in MySQL.
Uses environment variables or defaults to configure credentials safely.
Admin accounts cannot be registered through public registration forms.
"""

import os
import sys
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

# Load environment configuration
ADMIN_NAME = os.getenv("ADMIN_NAME", "Preetham (Administrator)").strip()
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "preethamnyamagoud@gmail.com").strip().lower()
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "LifeLink@2026!").strip()
ADMIN_PHONE = os.getenv("ADMIN_PHONE", "+1 (555) 019-0001").strip()


def init_admin():
    print("=" * 68)
    print("  LifeLink — Primary Administrator Provisioning Utility")
    print("=" * 68)
    print(f"  Target Admin Email: {ADMIN_EMAIL}")
    print(f"  Target Admin Name:  {ADMIN_NAME}")
    print(f"  Target Admin Role:  admin")
    print("-" * 68)

    try:
        from app import create_app
        from app.models.user import User
        from app.extensions import test_db_connection, execute_query

        app = create_app("development")
        with app.app_context():
            db_ok, msg, details = test_db_connection()

            # Hash the password securely using scrypt or pbkdf2
            password_hash = User.hash_password(ADMIN_PASSWORD)

            if db_ok:
                print(f"[✓] MySQL Connected: {details.get('mysql_version', 'Unknown Version')}")
                
                # Check if account already exists
                existing = User.find_by_email(ADMIN_EMAIL)
                if existing:
                    query = """
                        UPDATE users
                        SET full_name = %s,
                            password_hash = %s,
                            role = 'admin',
                            is_active = TRUE,
                            is_verified = TRUE,
                            is_demo = FALSE
                        WHERE email = %s;
                    """
                    execute_query(query, (ADMIN_NAME, password_hash, ADMIN_EMAIL), commit=True)
                    print(f"[✓] Existing account '{ADMIN_EMAIL}' (ID #{existing['id']}) updated with Admin privileges.")
                else:
                    query = """
                        INSERT INTO users (full_name, email, phone, password_hash, role, is_active, is_verified, is_demo)
                        VALUES (%s, %s, %s, %s, 'admin', TRUE, TRUE, FALSE)
                        ON DUPLICATE KEY UPDATE
                            password_hash = VALUES(password_hash),
                            role = 'admin',
                            is_active = TRUE,
                            is_verified = TRUE;
                    """
                    res = execute_query(query, (ADMIN_NAME, ADMIN_EMAIL, ADMIN_PHONE, password_hash), commit=True)
                    new_id = res.get("last_insert_id", 1)
                    print(f"[✓] Administrator account created successfully (User ID #{new_id}).")

                print(f"[✓] Password stored using cryptographic hash: {password_hash[:32]}...")
                print(f"[✓] Role set to 'admin' (Strictly guarded by server-side authorization).")
                print("=" * 68)
                print("  Admin Credentials Ready:")
                print(f"    URL:      http://localhost:5000/auth/login or http://localhost:5000/admin/login")
                print(f"    Email:    {ADMIN_EMAIL}")
                print(f"    Password: {ADMIN_PASSWORD}")
                print("=" * 68)
                return True
            else:
                print(f"[!] MySQL server is currently offline or unreachable: {msg}")
                print("    When MySQL is started, run this script to synchronize MySQL.")
                print("    Meanwhile, the standalone local server has provisioned the account in memory.")
                print("")
                print("    Direct SQL Seed Query:")
                print(f"    INSERT INTO users (full_name, email, phone, password_hash, role, is_active, is_verified, is_demo)")
                print(f"    VALUES ('{ADMIN_NAME}', '{ADMIN_EMAIL}', '{ADMIN_PHONE}', '{password_hash}', 'admin', TRUE, TRUE, FALSE)")
                print(f"    ON DUPLICATE KEY UPDATE password_hash=VALUES(password_hash), role='admin', is_active=TRUE, is_verified=TRUE;")
                print("=" * 68)
                return False

    except Exception as e:
        print(f"[X] Unexpected error during admin initialization: {e}")
        return False


if __name__ == "__main__":
    init_admin()
