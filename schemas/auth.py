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

class VerifyCodeRequest(BaseModel):
    email: str
    code: str

class VerifyTokenRequest(BaseModel):
    """Completes verification from the link in the email rather than a typed code."""
    token: str

class ResendVerificationRequest(BaseModel):
    email: str

class RegisterResponse(BaseModel):
    """What sign-up returns now that an account starts unverified.

    Deliberately NOT a TokenResponse. Registration no longer hands out a
    session, because handing one out would make verification decorative: the
    person would already be signed in and would never need to prove the
    address was theirs. The session is issued by /verify instead.
    """
    status: str = "verification_required"
    message: str
    email: str
    full_name: str
    verification_required: bool = True
    # "smtp" - handed to a mail server; "outbox" - no mail server configured,
    # written to storage/outbox and printed to the console; "failed" - sending
    # was attempted and did not work. The interface says something different
    # in each case rather than always claiming "check your inbox".
    delivery: str = "smtp"
    email_sent: bool = True
    expires_in_minutes: int = 30

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int
    full_name: str
    email: str
    is_verified: bool = True

class UserOut(BaseModel):
    user_id: int
    full_name: str
    email: str
    role: str
    created_at: datetime
    is_verified: bool = False
    verified_at: Optional[datetime] = None

    class Config:
        from_attributes = True
