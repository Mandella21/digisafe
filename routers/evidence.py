import os
import uuid
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.security import get_current_user
from models.user import User
from models.evidence import Evidence
from models.hash_record import HashRecord
from models.ml_classification import MLClassification
from models.audit_log import AuditLog
from models.alert import Alert

from services.encryption_service import encrypt_content, decrypt_content
from services.hashing_service import generate_sha256_hash, generate_file_hash, verify_and_recover
from services.ml_service import classify_text

router = APIRouter()

ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".pdf", ".txt", ".docx", ".webp"}
MAX_FILE_SIZE_MB = 10

@router.post("/submit")
async def submit_evidence(
    content_type: str = Form("text"),
    source_url: Optional[str] = Form(None),
    content: str = Form(...),
    file: Optional[UploadFile] = File(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Section 3.12.1 Evidence Submission Algorithm.
    Atomically generates SHA-256 hash, AES encryption, ML classification, and persists record.
    """
    if not content or not content.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Evidence content cannot be empty."
        )

    file_path = None
    file_hash_val = None

    if file and file.filename:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
            )

        file_bytes = await file.read()
        if len(file_bytes) > MAX_FILE_SIZE_MB * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File exceeds maximum allowed limit of {MAX_FILE_SIZE_MB}MB."
            )

        unique_name = f"{uuid.uuid4().hex}{ext}"
        target_path = settings.UPLOAD_DIR / unique_name
        with open(target_path, "wb") as f_dst:
            f_dst.write(file_bytes)

        file_path = str(target_path)
        file_hash_val = generate_file_hash(file_bytes)

    # 1. Cryptographic Hashing (SHA-256) of raw content
    hash_result = generate_sha256_hash(content)

    # 2. Data Shuffling / AES-256 Encryption of content
    encrypted_content = encrypt_content(content)

    # 3. Machine Learning Content Analysis
    ml_result = classify_text(content)

    # Initial status
    initial_status = "pending"
    if ml_result["threat_level"] in ["High", "Critical"]:
        initial_status = "flagged"

    # 4. Atomic Database Persistence
    try:
        evidence = Evidence(
            victim_id=current_user.user_id,
            content_type=content_type,
            content=encrypted_content,
            source_url=source_url,
            file_path=file_path,
            file_hash=file_hash_val,
            submitted_at=datetime.utcnow(),
            status=initial_status
        )
        db.add(evidence)
        db.flush() # obtain evidence.evidence_id

        # Add Hash Record
        hash_record = HashRecord(
            evidence_id=evidence.evidence_id,
            hash_value=hash_result["hash_value"],
            algorithm=hash_result["algorithm"],
            created_at=hash_result["created_at"]
        )
        db.add(hash_record)

        # Add ML Classification Record
        classification = MLClassification(
            evidence_id=evidence.evidence_id,
            label=ml_result["label"],
            confidence_score=ml_result["confidence_score"],
            threat_level=ml_result["threat_level"],
            model_version=ml_result["model_version"],
            classified_at=datetime.utcnow()
        )
        db.add(classification)

        # If high threat, create alert
        if initial_status == "flagged":
            db.add(Alert(
                user_id=current_user.user_id,
                evidence_id=evidence.evidence_id,
                message=f"High risk abuse detected on Evidence #{evidence.evidence_id} ({ml_result['threat_level']}). Requires immediate review.",
                severity=ml_result["threat_level"],
                acknowledged=False
            ))

        # Log to Audit Trail
        db.add(AuditLog(
            user_id=current_user.user_id,
            action="SUBMIT_EVIDENCE",
            entity_type="Evidence",
            entity_id=evidence.evidence_id,
            details=f"Evidence #{evidence.evidence_id} captured. SHA-256: {hash_result['hash_value'][:16]}... ML: {ml_result['label']} ({ml_result['threat_level']})"
        ))

        db.commit()
        db.refresh(evidence)

        return {
            "evidence_id": evidence.evidence_id,
            "status": evidence.status,
            "hash_value": hash_result["hash_value"],
            "ml_classification": ml_result,
            "submitted_at": evidence.submitted_at.isoformat(),
            "message": "Evidence securely captured, cryptographically hashed, and encrypted at rest."
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Evidence submission failed: {str(e)}"
        )

@router.get("/my")
def get_my_evidence(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve all evidence submitted by current victim."""
    records = db.query(Evidence).filter(Evidence.victim_id == current_user.user_id).order_by(Evidence.submitted_at.desc()).all()
    out = []
    for r in records:
        out.append({
            "evidence_id": r.evidence_id,
            "content_type": r.content_type,
            "content_decrypted": decrypt_content(r.content),
            "source_url": r.source_url,
            "file_path": r.file_path,
            "file_name": os.path.basename(r.file_path) if r.file_path else None,
            "submitted_at": r.submitted_at.strftime("%Y-%m-%d %H:%M:%S") if r.submitted_at else "N/A",
            "status": r.status,
            "hash_value": r.hash_record.hash_value if r.hash_record else "N/A",
            "ml_label": r.classification.label if r.classification else "Pending",
            "threat_level": r.classification.threat_level if r.classification else "None",
            "confidence_score": r.classification.confidence_score if r.classification else 0.0
        })
    return out

@router.get("/{evidence_id}")
def get_evidence_detail(
    evidence_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get detail of single evidence record (authorized for owner, admin, or officer)."""
    evidence = db.query(Evidence).filter(Evidence.evidence_id == evidence_id).first()
    if not evidence:
        raise HTTPException(404, "Evidence record not found")

    if current_user.role.lower() == "victim" and evidence.victim_id != current_user.user_id:
        raise HTTPException(403, "Not authorized to view this evidence record")

    return {
        "evidence_id": evidence.evidence_id,
        "victim_id": evidence.victim_id,
        "victim_name": evidence.owner.full_name if evidence.owner else "Anonymous",
        "content_type": evidence.content_type,
        "content_decrypted": decrypt_content(evidence.content),
        "source_url": evidence.source_url,
        "file_path": evidence.file_path,
        "file_name": os.path.basename(evidence.file_path) if evidence.file_path else None,
        "submitted_at": evidence.submitted_at.strftime("%Y-%m-%d %H:%M:%S") if evidence.submitted_at else "N/A",
        "status": evidence.status,
        "hash_record": {
            "hash_value": evidence.hash_record.hash_value if evidence.hash_record else None,
            "algorithm": evidence.hash_record.algorithm if evidence.hash_record else "SHA-256"
        },
        "classification": {
            "label": evidence.classification.label if evidence.classification else "Pending",
            "confidence_score": evidence.classification.confidence_score if evidence.classification else 0.0,
            "threat_level": evidence.classification.threat_level if evidence.classification else "None",
            "model_version": evidence.classification.model_version if evidence.classification else "v1.0"
        }
    }

@router.post("/{evidence_id}/verify")
def verify_evidence_integrity(
    evidence_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Section 4.1.8 Checksum Data Recovery Technique.
    Re-computes checksum and confirms authenticity or flags tampering.
    """
    result = verify_and_recover(evidence_id, db, user_id=current_user.user_id)
    return result
