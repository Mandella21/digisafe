"""Serverless entrypoint for Vercel.

Vercel's Python runtime looks for a module under api/ that exposes an ASGI
application called `app`. It does not run `uvicorn main:app`, so this is the
only thing that changes about how the platform is started - the application
itself is identical to the one every other host runs.

The parent directory has to go on sys.path because this file is imported from
inside api/, and everything it needs (main, core, routers, services) lives one
level up.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Re-exported for Vercel to find. main.py resolves its template and static
# directories from BASE_DIR rather than the working directory, which is what
# lets it be imported from here at all.
from main import app  # noqa: E402,F401
