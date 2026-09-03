from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class DashboardStats(BaseModel):
    total_submissions: int
    flagged_cases: int
    verified_records: int
    compromised_records: int
    active_users: int

class FlagCaseRequest(BaseModel):
    status: str # flagged, reviewed, verified, compromised
    notes: Optional[str] = None

class TamperSimulateRequest(BaseModel):
    evidence_id: int


class CreateStaffRequest(BaseModel):
    """Administrator-initiated creation of a privileged account.

    Privileged roles cannot be self-assigned at registration (see
    routers/auth.py), so this is the only route by which an administrator or
    law enforcement officer account comes into existence.
    """
    full_name: str
    email: str
    password: str
    role: str  # "admin" or "officer"


class StaffCreatedResponse(BaseModel):
    user_id: int
    full_name: str
    email: str
    role: str
    message: str
