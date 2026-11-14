import os
import sys

# Ensure repository root is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app


class VercelPathFixMiddleware:
    """
    WSGI Middleware to handle Vercel internal rewrites.
    Restores the original requested URL from Vercel's routing headers
    so Flask routes match correctly regardless of Vercel rewrite changes.
    """
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        matched_path = (
            environ.get("HTTP_X_MATCHED_PATH")
            or environ.get("HTTP_X_VERCEL_MATCHED_PATH")
            or environ.get("HTTP_X_FORWARDED_URI")
        )
        path_info = environ.get("PATH_INFO", "")
        if matched_path and path_info in ("/api/index", "/api/index.py", "/api"):
            environ["PATH_INFO"] = matched_path.split("?")[0]
        elif path_info in ("/api/index", "/api/index.py", "/api"):
            environ["PATH_INFO"] = "/"

        return self.wsgi_app(environ, start_response)


flask_env = os.getenv("FLASK_ENV", "development").lower()
app = create_app(flask_env)
app.wsgi_app = VercelPathFixMiddleware(app.wsgi_app)

if __name__ == "__main__":
    app.run()
