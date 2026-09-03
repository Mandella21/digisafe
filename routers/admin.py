import io
import csv
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import get_current_user, require_roles
from models.user import User
from models.evidence import Evidence
from models.audit_log import AuditLog
from models.alert import Alert
from services.encryption_service import decrypt_content
from services.hashing_service import verify_and_recover
from core.security import hash_password
from schemas.admin import DashboardStats, FlagCaseRequest, CreateStaffRequest, StaffCreatedResponse

router = APIRouter()

@router.get("/stats", response_model=DashboardStats)
def get_dashboard_statistics(
    current_user: User = Depends(require_roles(["admin", "officer"])),
    db: Session = Depends(get_db)
):
    """Section 4.1.2 Summary Statistics for Admin/Officer Dashboard."""
    total_submissions = db.query(Evidence).count()
    flagged_cases = db.query(Evidence).filter(Evidence.status == "flagged").count()
    verified_records = db.query(Evidence).filter(Evidence.status == "verified").count()
    compromised_records = db.query(Evidence).filter(Evidence.status == "compromised").count()
    active_users = db.query(User).count()

    return DashboardStats(
        total_submissions=total_submissions,
        flagged_cases=flagged_cases,
        verified_records=verified_records,
        compromised_records=compromised_records,
        active_users=active_users
    )

@router.get("/evidence")
def list_all_evidence(
    status_filter: Optional[str] = None,
    threat_filter: Optional[str] = None,
    current_user: User = Depends(require_roles(["admin", "officer"])),
    db: Session = Depends(get_db)
):
    """Section 3.9.2: Browse all submissions with status/severity filters."""
    query = db.query(Evidence).order_by(Evidence.submitted_at.desc())
    if status_filter and status_filter.lower() != "all":
        query = query.filter(Evidence.status == status_filter.lower())

    records = query.all()
    results = []
    for r in records:
        tl = r.classification.threat_level if r.classification else "None"
        if threat_filter and threat_filter.lower() != "all" and tl.lower() != threat_filter.lower():
            continue

        results.append({
            "evidence_id": r.evidence_id,
            "victim_id": r.victim_id,
            "victim_name": r.owner.full_name if r.owner else "Anonymous",
            "content_type": r.content_type,
            "content_preview": decrypt_content(r.content)[:85] + ("..." if len(decrypt_content(r.content)) > 85 else ""),
            "content_full": decrypt_content(r.content),
            "source_url": r.source_url,
            "file_path": r.file_path,
            "submitted_at": r.submitted_at.strftime("%Y-%m-%d %H:%M:%S") if r.submitted_at else "N/A",
            "status": r.status,
            "hash_value": r.hash_record.hash_value if r.hash_record else "N/A",
            "threat_level": tl,
            "confidence_score": r.classification.confidence_score if r.classification else 0.0,
            "ml_label": r.classification.label if r.classification else "Pending"
        })
    return results

@router.post("/evidence/{evidence_id}/status")
def update_case_status(
    evidence_id: int,
    payload: FlagCaseRequest,
    current_user: User = Depends(require_roles(["admin", "officer"])),
    db: Session = Depends(get_db)
):
    """Update case status (flagged, reviewed, verified, compromised)."""
    evidence = db.query(Evidence).filter(Evidence.evidence_id == evidence_id).first()
    if not evidence:
        raise HTTPException(404, "Evidence record not found")

    old_status = evidence.status
    evidence.status = payload.status.lower()

    db.add(AuditLog(
        user_id=current_user.user_id,
        action="UPDATE_CASE_STATUS",
        entity_type="Evidence",
        entity_id=evidence.evidence_id,
        details=f"Status updated from '{old_status}' to '{evidence.status}' by {current_user.role} {current_user.full_name}. Notes: {payload.notes or 'None'}"
    ))
    db.commit()
    return {"message": f"Case #{evidence_id} status updated to '{evidence.status}'."}

@router.post("/evidence/{evidence_id}/simulate-tamper")
def simulate_tampering(
    evidence_id: int,
    current_user: User = Depends(require_roles(["admin", "officer"])),
    db: Session = Depends(get_db)
):
    """
    DEMONSTRATION TOOL (Section 4.2.3 IT-02 & Section 4.3):
    Deliberately modifies the stored ciphertext in the database to demonstrate
    that the Checksum Verification function catches tampering live during assessment.
    """
    evidence = db.query(Evidence).filter(Evidence.evidence_id == evidence_id).first()
    if not evidence:
        raise HTTPException(404, "Evidence not found")

    from services.encryption_service import encrypt_content
    # Tamper with the content
    tampered_text = decrypt_content(evidence.content) + " [TAMPERED_MODIFIED_DATA]"
    evidence.content = encrypt_content(tampered_text)
    db.commit()

    # Now verify immediately to prove that the recovery/alert technique catches it
    result = verify_and_recover(evidence_id, db, user_id=current_user.user_id)
    return {
        "action": "Tampering simulated on record",
        "verification_result": result
    }

