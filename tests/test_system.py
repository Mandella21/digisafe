import unittest
import os
from core.database import SessionLocal, engine, ensure_schema
from seed_data import seed_database
from models.base import Base
from models.user import User
from models.evidence import Evidence
from models.hash_record import HashRecord
from models.ml_classification import MLClassification
from models.audit_log import AuditLog
from models.alert import Alert
from core.security import hash_password, verify_password, create_access_token, decode_access_token
from services.hashing_service import generate_sha256_hash, generate_file_hash, verify_and_recover
from services.encryption_service import encrypt_content, decrypt_content
from services.ml_service import classify_text
from services.report_service import generate_evidence_report

class TestDigiSafeDirect(unittest.TestCase):
    """End-to-end checks against the real service layer.

    The suite is self-sufficient: it creates the schema and its own fixture
    data if the database is empty, so it runs correctly on a fresh checkout
    with no digisafe.db present. Tests that depend on an evidence record
    obtain it through _fixture_evidence() rather than assuming one was left
    behind by a previous run.
    """

    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        ensure_schema()
        seed_database()

    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def _fixture_evidence(self):
        """Return an evidence record, creating one if the database is empty."""
        evidence = self.db.query(Evidence).first()
        if evidence is not None:
            return evidence

        user = self.db.query(User).first()
        if user is None:
            user = User(
                full_name="Test Complainant",
                email="fixture@digisafe.org",
                password_hash=hash_password("Fixture@123"),
                role="victim",
            )
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)

        plaintext = "I know where you live and I will hurt you if you report me."
        evidence = Evidence(
            victim_id=user.user_id,
            content_type="text",
            content=encrypt_content(plaintext),
            source_url="whatsapp",
            status="flagged",
        )
        self.db.add(evidence)
        self.db.commit()
        self.db.refresh(evidence)

        hash_result = generate_sha256_hash(plaintext)
        self.db.add(HashRecord(
            evidence_id=evidence.evidence_id,
            hash_value=hash_result["hash_value"],
            algorithm=hash_result["algorithm"],
        ))

        ml_result = classify_text(plaintext)
        self.db.add(MLClassification(
            evidence_id=evidence.evidence_id,
            label=ml_result["label"],
            confidence_score=ml_result["confidence_score"],
            threat_level=ml_result["threat_level"],
            model_version=ml_result["model_version"],
            detected_categories=", ".join(ml_result.get("detected_categories") or []) or None,
        ))
        self.db.commit()
        self.db.refresh(evidence)
        return evidence

    def test_01_password_and_jwt_security(self):
        """Test Section 4.1.4 Login & Security Module."""
        pwd = "SecurePassword@2026"
        hashed = hash_password(pwd)
        self.assertTrue(verify_password(pwd, hashed))
        self.assertFalse(verify_password("WrongPassword", hashed))

        token = create_access_token({"sub": "1", "role": "victim"})
        payload = decode_access_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["sub"], "1")
        self.assertEqual(payload["role"], "victim")

    def test_02_sha256_cryptographic_hashing(self):
        """Test Section 4.1.6 Cryptographic Hashing Implementation."""
        content = "Harassment message: You will never escape me."
        h_res = generate_sha256_hash(content)
        self.assertEqual(h_res["algorithm"], "SHA-256")
        self.assertEqual(len(h_res["hash_value"]), 64)
        # Verify deterministic hash property
        self.assertEqual(h_res["hash_value"], generate_sha256_hash(content)["hash_value"])

    def test_03_aes_data_shuffling_encryption(self):
        """Test Section 4.1.9 AES-256-CBC Data Shuffling."""
        plaintext = "Extremely sensitive personal abuse record."
        ciphertext = encrypt_content(plaintext)
        self.assertNotEqual(plaintext, ciphertext)
        self.assertNotIn(plaintext, ciphertext)

        recovered = decrypt_content(ciphertext)
        self.assertEqual(recovered, plaintext)

    def test_04_ml_harassment_classification(self):
        """Test Section 3.12.3 ML Harassment Detection.

        NOTE: confidence_score is the model's probability for the class it
        actually predicted (Section 3.12.3 step 6, "the associated confidence
        score"), so a confidently-clean message scores HIGH, not low.
        """
        # Critical Threat
        death_threat = "I will track you down in Kumasi and kill you tonight!"
        res_crit = classify_text(death_threat)
        self.assertEqual(res_crit["label"], "Abusive")
        self.assertIn(res_crit["threat_level"], ["High", "Critical"])
        self.assertGreaterEqual(res_crit["confidence_score"], 0.70)

        # Blackmail Threat
        blackmail = "Pay me 2000 GHS or I will leak all your private photos online!"
        res_blackmail = classify_text(blackmail)
        self.assertEqual(res_blackmail["label"], "Abusive")
        self.assertIn("Blackmail / Non-Consensual Extortion", res_blackmail["detected_categories"])

        # Benign Message
        benign = "Hello, kindly send the slides from today's computer science lecture."
        res_benign = classify_text(benign)
        self.assertEqual(res_benign["label"], "Non-Abusive")
        self.assertEqual(res_benign["threat_level"], "None")
        self.assertEqual(res_benign["detected_categories"], [])
        self.assertGreater(res_benign["confidence_score"], 0.70)

    def test_04b_ml_model_is_a_trained_sklearn_pipeline(self):
        """Objective 4 / Section 3.16: the classifier must be a real trained
        scikit-learn model loaded from disk, not a hard-coded rule list."""
        from sklearn.pipeline import Pipeline
        from sklearn.feature_extraction.text import TfidfVectorizer
        from services import ml_service

        self.assertTrue(ml_service.warmup(), "ML models failed to load")

        for key in ("binary", "category"):
            model = ml_service._models[key]
            self.assertIsInstance(model, Pipeline)
            self.assertIsInstance(model.named_steps["tfidf"], TfidfVectorizer)
            # A fitted vectoriser has a learned vocabulary.
            self.assertGreater(len(model.named_steps["tfidf"].vocabulary_), 200)

    def test_04c_ml_resists_hard_negatives(self):
        """The classifier must not flag ordinary messages that merely discuss
        abuse. This is what separates a trained model from keyword matching."""
        hard_negatives = [
            "our lecturer discussed cyberbullying and harassment in class today",
            "i am writing my project on detecting abusive messages online",
            "the news said a man was killed in an accident on the highway",
            "the counsellor gave a talk about domestic violence awareness",
            "i am really angry about how the meeting went today",
        ]
        for text in hard_negatives:
            with self.subTest(text=text):
                self.assertEqual(
                    classify_text(text)["label"], "Non-Abusive",
                    f"False positive on benign message: {text!r}",
                )

    def test_04d_ml_severity_bands_are_graded(self):
        """Section 3.3.6: severity must discriminate between kinds of abuse,
        not collapse every flagged item into one band."""
        cases = [
            ("i will kill you tonight and bury your body", "Critical"),
            ("pay me or i will leak your private pictures", "Critical"),
            ("i know where you live and i am watching your hostel every night", "High"),
            ("you are a worthless stupid idiot nobody likes you", "Medium"),
        ]
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(classify_text(text)["threat_level"], expected)

    def test_04e_ml_reports_multiple_categories(self):
        """A message that is both an extortion attempt and a violent threat
        must surface both categories, not just the top-ranked one."""
        result = classify_text(
            "pay me or i post the video and then i will come and break your legs"
        )
        self.assertEqual(result["label"], "Abusive")
        self.assertGreaterEqual(len(result["detected_categories"]), 2)
        self.assertEqual(result["threat_level"], "Critical")

    def test_04f_public_registration_cannot_self_assign_privileged_roles(self):
        """SECURITY REGRESSION (Sections 3.8.2 / 3.10).

        Public registration must always produce a victim account. Honouring a
        client-supplied role would let any member of the public register as
        {"role": "admin"} and read every victim's evidence.
        """
        from fastapi.testclient import TestClient
        from main import app

        with TestClient(app) as client:
            for attempted_role in ("admin", "officer", "ADMIN", "Admin"):
                with self.subTest(role=attempted_role):
                    response = client.post("/api/auth/register", json={
                        "full_name": "Privilege Escalation Probe",
                        "email": f"probe-{attempted_role.lower()}-{os.urandom(4).hex()}@example.com",
                        "password": "Probe@12345",
                        "role": attempted_role,
                    })
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(
                        response.json()["role"], "victim",
                        f"Registration granted '{attempted_role}' to a public sign-up",
                    )

                    # And the token it issued must be refused by admin endpoints.
                    token = response.json()["access_token"]
                    denied = client.get(
                        "/api/admin/stats",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    self.assertEqual(
                        denied.status_code, 403,
                        "A self-registered account reached an admin endpoint",
                    )

    def test_04g_only_admins_may_create_staff_accounts(self):
        """The controlled path for privileged accounts must itself be guarded."""
        from fastapi.testclient import TestClient
        from main import app

        with TestClient(app) as client:
            victim = client.post("/api/auth/login", json={
                "email": "victim@digisafe.org", "password": "Victim@123",
            })
            victim_token = victim.json()["access_token"]

            blocked = client.post(
                "/api/admin/users",
                headers={"Authorization": f"Bearer {victim_token}"},
                json={
                    "full_name": "Sneaky Officer", "email": "sneaky@example.com",
                    "password": "Sneaky@12345", "role": "officer",
                },
            )
            self.assertEqual(blocked.status_code, 403)

            admin = client.post("/api/auth/login", json={
                "email": "admin@digisafe.org", "password": "Admin@123",
            })
            admin_token = admin.json()["access_token"]

            created = client.post(
                "/api/admin/users",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={
                    "full_name": "DSP Kwame Officer",
                    "email": f"officer-{os.urandom(4).hex()}@police.gov.gh",
                    "password": "Officer@12345",
                    "role": "officer",
                },
            )
            self.assertEqual(created.status_code, 201)
            self.assertEqual(created.json()["role"], "officer")

    def test_05_checksum_data_recovery_and_tamper_detection(self):
        """Test Section 4.1.8 Checksum Data Recovery Technique (IT-02)."""
        ev = self._fixture_evidence()

        # 1. Authentic record check
        clean_check = verify_and_recover(ev.evidence_id, self.db)
        self.assertEqual(clean_check["status"], "verified")
        self.assertFalse(clean_check["tampered"])

        # 2. Simulate deliberate database tampering
        orig_content = ev.content
        ev.content = encrypt_content("UNAUTHORIZED FORGED TEXT")
        self.db.commit()

        # 3. Checksum verification detects tampering
        tamper_check = verify_and_recover(ev.evidence_id, self.db)
        self.assertEqual(tamper_check["status"], "compromised")
        self.assertTrue(tamper_check["tampered"])
        self.assertIn("INTEGRITY BREACH", tamper_check["message"])

        # Confirm audit log entry recorded
        log_entry = self.db.query(AuditLog).filter(
            AuditLog.entity_id == ev.evidence_id,
            AuditLog.action == "CHECKSUM_MISMATCH"
        ).first()
        self.assertIsNotNone(log_entry)

        # Restore original content
        ev.content = orig_content
        ev.status = "flagged"
        self.db.commit()

    def test_06_pdf_report_generation(self):
        """Test Section 3.12.4 Automated Report Generation Algorithm (IT-03)."""
        ev = self._fixture_evidence()
        pdf_path = generate_evidence_report(ev, "Test Complainant", "test@victim.org")
        self.assertTrue(os.path.exists(pdf_path))
        self.assertGreater(os.path.getsize(pdf_path), 500) # Valid PDF bytes

if __name__ == "__main__":
    unittest.main()
