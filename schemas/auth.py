from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class RegisterRequest(BaseModel):
    full_name: str
    email: str
    password: str
    role: Optional[str] = "victim" # victim, admin, officer

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