@router.post("/users", response_model=StaffCreatedResponse, status_code=status.HTTP_201_CREATED)
def create_staff_account(
    payload: CreateStaffRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["admin"])),
):
    """Create an administrator or law enforcement officer account.

    Restricted to administrators. This exists because public registration
    always produces a victim account - a privileged role can never be
    self-assigned - so there has to be a controlled path for provisioning
    staff. Section 3.6 assigns this responsibility to the System Administrator.
    """
    requested_role = (payload.role or "").strip().lower()
    if requested_role not in ("admin", "officer"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role must be either 'admin' or 'officer'.",
        )

    email_clean = payload.email.strip().lower()
    if db.query(User).filter(User.email == email_clean).first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists.",
        )

    if len(payload.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Privileged accounts require a password of at least 8 characters.",
        )

    # An account handed out in person by an administrator has already had its
    # owner identified; there is no inbox to prove ownership of and no one to
    # read a code sent to a police address the officer may not control yet.
    # So staff accounts start verified and can sign in straight away.
    staff = User(
        full_name=payload.full_name.strip(),
        email=email_clean,
        password_hash=hash_password(payload.password),
        role=requested_role,
        is_verified=True,
        verified_at=datetime.utcnow(),
    )
    db.add(staff)
    db.commit()
    db.refresh(staff)

    # Creating a privileged account is exactly the kind of action the audit log
    # exists for (Section 3.8.2: log every administrative action).
    db.add(AuditLog(
        user_id=current_user.user_id,
        action="STAFF_ACCOUNT_CREATED",
        entity_type="User",
        entity_id=staff.user_id,
        details=(
            f"Administrator {current_user.email} created {staff.role} "
            f"account for {staff.email}"
        ),
    ))
    db.commit()

    return StaffCreatedResponse(
        user_id=staff.user_id,
        full_name=staff.full_name,
        email=staff.email,
        role=staff.role,
        message=f"{staff.role.capitalize()} account created successfully.",
    )


@router.get("/audit-logs")
def get_audit_logs(
    limit: int = 100,
    action_filter: Optional[str] = None,
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db)
):
    """Section 3.15.1 Figure 3.16: System Audit Log viewer for Admin."""
    query = db.query(AuditLog).order_by(AuditLog.performed_at.desc())
    if action_filter and action_filter.lower() != "all":
        query = query.filter(AuditLog.action == action_filter.upper())

    logs = query.limit(limit).all()
    return [{
        "log_id": l.log_id,
        "user_id": l.user_id,
        "user_name": l.user.full_name if l.user else "System",
        "role": l.user.role if l.user else "System",
        "action": l.action,
        "entity_type": l.entity_type,
        "entity_id": l.entity_id,
        "details": l.details,
        "performed_at": l.performed_at.strftime("%Y-%m-%d %H:%M:%S") if l.performed_at else "N/A"
    } for l in logs]

@router.get("/audit-logs/export-csv")
def export_audit_logs_csv(
    current_user: User = Depends(require_roles(["admin"])),
    db: Session = Depends(get_db)
):
    """Export audit log to CSV as specified in Section 3.15.1."""
    logs = db.query(AuditLog).order_by(AuditLog.performed_at.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Log ID", "User ID", "User Name", "Role", "Action", "Entity Type", "Entity ID", "Details", "Timestamp"])

    for l in logs:
        writer.writerow([
            l.log_id,
            l.user_id or "System",
            l.user.full_name if l.user else "System",
            l.user.role if l.user else "System",
            l.action,
            l.entity_type or "",
            l.entity_id or "",
            l.details or "",
            l.performed_at.strftime("%Y-%m-%d %H:%M:%S") if l.performed_at else ""
        ])

    csv_data = output.getvalue()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=digisafe_audit_logs.csv"}
    )

@router.get("/alerts")
def get_system_alerts(
    current_user: User = Depends(require_roles(["admin", "officer"])),
    db: Session = Depends(get_db)
):
    """Get active alerts."""
    alerts = db.query(Alert).filter(Alert.acknowledged == False).order_by(Alert.created_at.desc()).all()
    return [{
        "alert_id": a.alert_id,
        "evidence_id": a.evidence_id,
        "message": a.message,
        "severity": a.severity,
        "created_at": a.created_at.strftime("%Y-%m-%d %H:%M:%S") if a.created_at else "N/A"
    } for a in alerts]

@router.post("/alerts/{alert_id}/ack")
def acknowledge_alert(
    alert_id: int,
    current_user: User = Depends(require_roles(["admin", "officer"])),
    db: Session = Depends(get_db)
):
    alert = db.query(Alert).filter(Alert.alert_id == alert_id).first()
    if alert:
        alert.acknowledged = True
        db.commit()
    return {"message": "Alert acknowledged"}
