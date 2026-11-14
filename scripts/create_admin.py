"""
LifeLink - Secure Administrator Provisioning Script
Executes administrative account creation via secure CLI execution.
Admin accounts cannot be created via public registration forms.
"""

import sys
import getpass
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app import create_app
from app.models.user import User
from app.services.security import validate_email, validate_password_strength, validate_phone
from app.extensions import test_db_connection


def main():
    print("")
    print("=" * 65)
    print("  LifeLink — Privileged Administrator Provisioning Utility")
    print("  Notice: This utility is restricted to authorized operators.")
    print("=" * 65)
    print("")

    app = create_app("development")
    with app.app_context():
        db_ok, msg, _ = test_db_connection()
        if not db_ok:
            print(f"[!] Warning: MySQL database is unreachable ({msg}).")
            print("    Please start MySQL Server before provisioning live admin accounts.")
            print("")

        full_name = input("Enter Administrator Full Name: ").strip()
        if not full_name:
            print("[X] Error: Administrator name cannot be empty.")
            sys.exit(1)

        email = input("Enter Administrator Email: ").strip().lower()
        ok_email, err_email = validate_email(email)
        if not ok_email:
            print(f"[X] Error: {err_email}")
            sys.exit(1)

        phone = input("Enter Administrator Callback Phone: ").strip()
        ok_phone, err_phone = validate_phone(phone)
        if not ok_phone:
            print(f"[X] Error: {err_phone}")
            sys.exit(1)

        password = getpass.getpass("Enter Strong Administrator Password: ")
        confirm_password = getpass.getpass("Confirm Administrator Password: ")

        if password != confirm_password:
            print("[X] Security Error: Passwords do not match.")
            sys.exit(1)

        ok_pw, err_pw = validate_password_strength(password)
        if not ok_pw:
            print(f"[X] Password Complexity Error: {err_pw}")
            sys.exit(1)

        try:
            user_id = User.create_admin(full_name, email, phone, password)
            print("")
            print(f"[✓] Success: Administrator '{full_name}' (#{user_id}) provisioned successfully.")
            print(f"    Account Role: 'admin' (Granted full system oversight)")
            print(f"    Login Email:  {email}")
            print("")
        except Exception as e:
            print(f"[X] Provisioning Failed: {e}")
            sys.exit(1)


if __name__ == "__main__":
    main()
