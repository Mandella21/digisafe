from fastapi import APIRouter, Request
from fastapi.templating import Jinja2Templates

templates = Jinja2Templates(directory="templates")
router = APIRouter()

@router.get("/")
def home_page(request: Request):
    return templates.TemplateResponse(request=request, name="index.html")

@router.get("/auth")
def auth_page(request: Request):
    return templates.TemplateResponse(request=request, name="auth.html")

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
