import unittest
import os
from core.database import SessionLocal, engine
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
    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

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
        """Test Section 3.12.3 ML Harassment Detection."""
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
        self.assertLess(res_benign["confidence_score"], 0.30)

    def test_05_checksum_data_recovery_and_tamper_detection(self):
        """Test Section 4.1.8 Checksum Data Recovery Technique (IT-02)."""
        ev = self.db.query(Evidence).first()
        self.assertIsNotNone(ev, "Evidence record must exist for test")

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
        ev = self.db.query(Evidence).first()
        pdf_path = generate_evidence_report(ev, "Test Complainant", "test@victim.org")
        self.assertTrue(os.path.exists(pdf_path))
        self.assertGreater(os.path.getsize(pdf_path), 500) # Valid PDF bytes

if __name__ == "__main__":
    unittest.main()
