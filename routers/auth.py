from datetime import datetime, timedelta
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from core.config import settings
from core.database import get_db
from core.security import hash_password, verify_password, create_access_token, get_current_user
from models.user import User
from models.audit_log import AuditLog
from schemas.auth import (
    RegisterRequest,
    LoginRequest,
    TokenResponse,
    UserOut,
    RegisterResponse,
    VerifyCodeRequest,
    VerifyTokenRequest,
    ResendVerificationRequest,
)
from services import email_service

router = APIRouter()


def _issue_verification(user: User, db: Session, request: Request = None) -> dict:
    """Mint a fresh code/token pair for a user and email it.

    Always replaces whatever was pending. Leaving an old code alive alongside a
    new one would mean every resend widened the set of values an attacker could
    guess, so the previous pair is overwritten rather than added to.
    """
    code = email_service.generate_verification_code()
    token = email_service.generate_verification_token()
    now = datetime.utcnow()

    user.verification_code = code
    user.verification_token = token
    user.verification_sent_at = now
    user.verification_expires_at = now + timedelta(minutes=settings.VERIFICATION_CODE_TTL_MINUTES)
    user.verification_attempts = 0
    db.commit()

    # The link is built from the address this very request arrived on, unless a
    # deployment has pinned one. That is what makes the emailed button work on a
    # phone, over a Cloudflare tunnel, or on a LAN address, without anyone
    # having to reconfigure anything between them.
    return email_service.send_verification_email(
        to_email=user.email,
        full_name=user.full_name,
        code=code,
        token=token,
        base_url=str(request.base_url) if request is not None else "",
    )


def _mark_verified(user: User, db: Session, method: str) -> TokenResponse:
    """Complete verification and sign the person in."""
    user.is_verified = True
    user.verified_at = datetime.utcnow()
    # The code and token are single-use. Clearing them means a forwarded email,
    # or a link sitting in browser history, cannot re-verify or be replayed.
    user.verification_code = None
    user.verification_token = None
    user.verification_expires_at = None
    user.verification_attempts = 0

    db.add(AuditLog(
        user_id=user.user_id,
        action="EMAIL_VERIFIED",
        entity_type="User",
        entity_id=user.user_id,
        details=f"Email address confirmed for {user.email} (via {method}).",
    ))
    db.commit()
    db.refresh(user)

    token = create_access_token(data={"sub": str(user.user_id), "role": user.role})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        role=user.role,
        user_id=user.user_id,
        full_name=user.full_name,
        email=user.email,
        is_verified=True,
    )


