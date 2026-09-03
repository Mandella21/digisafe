from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class RegisterRequest(BaseModel):
    full_name: str
    email: str
    password: str
    # Optional so an API client is not forced to send it twice; when the web
    # form does send it, the server verifies the two match rather than trusting
    # the browser to have done so.
    confirm_password: Optional[str] = None
    # Accepted but IGNORED - public sign-up always creates a victim account.
    # See the security note in routers/auth.py.
    role: Optional[str] = "victim"

class LoginRequest(BaseModel):
    email: str
    password: str
    role: Optional[str] = "victim"

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int
    full_name: str
    email: str

class UserOut(BaseModel):
    user_id: int
    full_name: str
    email: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True
