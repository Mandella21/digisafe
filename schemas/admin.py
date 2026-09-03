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
