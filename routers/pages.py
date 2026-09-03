from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

from core.config import settings

templates = Jinja2Templates(directory="templates")

# base.html wraps every page, so demo_mode is registered as a Jinja global
# rather than passed per route. Missing it on one route would silently render
# the demonstration shortcuts on a live deployment.
templates.env.globals["demo_mode"] = settings.SEED_DEMO_DATA
router = APIRouter()

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
