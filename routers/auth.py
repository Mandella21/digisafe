from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from core.database import get_db
from core.security import hash_password, verify_password, create_access_token, get_current_user
from models.user import User
from models.audit_log import AuditLog
from schemas.auth import RegisterRequest, LoginRequest, TokenResponse, UserOut

router = APIRouter()

@router.post("/register", response_model=TokenResponse)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    email_clean = payload.email.strip().lower()
    existing_user = db.query(User).filter(User.email == email_clean).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists."
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
        role="victim"
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

    token = create_access_token(data={"sub": str(new_user.user_id), "role": new_user.role})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        role=new_user.role,
        user_id=new_user.user_id,
        full_name=new_user.full_name,
        email=new_user.email
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
        email=user.email
    )

@router.get("/me", response_model=UserOut)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    return current_user
