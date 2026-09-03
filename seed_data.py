from datetime import datetime, timedelta
from core.database import SessionLocal, engine
from models.base import Base
from models.user import User
from models.evidence import Evidence
from models.hash_record import HashRecord
from models.ml_classification import MLClassification
from models.audit_log import AuditLog
from models.alert import Alert
from core.security import hash_password
from services.hashing_service import generate_sha256_hash
from services.encryption_service import encrypt_content
from services.ml_service import classify_text

def seed_database():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        # Check if users already exist
        if db.query(User).count() > 0:
            print("Database already initialized with seed data.")
            return

        print("Seeding default accounts and evidence records...")

        # 1. Create Default Users
        # Seeded accounts are marked verified: they exist to be signed into
        # during a walkthrough, and nobody can read mail at digisafe.org to
        # confirm them.
        verified_now = datetime.utcnow()
        victim = User(
            full_name="Ama Serwaa (Complainant)",
            email="victim@digisafe.org",
            password_hash=hash_password("Victim@123"),
            role="victim",
            created_at=datetime.utcnow() - timedelta(days=2),
            is_verified=True,
            verified_at=verified_now
        )
        officer = User(
            full_name="Inspector Kwesi Mensah (Cybercrime Unit)",
            email="officer@police.gov.gh",
            password_hash=hash_password("Officer@123"),
            role="officer",
            created_at=datetime.utcnow() - timedelta(days=5),
            is_verified=True,
            verified_at=verified_now
        )
        admin = User(
            full_name="DigiSafe System Administrator",
            email="admin@digisafe.org",
            password_hash=hash_password("Admin@123"),
            role="admin",
            created_at=datetime.utcnow() - timedelta(days=10),
            is_verified=True,
            verified_at=verified_now
        )

        db.add_all([victim, officer, admin])
        db.commit()
        db.refresh(victim)
        db.refresh(officer)
        db.refresh(admin)

        # 2. Seed Evidence Cases
        cases = [
            {
                "type": "text",
                "source": "WhatsApp (+233 24 111 2233)",
                "content": "I know where you stay in Kumasi. If you ever report me to anyone, I will track you down and hurt you severely. Watch your back.",
                "status": "flagged",
                "days_ago": 1
            },
            {
                "type": "url",
                "source": "https://instagram.com/p/harassment_report_sample",
                "content": "Pay me 5000 GHS immediately or I will leak your private photos across all student Telegram groups and ruin your life.",
                "status": "flagged",
                "days_ago": 2
            },
            {
                "type": "text",
                "source": "SMS Message",
                "content": "Please remember to return the course lecture notes you borrowed by Friday before the departmental seminar.",
                "status": "verified",
                "days_ago": 3
            }
        ]

        for c in cases:
            sub_time = datetime.utcnow() - timedelta(days=c["days_ago"])
            h_info = generate_sha256_hash(c["content"])
            enc_text = encrypt_content(c["content"])
            ml_info = classify_text(c["content"])

            ev = Evidence(
                victim_id=victim.user_id,
                content_type=c["type"],
                content=enc_text,
                source_url=c["source"],
                submitted_at=sub_time,
                status=c["status"]
            )
            db.add(ev)
            db.flush()

            db.add(HashRecord(
                evidence_id=ev.evidence_id,
                hash_value=h_info["hash_value"],
                algorithm="SHA-256",
                created_at=sub_time
            ))

            db.add(MLClassification(
                evidence_id=ev.evidence_id,
                label=ml_info["label"],
                confidence_score=ml_info["confidence_score"],
                threat_level=ml_info["threat_level"],
                model_version=ml_info["model_version"],
                classified_at=sub_time
            ))

            db.add(AuditLog(
                user_id=victim.user_id,
                action="SUBMIT_EVIDENCE",
                entity_type="Evidence",
                entity_id=ev.evidence_id,
                details=f"Evidence #{ev.evidence_id} captured. SHA-256: {h_info['hash_value'][:16]}... Threat: {ml_info['threat_level']}",
                performed_at=sub_time
            ))

            if c["status"] == "flagged":
                db.add(Alert(
                    user_id=victim.user_id,
                    evidence_id=ev.evidence_id,
                    message=f"High risk abuse detected on Evidence #{ev.evidence_id} ({ml_info['threat_level']}). Requires immediate review.",
                    severity=ml_info["threat_level"],
                    acknowledged=False,
                    created_at=sub_time
                ))

        db.commit()
        print("Database seeded successfully with default users and demonstration cases.")
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
