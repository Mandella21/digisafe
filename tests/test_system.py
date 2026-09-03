import unittest
import os
import pathlib

# Point the application at a SEPARATE database before anything imports
# core.database, which builds its engine from this value at import time.
#
# Without this the suite ran against digisafe.db - the same file the live
# application uses - so every test run wrote fabricated users and evidence into
# real data. In a system that holds abuse victims' evidence, a test run must
# never be able to touch the production database.
_TEST_DB = pathlib.Path(__file__).resolve().parent / "test_digisafe.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"
# Fixtures rely on the demonstration accounts, so enable seeding for the suite.
os.environ["DIGISAFE_SEED_DEMO"] = "true"

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
        # Start from a clean slate so results never depend on a previous run.
        if _TEST_DB.exists():
            _TEST_DB.unlink()
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
                    email = f"probe-{attempted_role.lower()}-{os.urandom(4).hex()}@example.com"
                    response = client.post("/api/auth/register", json={
                        "full_name": "Privilege Escalation Probe",
                        "email": email,
                        "password": "Probe@12345",
                        "role": attempted_role,
                    })
                    self.assertEqual(response.status_code, 200)

                    # Sign-up itself must not hand out a session - the account is
                    # inert until the emailed code is entered.
                    self.assertNotIn(
                        "access_token", response.json(),
                        "Registration issued a session before the email was verified",
                    )

                    token = self._verify_and_get_token(client, email)
                    self.assertEqual(
                        token["role"], "victim",
                        f"Registration granted '{attempted_role}' to a public sign-up",
                    )

                    # And the token it eventually issues must be refused by
                    # admin endpoints.
                    denied = client.get(
                        "/api/admin/stats",
                        headers={"Authorization": f"Bearer {token['access_token']}"},
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

    def _pending_code(self, email):
        """Read the outstanding code straight from the database.

        The suite cannot open a mailbox, so it reads what was stored rather than
        what was delivered. That is the right seam: delivery is smtplib's
        responsibility, while the rule under test - that an account stays inert
        until the correct code is presented - lives in this codebase.
        """
        db = SessionLocal()
        try:
            user = db.query(User).filter(User.email == email.strip().lower()).first()
            return user.verification_code if user else None
        finally:
            db.close()

    def _verify_and_get_token(self, client, email):
        code = self._pending_code(email)
        self.assertIsNotNone(code, f"No verification code was issued for {email}")
        response = client.post("/api/auth/verify", json={"email": email, "code": code})
        self.assertEqual(
            response.status_code, 200,
            f"Verification failed for {email}: {response.text}",
        )
        return response.json()

    def test_04h_account_is_inert_until_the_emailed_code_is_entered(self):
        """Sign-up must not be enough on its own (Section 3.8.2, authentication).

        Registering with an address you cannot read must not get you in. If it
        did, anyone could register as a victim they were targeting and be handed
        that victim's evidence tracking.
        """
        from fastapi.testclient import TestClient
        from main import app

        email = f"verify-{os.urandom(4).hex()}@example.com"
        password = "Verify@12345"

        with TestClient(app) as client:
            registered = client.post("/api/auth/register", json={
                "full_name": "Akosua Verification",
                "email": email,
                "password": password,
                "confirm_password": password,
            })
            self.assertEqual(registered.status_code, 200)
            self.assertTrue(registered.json()["verification_required"])

            # The account exists, and the password is right - and it still
            # cannot sign in.
            blocked = client.post("/api/auth/login", json={
                "email": email, "password": password,
            })
            self.assertEqual(
                blocked.status_code, 403,
                "An unverified account was allowed to sign in",
            )
            self.assertEqual(blocked.headers.get("X-DigiSafe-Reason"), "email-unverified")

            # A wrong code changes nothing.
            wrong = client.post("/api/auth/verify", json={
                "email": email, "code": "000000" if self._pending_code(email) != "000000" else "111111",
            })
            self.assertEqual(wrong.status_code, 400)
            self.assertEqual(
                client.post("/api/auth/login", json={"email": email, "password": password}).status_code,
                403,
                "A failed verification attempt still unlocked the account",
            )

            # The correct code does, and signs the person in as a victim.
            token = self._verify_and_get_token(client, email)
            self.assertTrue(token["is_verified"])
            self.assertEqual(token["role"], "victim")

            # And now the ordinary login works.
            allowed = client.post("/api/auth/login", json={
                "email": email, "password": password,
            })
            self.assertEqual(allowed.status_code, 200)

    def test_04i_verification_code_is_single_use(self):
        """A code that has been spent must not work twice.

        An emailed code can be forwarded, screenshotted, or sit in a synced
        mailbox for years. Once it has done its job it has to stop being a key.
        """
        from fastapi.testclient import TestClient
        from main import app

        email = f"replay-{os.urandom(4).hex()}@example.com"
        with TestClient(app) as client:
            client.post("/api/auth/register", json={
                "full_name": "Replay Probe", "email": email, "password": "Replay@12345",
            })
            code = self._pending_code(email)
            self.assertEqual(
                client.post("/api/auth/verify", json={"email": email, "code": code}).status_code,
                200,
            )
            replayed = client.post("/api/auth/verify", json={"email": email, "code": code})
            self.assertNotEqual(
                replayed.status_code, 200,
                "A verification code was accepted a second time",
            )

    def test_04j_verification_link_token_also_works(self):
        """Tapping the button in the email must complete verification too.

        Typing a code on a phone is the fallback, not the main path.
        """
        from fastapi.testclient import TestClient
        from main import app

        email = f"link-{os.urandom(4).hex()}@example.com"
        with TestClient(app) as client:
            client.post("/api/auth/register", json={
                "full_name": "Link Probe", "email": email, "password": "Linked@12345",
            })

            db = SessionLocal()
            try:
                token_value = db.query(User).filter(User.email == email).first().verification_token
            finally:
                db.close()
            self.assertTrue(token_value, "No verification token was issued")

            verified = client.post("/api/auth/verify-token", json={"token": token_value})
            self.assertEqual(verified.status_code, 200, verified.text)
            self.assertTrue(verified.json()["is_verified"])

            # And the link, like the code, is spent.
            self.assertNotEqual(
                client.post("/api/auth/verify-token", json={"token": token_value}).status_code,
                200,
                "A verification link was accepted a second time",
            )

    def test_04k_resend_does_not_reveal_who_has_an_account(self):
        """Asking for a code must not answer 'is this person registered here?'

        For a platform used by abuse victims, that question is exactly what an
        abuser wants answered, so an unknown address gets the same reply as a
        real one.
        """
        from fastapi.testclient import TestClient
        from main import app

        with TestClient(app) as client:
            stranger = client.post("/api/auth/resend-verification", json={
                "email": f"nobody-{os.urandom(4).hex()}@example.com",
            })
            self.assertEqual(
                stranger.status_code, 200,
                "An unknown address got a different answer from a registered one",
            )

    def test_04l_verification_email_carries_the_code_and_the_link(self):
        """The message itself has to contain what the person needs.

        Rendering is checked directly rather than through delivery: with no SMTP
        server configured the platform writes the message to storage/outbox
        instead of sending it, and the content is the part this codebase owns.
        """
        from services.email_service import (
            generate_verification_code,
            generate_verification_token,
            send_verification_email,
            verification_link,
        )

        code = generate_verification_code()
        token = generate_verification_token()

        self.assertEqual(len(code), 6, "Verification code should be six digits")
        self.assertTrue(code.isdigit())
        self.assertNotEqual(
            code, generate_verification_code(),
            "Two consecutive codes were identical - the generator is not random",
        )

        result = send_verification_email(
            to_email="outbox-probe@example.com",
            full_name="Outbox Probe",
            code=code,
            token=token,
        )
        # No SMTP server in the test environment, so this must report honestly
        # rather than claiming a delivery that did not happen.
        self.assertFalse(result["delivered"])
        self.assertEqual(result["delivery"], "outbox")

        written = pathlib.Path(result["detail"]).read_text(encoding="utf-8", errors="replace")
        self.assertIn(code, written, "The verification code is missing from the email")
        self.assertIn(token, written, "The verification link is missing from the email")
        self.assertIn(verification_link(token).split("?")[0], written)

    def test_04m_a_code_only_verifies_the_account_it_was_issued_to(self):
        """Codes must be bound to one account, not merely be valid codes.

        Two people register within seconds of each other. If either one's code
        could activate the other's account, the whole mechanism would prove
        nothing about who controls which inbox.
        """
        from fastapi.testclient import TestClient
        from main import app

        alice = f"alice-{os.urandom(4).hex()}@example.com"
        bob = f"bob-{os.urandom(4).hex()}@example.com"

        with TestClient(app) as client:
            for address in (alice, bob):
                client.post("/api/auth/register", json={
                    "full_name": "Binding Probe",
                    "email": address,
                    "password": "Binding@12345",
                })

            alice_code = self._pending_code(alice)
            bob_code = self._pending_code(bob)
            self.assertNotEqual(alice_code, bob_code)

            crossed = client.post("/api/auth/verify", json={
                "email": alice, "code": bob_code,
            })
            self.assertEqual(
                crossed.status_code, 400,
                "One account's verification code activated a different account",
            )

            # And the emailed link is bound the same way: it verifies the
            # account it was issued for, never whoever happens to open it.
            db = SessionLocal()
            try:
                bob_token = db.query(User).filter(User.email == bob).first().verification_token
            finally:
                db.close()

            followed = client.post("/api/auth/verify-token", json={"token": bob_token})
            self.assertEqual(followed.status_code, 200)
            self.assertEqual(
                followed.json()["email"], bob,
                "A verification link signed in the wrong account",
            )

            still_locked = client.post("/api/auth/login", json={
                "email": alice, "password": "Binding@12345",
            })
            self.assertEqual(
                still_locked.status_code, 403,
                "Alice was let in after Bob verified his own account",
            )

    def test_04n_configured_smtp_is_actually_used(self):
        """With a mail server configured, the message must go to it.

        The unconfigured path (console + storage/outbox) is well covered above,
        which is exactly the risk: it would be easy for the real branch to be
        broken and every test still pass. This one drives the code that runs in
        production, stubbing only the socket conversation itself.
        """
        from unittest import mock
        from core.config import settings
        from services import email_service

        sent = {}

        def fake_transport(message):
            sent["to"] = message["To"]
            sent["from"] = message["From"]
            sent["subject"] = message["Subject"]
            sent["body"] = message.get_body(
                preferencelist=("plain",)
            ).get_content()

        code = email_service.generate_verification_code()
        token = email_service.generate_verification_token()

        with mock.patch.object(settings, "SMTP_HOST", "smtp.example.org"), \
             mock.patch.object(settings, "MAIL_FROM", "digisafe@example.org"), \
             mock.patch.object(settings, "MAIL_FROM_NAME", "DigiSafe"), \
             mock.patch.object(email_service, "_send_via_smtp", fake_transport):

            self.assertTrue(
                email_service.is_smtp_configured(),
                "Setting SMTP_HOST and MAIL_FROM should count as configured",
            )
            result = email_service.send_verification_email(
                to_email="recipient@yahoo.com",
                full_name="Kofi Owusu",
                code=code,
                token=token,
            )

        self.assertTrue(result["delivered"], "A successful send reported failure")
        self.assertEqual(result["delivery"], "smtp")
        self.assertEqual(sent["to"], "recipient@yahoo.com")
        self.assertIn("digisafe@example.org", sent["from"])
        self.assertIn(code, sent["subject"])
        self.assertIn(code, sent["body"])
        self.assertIn(token, sent["body"])

    def test_04o_a_failed_send_still_leaves_the_account_recoverable(self):
        """When the mail server refuses, nothing may be silently lost.

        A registration that already succeeded must not be undone by a mail
        failure, and the code must remain reachable - otherwise a transient SMTP
        outage would strand every account created during it.
        """
        from unittest import mock
        from core.config import settings
        from services import email_service

        def explode(message):
            raise OSError("Connection unexpectedly closed")

        code = email_service.generate_verification_code()

        with mock.patch.object(settings, "SMTP_HOST", "smtp.example.org"), \
             mock.patch.object(settings, "MAIL_FROM", "digisafe@example.org"), \
             mock.patch.object(email_service, "_send_via_smtp", explode):
            result = email_service.send_verification_email(
                to_email="unlucky@example.com",
                full_name="Unlucky Person",
                code=code,
                token=email_service.generate_verification_token(),
            )

        # Reported honestly rather than raised, so the caller can tell the user
        # what happened instead of returning a 500 over a created account.
        self.assertFalse(result["delivered"])
        self.assertEqual(result["delivery"], "failed")
        self.assertIn("Connection unexpectedly closed", result["detail"])

        # And the message survives on disk, so the code is still recoverable.
        saved = sorted(pathlib.Path(settings.OUTBOX_DIR).glob("*unlucky*.eml"))
        self.assertTrue(saved, "A failed send left no copy of the message")
        self.assertIn(code, saved[-1].read_text(encoding="utf-8", errors="replace"))

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
