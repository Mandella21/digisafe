from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class EvidenceCreate(BaseModel):
    content_type: str = "text" # text, url, file
    content: str
    source_url: Optional[str] = None

class MLResultOut(BaseModel):
    label: str
    confidence_score: float
    threat_level: str
    model_version: str

    class Config:
        from_attributes = True

class HashRecordOut(BaseModel):
    hash_value: str
    algorithm: str
    created_at: datetime

    class Config:
        from_attributes = True

class EvidenceOut(BaseModel):
    evidence_id: int
    victim_id: int
    content_type: str
    content: str # decrypted for authorized viewer
    source_url: Optional[str]
    file_path: Optional[str]
    file_hash: Optional[str]
    submitted_at: datetime
    status: str
    hash_record: Optional[HashRecordOut]
    classification: Optional[MLResultOut]

    class Config:
        from_attributes = True
