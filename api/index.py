import os
import sys

# Ensure the repository root is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app

# Initialize application factory
flask_env = os.getenv("FLASK_ENV", "development").lower()
app = create_app(flask_env)

if __name__ == "__main__":
    app.run()
