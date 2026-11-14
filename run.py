"""
LifeLink - Application Bootstrap & Entry Point
Executes the Flask development server when run directly.
Usage: python run.py
"""

import os
import sys

# Ensure root project directory is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.config import Config

# Initialize application factory using active environment
env_name = os.getenv("FLASK_ENV", "development").lower()
app = create_app(env_name)

if __name__ == "__main__":
    host = os.getenv("FLASK_RUN_HOST", "127.0.0.1")
    port = int(os.getenv("FLASK_RUN_PORT", 5000))
    debug = app.config.get("DEBUG", True)

    print("\n" + "=" * 70)
    print("  " + app.config.get("APP_NAME", "LifeLink").upper())
    print("  " + app.config.get("APP_TAGLINE", "Smart Blood Donor Portal"))
    print("=" * 70)
    print(f"  • Environment  : {env_name.upper()}")
    print(f"  • Debug Mode   : {'ENABLED' if debug else 'DISABLED'}")
    print(f"  • Web URL      : http://{host}:{port}/")
    print(f"  • Health Check : http://{host}:{port}/health")
    print(f"  • Target DB    : {Config.DB_NAME} on {Config.DB_HOST}:{Config.DB_PORT}")
    print("=" * 70)
    print("  Server is starting... Press CTRL+C to terminate.\n")

    app.run(host=host, port=port, debug=debug)
