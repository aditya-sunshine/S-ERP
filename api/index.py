import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("VERCEL", "1")

from app import app as flask_app

# Some Vercel setups leave "/api" or "/api/index" in PATH_INFO.
# Normalize so Flask routes like /dashboard match correctly.
class PathFix:
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "") or ""
        # Remove common Vercel prefixes if present
        for prefix in ("/api/index", "/api"):
            if path == prefix:
                path = "/"
                break
            if path.startswith(prefix + "/"):
                path = path[len(prefix):]
                break
        environ["PATH_INFO"] = path or "/"
        return self.app(environ, start_response)

app = PathFix(flask_app)
