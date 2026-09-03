import os
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from core.database import get_db
from core.security import get_current_user
from models.user import User
from models.evidence import Evidence
from models.report import Report
from models.audit_log import AuditLog
from services.report_service import generate_evidence_report

router = APIRouter()

@router.post("/generate/{evidence_id}")
def create_report(
    evidence_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Section 3.12.4: Generate a court-admissible PDF report."""
    evidence = db.query(Evidence).filter(Evidence.evidence_id == evidence_id).first()
    if not evidence:
        raise HTTPException(404, "Evidence not found")

    if current_user.role.lower() == "victim" and evidence.victim_id != current_user.user_id:
        raise HTTPException(403, "Not authorized to generate report for this case")

    victim_name = evidence.owner.full_name if evidence.owner else "Protected Complainant"
    victim_email = evidence.owner.email if evidence.owner else "N/A"

    try:
        pdf_path = generate_evidence_report(evidence, victim_name, victim_email)

        report_rec = Report(
            evidence_id=evidence.evidence_id,
            victim_id=evidence.victim_id,
            file_path=pdf_path
        )
        db.add(report_rec)
        db.add(AuditLog(
            user_id=current_user.user_id,
            action="GENERATE_PDF_REPORT",
            entity_type="Report",
            entity_id=evidence.evidence_id,
            details=f"Official PDF report generated for Case #{evidence.evidence_id}"
        ))
        db.commit()
        db.refresh(report_rec)

        return {
            "report_id": report_rec.report_id,
            "evidence_id": evidence.evidence_id,
            "download_url": f"/api/reports/download/{evidence.evidence_id}",
            "message": "Court-admissible PDF evidence report generated successfully."
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(500, f"Failed to generate report: {str(e)}")

@router.get("/download/{evidence_id}")
def download_report(
    evidence_id: int,
    token: str = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Download the generated PDF report."""
    evidence = db.query(Evidence).filter(Evidence.evidence_id == evidence_id).first()
    if not evidence:
        raise HTTPException(404, "Evidence not found")

    if current_user.role.lower() == "victim" and evidence.victim_id != current_user.user_id:
        raise HTTPException(403, "Access denied")

    # Check for latest report or generate on the fly
    latest_report = db.query(Report).filter(Report.evidence_id == evidence_id).order_by(Report.generated_at.desc()).first()

    if latest_report and os.path.exists(latest_report.file_path):
        file_path = latest_report.file_path
    else:
        # Generate fresh report
        victim_name = evidence.owner.full_name if evidence.owner else "Protected Complainant"
        victim_email = evidence.owner.email if evidence.owner else "N/A"
        file_path = generate_evidence_report(evidence, victim_name, victim_email)

        new_rep = Report(
            evidence_id=evidence.evidence_id,
            victim_id=evidence.victim_id,
            file_path=file_path
        )
        db.add(new_rep)
        db.commit()

    return FileResponse(
        path=file_path,
        media_type="application/pdf",
        filename=f"DigiSafe_Evidence_Report_Case_{evidence_id}.pdf"
    )
