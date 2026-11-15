import os
import sys
import json
import urllib.parse
import traceback

# Ensure repository root is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import_error = None
flask_app = None

try:
    from app import create_app
    flask_env = os.getenv("FLASK_ENV", "production").lower()
    flask_app = create_app(flask_env)
except Exception as e:
    import_error = traceback.format_exc()


class VercelWSGIHandler:
    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        if import_error:
            start_response("500 Internal Server Error", [("Content-Type", "text/plain; charset=utf-8")])
            return [f"=== LIFELINK APPLICATION INITIALIZATION ERROR ===\n\n{import_error}".encode("utf-8")]

        # Handle Vercel internal rewrites:
        # 1. Check for path captured via vercel.json rewrite query parameter: ?__path__=...
        query_string = environ.get("QUERY_STRING", "")
        if "__path__=" in query_string:
            qs_dict = urllib.parse.parse_qs(query_string, keep_blank_values=True)
            custom_path = qs_dict.pop("__path__", [None])[0]
            if custom_path:
                if not custom_path.startswith("/"):
                    custom_path = "/" + custom_path
                environ["PATH_INFO"] = custom_path
                # Reconstruct query string without internal routing parameter
                clean_query = urllib.parse.urlencode([
                    (k, v) for k, vals in qs_dict.items() for v in vals
                ])
                environ["QUERY_STRING"] = clean_query
        else:
            # Fallback to standard Vercel headers if present
            matched_path = (
                environ.get("HTTP_X_MATCHED_PATH")
                or environ.get("HTTP_X_VERCEL_MATCHED_PATH")
                or environ.get("HTTP_X_FORWARDED_URI")
                or environ.get("HTTP_X_ORIGINAL_URI")
                or environ.get("x-matched-path")
            )
            path_info = environ.get("PATH_INFO", "")
            if matched_path and path_info in ("/api/index", "/api/index.py", "/api", "/api/"):
                environ["PATH_INFO"] = matched_path.split("?")[0]
            elif path_info in ("/api/index", "/api/index.py", "/api", "/api/"):
                environ["PATH_INFO"] = "/"

        try:
            return self.wsgi_app(environ, start_response)
        except Exception as exc:
            err_tb = traceback.format_exc()
            try:
                from app.database.connection import sanitize_db_error
                err_tb = sanitize_db_error(err_tb)
            except Exception:
                pass
            start_response("500 Internal Server Error", [("Content-Type", "text/plain; charset=utf-8")])
            return [f"=== LIFELINK RUNTIME WSGI INVOCATION ERROR ===\n\n{err_tb}".encode("utf-8")]


if flask_app:
    app = VercelWSGIHandler(flask_app.wsgi_app)
else:
    def app(environ, start_response):
        start_response("500 Internal Server Error", [("Content-Type", "text/plain; charset=utf-8")])
        return [f"=== LIFELINK APPLICATION INITIALIZATION ERROR ===\n\n{import_error}".encode("utf-8")]

application = app

if __name__ == "__main__":
    if flask_app:
        flask_app.run()
    else:
        print("Application failed to initialize:", import_error)
