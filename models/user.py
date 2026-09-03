from sqlalchemy import Column, Integer, String, DateTime
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

    evidence_records = relationship('Evidence', back_populates='owner', cascade='all, delete-orphan')
    reports = relationship('Report', back_populates='victim')
    audit_logs = relationship('AuditLog', back_populates='user')
