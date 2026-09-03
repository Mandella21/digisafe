from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from models.base import Base

class User(Base):
    __tablename__ = 'users'

    user_id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(30), default='victim', nullable=False) # victim, admin, officer
    created_at = Column(DateTime, default=datetime.utcnow)

    # --- Email ownership verification (Section 3.8.2, authentication) ---
    #
    # An account is inert until the person behind it proves they can read the
    # inbox they signed up with. Without that step anyone could register under
    # someone else's address, and in a system holding abuse evidence the
    # consequences are not hypothetical: an abuser could register as their
    # victim and be handed the victim's own case tracking.
    #
    # The code is what the person types; the token is what the emailed link
    # carries. Both refer to the same pending verification and either one
    # completes it, because a tunnelled or relocated deployment can serve the
    # link from a different host than the one that sent it.
    is_verified = Column(Boolean, default=False, nullable=False)
    verification_code = Column(String(10), nullable=True)
    verification_token = Column(String(64), index=True, nullable=True)
    verification_sent_at = Column(DateTime, nullable=True)
    verification_expires_at = Column(DateTime, nullable=True)
    verification_attempts = Column(Integer, default=0, nullable=True)
    verified_at = Column(DateTime, nullable=True)

    evidence_records = relationship('Evidence', back_populates='owner', cascade='all, delete-orphan')
    reports = relationship('Report', back_populates='victim')
    audit_logs = relationship('AuditLog', back_populates='user')
