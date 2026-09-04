from fastapi import APIRouter, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from core.config import settings, BASE_DIR

STATIC_IMG = BASE_DIR / "static" / "img"

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# base.html wraps every page, so demo_mode is registered as a Jinja global
# rather than passed per route. Missing it on one route would silently render
# the demonstration shortcuts on a live deployment.
templates.env.globals["demo_mode"] = settings.SEED_DEMO_DATA
router = APIRouter()

@router.get("/favicon.ico", include_in_schema=False)
def favicon():
    """Serve the icon from the site root.

    Browsers request /favicon.ico directly, without reading the page, and some
    surfaces that display a site icon never parse the <link> tags at all. The
    file lives under /static, so this just points there rather than duplicating
    it - a 404 here is why a tab shows a blank page icon even when the markup
    is correct.
    """
    return FileResponse(
        STATIC_IMG / "favicon.ico",
        media_type="image/x-icon",
        # Icons change about never, and re-requesting one on every page view is
        # wasted round trips on a phone connection.
        headers={"Cache-Control": "public, max-age=604800"},
    )


@router.get("/site.webmanifest", include_in_schema=False)
def web_manifest():
    """Names and icons the platform by when someone adds it to a home screen.

    Without this, a phone shows a screenshot of the page and the page title as
    the app name. It costs nothing and this is a platform people are meant to
    reach quickly, possibly in distress.
    """
    return JSONResponse(
        {
            "name": "DigiSafe - Digital Safety & Record Protection",
            "short_name": "DigiSafe",
            "description": (
                "Capture and cryptographically preserve evidence of online abuse."
            ),
            "start_url": "/",
            "display": "standalone",
            "background_color": "#0f172a",
            "theme_color": "#0f172a",
            "icons": [
                {"src": "/static/img/icon-192.png", "sizes": "192x192", "type": "image/png"},
                {"src": "/static/img/icon-512.png", "sizes": "512x512", "type": "image/png"},
                {"src": "/static/img/favicon.svg", "sizes": "any", "type": "image/svg+xml"},
            ],
        },
        media_type="application/manifest+json",
    )


@router.get("/")
def home_page(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@router.get("/auth")
def auth_page(request: Request):
    # The one-click role logins only exist when demonstration data does. On a
    # real deployment they would be an open door to an administrator account.
    return templates.TemplateResponse(request=request, name="auth.html")

@router.get("/verify")
def verify_page(request: Request):
    """Where a new account is confirmed.

    Reached two ways: redirected here straight after sign-up, or by tapping the
    button in the verification email. The ?token= in the link is read by the
    browser, so the same page serves both without a second route.
    """
    return templates.TemplateResponse(request=request, name="verify.html")

@router.get("/submit")
def submit_page(request: Request):
    return templates.TemplateResponse(request=request, name="victim_submit.html")

@router.get("/track")
def track_page(request: Request):
    return templates.TemplateResponse(request=request, name="victim_track.html")

@router.get("/admin")
def admin_page(request: Request):
    return templates.TemplateResponse(request=request, name="admin_dashboard.html")

@router.get("/audit")
def audit_page(request: Request):
    return templates.TemplateResponse(request=request, name="audit_logs.html")
