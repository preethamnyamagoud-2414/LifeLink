import os
import sys
import json
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

        # Diagnostic file & environment inspection endpoint
        if "list_files=1" in environ.get("QUERY_STRING", ""):
            tree = []
            for r, dirs, files in os.walk("/var/task"):
                for f in files:
                    # skip .git or large wheels
                    if not any(ign in r for ign in [".git", "__pycache__"]):
                        tree.append(os.path.join(r, f))
            resp_obj = {
                "raw_path_info": environ.get("PATH_INFO"),
                "raw_query_string": environ.get("QUERY_STRING"),
                "all_headers": {k: str(v) for k, v in environ.items() if not any(s in k.upper() for s in ["KEY", "PASS", "SECRET", "TOKEN", "AUTH"])},
                "task_files": tree
            }
            start_response("200 OK", [("Content-Type", "application/json; charset=utf-8")])
            return [json.dumps(resp_obj, indent=2).encode("utf-8")]

        try:
            # Handle Vercel internal rewrites:
            # Vercel passes the original requested path in HTTP headers
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

            return self.wsgi_app(environ, start_response)
        except Exception as exc:
            err_tb = traceback.format_exc()
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
