import hashlib
from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from models.evidence import Evidence
from models.hash_record import HashRecord
from models.audit_log import AuditLog
from models.alert import Alert
from services.encryption_service import decrypt_content

def generate_sha256_hash(content: str) -> dict:
    """Section 4.1.6 Cryptographic Hashing: Generates SHA-256 digital fingerprint."""
    encoded_content = content.encode("utf-8")
    hash_value = hashlib.sha256(encoded_content).hexdigest()
    return {
        "hash_value": hash_value,
        "algorithm": "SHA-256",
        "created_at": datetime.utcnow(),
    }

def generate_file_hash(file_bytes: bytes) -> str:
    """Generate SHA-256 hash for binary file content."""
    return hashlib.sha256(file_bytes).hexdigest()

def verify_and_recover(evidence_id: int, db: Session, user_id: Optional[int] = None) -> dict:
    """
    Section 4.1.8 Checksum Data Recovery Technique.
    Re-computes checksum of stored evidence content and compares against the captured hash.
    Flags tampering and raises alert rather than silently altering record.
    """
    evidence = db.query(Evidence).filter(Evidence.evidence_id == evidence_id).first()
    if not evidence:
        return {"error": "Evidence not found", "status": "not_found", "tampered": False}

    hash_record = evidence.hash_record
    if not hash_record:
        return {"error": "No hash record found for evidence", "status": "missing_hash", "tampered": False}

    decrypted_content = decrypt_content(evidence.content)
    recomputed_hash = hashlib.sha256(decrypted_content.encode("utf-8")).hexdigest()
    original_hash = hash_record.hash_value

    if recomputed_hash != original_hash:
        evidence.status = "compromised"
        db.add(AuditLog(
            user_id=user_id,
            action="CHECKSUM_MISMATCH",
            entity_type="Evidence",
            entity_id=evidence.evidence_id,
            details=f"Tampering detected! Stored: {original_hash[:16]}... Recomputed: {recomputed_hash[:16]}..."
        ))
        db.add(Alert(
            user_id=user_id,
            evidence_id=evidence.evidence_id,
            message=f"CRITICAL: Checksum mismatch on Evidence #{evidence.evidence_id}. Potential evidence tampering detected.",
            severity="High",
            acknowledged=False
        ))
        db.commit()
        return {
            "status": "compromised",
            "is_valid": False,
            "tampered": True,
            "original_hash": original_hash,
            "recomputed_hash": recomputed_hash,
            "message": "INTEGRITY BREACH: Checksum mismatch! The stored evidence content differs from its original cryptographic fingerprint."
        }

    # Verified clean
    db.add(AuditLog(
        user_id=user_id,
        action="VERIFY_INTEGRITY_PASS",
        entity_type="Evidence",
        entity_id=evidence.evidence_id,
        details=f"Cryptographic integrity confirmed. SHA-256 matches: {original_hash}"
    ))
    db.commit()
    return {
        "status": "verified",
        "is_valid": True,
        "tampered": False,
        "original_hash": original_hash,
        "recomputed_hash": recomputed_hash,
        "message": "Cryptographic integrity verified. Digital evidence fingerprint is authentic and unaltered."
    }