@router.post("/register", response_model=RegisterResponse)
def register(payload: RegisterRequest, request: Request, db: Session = Depends(get_db)):
    email_clean = payload.email.strip().lower()

    # Server-side validation. The browser checks these too, but a form can be
    # bypassed entirely - anyone can POST straight to this endpoint - so the
    # rules have to live here to actually mean anything.
    if not payload.full_name or not payload.full_name.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please enter your full name.",
        )
    if "@" not in email_clean or "." not in email_clean.split("@")[-1]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please enter a valid email address.",
        )
    if len(payload.password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Your password must be at least 8 characters long.",
        )
    if payload.confirm_password is not None and payload.password != payload.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Those two passwords are different. Please retype them.",
        )

    existing_user = db.query(User).filter(User.email == email_clean).first()
    if existing_user:
        # An address that registered but never confirmed is not a taken
        # address - it is an abandoned attempt, or a typo someone is retrying.
        # Refusing it outright would let anyone lock a victim out of the
        # platform for good simply by registering their address first and never
        # opening the email. So the pending account is reissued to whoever can
        # read that inbox, with a fresh password. An account that IS verified is
        # never touched by this path.
        if not existing_user.is_verified and settings.REQUIRE_EMAIL_VERIFICATION:
            existing_user.full_name = payload.full_name.strip()
            existing_user.password_hash = hash_password(payload.password)
            db.commit()
            delivery = _issue_verification(existing_user, db, request)
            return RegisterResponse(
                message=_delivery_message(delivery, existing_user.email),
                email=existing_user.email,
                full_name=existing_user.full_name,
                delivery=delivery["delivery"],
                email_sent=delivery["delivered"],
                expires_in_minutes=settings.VERIFICATION_CODE_TTL_MINUTES,
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists.",
        )

    # SECURITY: public self-registration ALWAYS creates a victim account.
    #
    # The role in the request body is deliberately ignored. Honouring it would
    # let any member of the public register with {"role": "admin"} and
    # immediately read every victim's evidence, which is a total compromise of
    # the confidentiality guarantee in Section 3.10 and of the role-based access
    # restriction required by Section 3.8.2.
    #
    # Privileged accounts (administrator, law enforcement officer) are created
    # by an existing administrator through POST /api/admin/users, which matches
    # Section 3.6: the System Administrator is the stakeholder "responsible for
    # managing user accounts".
    new_user = User(
        full_name=payload.full_name.strip(),
        email=email_clean,
        password_hash=hash_password(payload.password),
        role="victim",
        is_verified=not settings.REQUIRE_EMAIL_VERIFICATION,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    db.add(AuditLog(
        user_id=new_user.user_id,
        action="USER_REGISTER",
        entity_type="User",
        entity_id=new_user.user_id,
        details=(
            f"New user registered: {new_user.email} (Role: {new_user.role})"
            + (
                f" | NOTE: request asked for role '{payload.role}' and was "
                f"downgraded to victim by policy."
                if payload.role and payload.role.strip().lower() not in ("", "victim")
                else ""
            )
        )
    ))
    db.commit()

    if not settings.REQUIRE_EMAIL_VERIFICATION:
        # Verification switched off for an offline walkthrough: the account is
        # usable immediately and the response says so plainly.
        return RegisterResponse(
            status="verified",
            message="Account created. Email verification is switched off on this deployment, so you can sign in now.",
            email=new_user.email,
            full_name=new_user.full_name,
            verification_required=False,
            delivery="disabled",
            email_sent=False,
            expires_in_minutes=0,
        )

    delivery = _issue_verification(new_user, db, request)
    return RegisterResponse(
        message=_delivery_message(delivery, new_user.email),
        email=new_user.email,
        full_name=new_user.full_name,
        delivery=delivery["delivery"],
        email_sent=delivery["delivered"],
        expires_in_minutes=settings.VERIFICATION_CODE_TTL_MINUTES,
    )


def _delivery_message(delivery: dict, email: str) -> str:
    if delivery["delivery"] == "smtp":
        return f"We sent a 6-digit verification code to {email}. Enter it below to activate your account."
    if delivery["delivery"] == "outbox":
        return (
            "Your account was created, but this deployment has no mail server configured, "
            "so nothing was emailed. The verification code was printed in the server console."
        )
    return (
        "Your account was created, but the verification email could not be sent. "
        "The code was printed in the server console - or press Resend to try again."
    )


@router.post("/verify", response_model=TokenResponse)
def verify_email(payload: VerifyCodeRequest, db: Session = Depends(get_db)):
    """Confirm ownership of an address with the typed 6-digit code."""
    email_clean = payload.email.strip().lower()
    code_clean = "".join(ch for ch in (payload.code or "") if ch.isdigit())

    user = db.query(User).filter(User.email == email_clean).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="We have no pending registration for that email address.",
        )
    if user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account is already verified. You can sign in.",
        )
    if not user.verification_code or not user.verification_expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No verification code is outstanding. Press Resend to get a new one.",
        )
    if datetime.utcnow() > user.verification_expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That code has expired. Press Resend to get a new one.",
        )

    if (user.verification_attempts or 0) >= settings.VERIFICATION_MAX_ATTEMPTS:
        # Six digits is a million possibilities; without a cap, an attacker
        # could simply work through them. Burning the code forces a resend,
        # which resets the target they are aiming at.
        user.verification_code = None
        user.verification_token = None
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many incorrect codes. That code has been cancelled - press Resend to get a new one.",
        )

    # Constant-time comparison: a plain != leaks, through its timing, how many
    # leading digits were right, which turns a million guesses into about sixty.
    if not secrets.compare_digest(code_clean, user.verification_code):
        user.verification_attempts = (user.verification_attempts or 0) + 1
        db.commit()
        remaining = max(0, settings.VERIFICATION_MAX_ATTEMPTS - user.verification_attempts)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"That code is not correct. {remaining} attempt(s) left before it is cancelled.",
        )

    return _mark_verified(user, db, method="code")


