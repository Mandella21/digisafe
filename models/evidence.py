from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from models.base import Base

class Evidence(Base):
    __tablename__ = 'evidence'

    evidence_id = Column(Integer, primary_key=True, index=True)
    victim_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    content_type = Column(String(20), nullable=False) # text, url, file
    content = Column(Text, nullable=False)            # AES-256 encrypted ciphertext at rest
    source_url = Column(String(500), nullable=True)
    file_path = Column(String(500), nullable=True)
    file_hash = Column(String(64), nullable=True)     # SHA-256 for attachment if any
    submitted_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default='pending')    # pending, verified, flagged, compromised, reviewed

    owner = relationship('User', back_populates='evidence_records')
    hash_record = relationship('HashRecord', uselist=False, back_populates='evidence', cascade='all, delete-orphan')
    classification = relationship('MLClassification', uselist=False, back_populates='evidence', cascade='all, delete-orphan')
    reports = relationship('Report', back_populates='evidence', cascade='all, delete-orphan')
    alerts = relationship('Alert', back_populates='evidence', cascade='all, delete-orphan')
