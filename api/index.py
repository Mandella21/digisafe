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

# main.py resolves its template and static directories from BASE_DIR rather
# than the working directory, which is what lets it be imported from here.
from main import app, initialise_application  # noqa: E402

# Run startup here, explicitly.
#
# A long-running server gets this from the ASGI lifespan event. Serverless
# invocations may not run one at all, and without it the schema is never
# created - so every request would fail against an empty database, reporting a
# missing table rather than a missing startup. Calling it at import time means
# it happens once per cold start, which is exactly when it is needed.
#
# It is deliberately not wrapped in try/except: if the database is unreachable
# or misconfigured, failing loudly here surfaces it in the deployment log,
# where it can be read. Swallowing it would produce a site that loads and then
# fails on every action, for reasons nothing records.
initialise_application()

__all__ = ["app"]
