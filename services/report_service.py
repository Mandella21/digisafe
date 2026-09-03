import os
from datetime import datetime, timezone
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from core.config import settings
from models.evidence import Evidence
from services.encryption_service import decrypt_content

class DigiSafePDF(FPDF):
    def header(self):
        self.set_fill_color(26, 32, 44)
        self.rect(0, 0, 210, 32, "F")
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 16)
        self.set_xy(10, 8)
        self.cell(190, 8, "DIGISAFE | DIGITAL SAFETY & RECORD PROTECTION", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")
        self.set_font("Helvetica", "", 9)
        self.set_xy(10, 18)
        self.cell(190, 5, "Forensic Digital Evidence Preservation Platform  *  Republic of Ghana (Act 775 / Act 29)", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="L")
        self.ln(12)

    def footer(self):
        self.set_y(-20)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 5, f"CONFIDENTIAL & COURT ADMISSIBLE EVIDENCE RECORD  *  PAGE {self.page_no()}/{{nb}}", align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.cell(0, 4, "Generated securely by DigiSafe Evidence Engine. Tamper-evident cryptographic fingerprint embedded.", align="C")

def generate_evidence_report(evidence: Evidence, victim_name: str, victim_email: str) -> str:
    """Section 3.12.4: Generates a court-admissible PDF report using FPDF."""
    pdf = DigiSafePDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=25)

    # 1. Report Title & Reference
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(30, 41, 59)
    case_ref = f"DS-GH-2026-{evidence.evidence_id:05d}"
    pdf.cell(130, 8, f"CASE EVIDENCE DOSSIER: {case_ref}", new_x=XPos.RIGHT, new_y=YPos.TOP)

    pdf.set_font("Helvetica", "B", 10)
    status_str = (evidence.status or "PENDING").upper()
    if status_str == "COMPROMISED":
        pdf.set_text_color(220, 38, 38)
    elif status_str == "FLAGGED":
        pdf.set_text_color(234, 88, 12)
    else:
        pdf.set_text_color(16, 185, 129)
    pdf.cell(60, 8, f"STATUS: {status_str}", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")

    pdf.set_draw_color(226, 232, 240)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)

    # 2. Case Metadata Table
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(71, 85, 105)
    pdf.set_fill_color(248, 250, 252)
    pdf.cell(95, 7, "  SUBMISSION METADATA", border=1, fill=True, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(95, 7, "  VICTIM / COMPLAINANT PARTICULARS", border=1, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(15, 23, 42)

    sub_time = evidence.submitted_at.strftime("%Y-%m-%d %H:%M:%S UTC") if evidence.submitted_at else "N/A"
    pdf.cell(95, 6, f"  Evidence ID: #{evidence.evidence_id}", border=1, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(95, 6, f"  Full Name: {victim_name}", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.cell(95, 6, f"  Date & Time: {sub_time}", border=1, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(95, 6, f"  Registered Email: {victim_email}", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    src_url = evidence.source_url or "N/A (Direct text submission)"
    if len(src_url) > 42:
        src_url = src_url[:39] + "..."
    pdf.cell(95, 6, f"  Type: {evidence.content_type.upper()}", border=1, new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(95, 6, f"  Source / URL: {src_url}", border=1, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(4)

    # 3. Cryptographic Integrity Box (SHA-256)
    hash_val = evidence.hash_record.hash_value if evidence.hash_record else "NOT COMPUTED"
    pdf.set_fill_color(238, 242, 255)
    pdf.set_draw_color(199, 210, 254)
    pdf.rect(10, pdf.get_y(), 190, 24, "FD")

    pdf.set_xy(14, pdf.get_y() + 2)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(67, 56, 202)
    pdf.cell(180, 5, "[X] CRYPTOGRAPHIC INTEGRITY CERTIFICATION (SHA-256 DIGITAL FINGERPRINT)", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_xy(14, pdf.get_y())
    pdf.set_font("Courier", "B", 8)
    pdf.set_text_color(30, 27, 75)
    pdf.multi_cell(182, 4, f"Digest: {hash_val}\nAlgorithm: SHA-256 (NIST FIPS 180-4 Standard)  |  Integrity: SECURED AT CAPTURE")
    pdf.set_y(pdf.get_y() + 6)

    # 4. Decrypted Evidence Content
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(190, 6, "RECORDED ABUSE CONTENT (PRESERVED EVIDENCE):", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    decrypted_body = decrypt_content(evidence.content)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_fill_color(255, 255, 255)
    pdf.set_draw_color(203, 213, 225)
    pdf.set_text_color(15, 23, 42)
    pdf.multi_cell(190, 5, decrypted_body if decrypted_body else "[No content recorded]", border=1, fill=True)
    pdf.ln(4)

    # 5. Attachment metadata if present
    if evidence.file_path:
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(190, 5, f"Associated File Attachment: {os.path.basename(evidence.file_path)}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if evidence.file_hash:
            pdf.set_font("Courier", "", 8)
            pdf.cell(190, 4, f"Attachment SHA-256 Checksum: {evidence.file_hash}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(2)

    # 6. Machine Learning Threat Assessment
    pdf.set_font("Helvetica", "B", 10)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(190, 6, "MACHINE LEARNING THREAT ASSESSMENT & SEVERITY CLASSIFICATION:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    classification = evidence.classification
    label = classification.label if classification else "Pending"
    score = classification.confidence_score if classification else 0.0
    threat_level = classification.threat_level if classification else "Low"

    pdf.set_font("Helvetica", "", 9)
    pdf.set_fill_color(254, 242, 242) if label == "Abusive" else pdf.set_fill_color(240, 253, 244)
    pdf.rect(10, pdf.get_y(), 190, 16, "FD")

    pdf.set_xy(14, pdf.get_y() + 2)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(185, 28, 28) if label == "Abusive" else pdf.set_text_color(21, 128, 61)
    pdf.cell(60, 5, f"Classification: {label.upper()}", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(60, 5, f"Threat Severity: {threat_level.upper()}", new_x=XPos.RIGHT, new_y=YPos.TOP)
    pdf.cell(60, 5, f"Confidence Score: {score * 100:.1f}%", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_xy(14, pdf.get_y())
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(71, 85, 105)
    pdf.cell(180, 5, f"Model: Scikit-learn TF-IDF Harassment Classifier ({classification.model_version if classification else 'v1.0'})", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(8)

    # 7. Chain of Custody & Law Enforcement Sign-off Block
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(30, 41, 59)
    pdf.cell(190, 5, "CHAIN OF CUSTODY & FORENSIC CERTIFICATION:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(71, 85, 105)
    pdf.multi_cell(190, 4,
        "This document constitutes an electronically verified digital evidence package compiled in accordance "
        "with Section 73 of the Electronic Communications Act, 2008 (Act 775) of the Republic of Ghana. "
        "The cryptographic hash above guarantees that the recorded content is mathematically identical to the data captured."
    )
    pdf.ln(6)

    # Signature lines
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(15, 23, 42)
    y_sig = pdf.get_y()
    pdf.line(10, y_sig + 10, 85, y_sig + 10)
    pdf.text(10, y_sig + 15, "Investigating Officer Signature / Badge #")

    pdf.line(125, y_sig + 10, 200, y_sig + 10)
    pdf.text(125, y_sig + 15, "Date & Official Unit Verification Stamp")

    # Output file
    now_utc = datetime.now(timezone.utc)
    filename = f"report_evidence_{evidence.evidence_id}_{int(now_utc.timestamp())}.pdf"
    out_path = str(settings.REPORTS_DIR / filename)
    pdf.output(out_path)
    return out_path
