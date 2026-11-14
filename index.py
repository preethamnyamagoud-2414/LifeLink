"""
LifeLink - Root Application Entrypoint
Exposes app for local servers, cloud hosts, and Vercel.
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from api.index import app, application, flask_app

if __name__ == "__main__":
    if flask_app:
        flask_app.run()