@router.post("/verify-token", response_model=TokenResponse)
def verify_email_by_token(payload: VerifyTokenRequest, db: Session = Depends(get_db)):
    """Confirm ownership from the link in the email, no typing required."""
    token_clean = (payload.token or "").strip()
    if not token_clean:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That verification link is incomplete.",
        )

    user = db.query(User).filter(User.verification_token == token_clean).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This verification link is no longer valid. It may already have been used.",
        )
    if user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account is already verified. You can sign in.",
        )
    if not user.verification_expires_at or datetime.utcnow() > user.verification_expires_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="That link has expired. Press Resend to get a new one.",
        )

    return _mark_verified(user, db, method="email link")


@router.post("/resend-verification", response_model=RegisterResponse)
def resend_verification(payload: ResendVerificationRequest, request: Request, db: Session = Depends(get_db)):
    email_clean = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email_clean).first()

    generic = RegisterResponse(
        message=f"If {email_clean} has an account awaiting verification, a new code is on its way.",
        email=email_clean,
        full_name="",
        delivery="smtp",
        email_sent=True,
        expires_in_minutes=settings.VERIFICATION_CODE_TTL_MINUTES,
    )

    # An unknown or already-verified address gets the same answer as a real
    # pending one. Anything else turns this endpoint into a way to ask the
    # platform "does this person have an account here?" - which, for a service
    # used by abuse victims, is precisely the question an abuser wants answered.
    if not user or user.is_verified:
        return generic

    if user.verification_sent_at:
        elapsed = (datetime.utcnow() - user.verification_sent_at).total_seconds()
        wait = settings.VERIFICATION_RESEND_COOLDOWN_SECONDS - elapsed
        if wait > 0:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"A code was just sent. Please wait {int(wait) + 1} seconds before asking for another.",
            )

    delivery = _issue_verification(user, db, request)
    return RegisterResponse(
        message=_delivery_message(delivery, user.email),
        email=user.email,
        full_name=user.full_name,
        delivery=delivery["delivery"],
        email_sent=delivery["delivered"],
        expires_in_minutes=settings.VERIFICATION_CODE_TTL_MINUTES,
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    email_clean = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email_clean).first()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    # The password check comes first on purpose. Reversing the order would let
    # anyone learn which addresses are registered but unconfirmed without
    # knowing a password.
    if settings.REQUIRE_EMAIL_VERIFICATION and not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Please verify your email address before signing in. We can send you a new code.",
            # The browser branches on this header to open the verification
            # screen with the address filled in, instead of showing a dead end.
            headers={"X-DigiSafe-Reason": "email-unverified"},
        )

    db.add(AuditLog(
        user_id=user.user_id,
        action="USER_LOGIN",
        entity_type="User",
        entity_id=user.user_id,
        details=f"User logged in: {user.email}"
    ))
    db.commit()

    token = create_access_token(data={"sub": str(user.user_id), "role": user.role})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        role=user.role,
        user_id=user.user_id,
        full_name=user.full_name,
        email=user.email,
        is_verified=bool(user.is_verified),
    )


@router.get("/me", response_model=UserOut)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    return current_user
