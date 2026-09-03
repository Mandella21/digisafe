from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, LargeBinary
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
    # Attachments are stored IN the database, not on the filesystem.
    #
    # Every free hosting tier this can realistically run on - Render, Cloud Run,
    # Hugging Face - gives the process an ephemeral disk that is wiped on every
    # restart, redeploy and idle spin-down. A path column would keep pointing at
    # a file that no longer exists, so an evidence record would survive while
    # the evidence itself quietly disappeared. For a system whose entire purpose
    # is preserving evidence, that is the one failure that must not happen.
    #
    # Attachments are capped at a few megabytes (see routers/evidence.py), so
    # the size is well within what a row can hold, and it means a database
    # backup is a complete backup.
    file_data = Column(LargeBinary, nullable=True)
    file_name = Column(String(255), nullable=True)
    file_mime = Column(String(120), nullable=True)
    # Retained so databases written before the change above still open, and so
    # a record captured then still names its original file.
    file_path = Column(String(500), nullable=True)
    file_hash = Column(String(64), nullable=True)     # SHA-256 for attachment if any
    submitted_at = Column(DateTime, default=datetime.utcnow)
    status = Column(String(20), default='pending')    # pending, verified, flagged, compromised, reviewed

    owner = relationship('User', back_populates='evidence_records')
    hash_record = relationship('HashRecord', uselist=False, back_populates='evidence', cascade='all, delete-orphan')
    classification = relationship('MLClassification', uselist=False, back_populates='evidence', cascade='all, delete-orphan')
    reports = relationship('Report', back_populates='evidence', cascade='all, delete-orphan')
    alerts = relationship('Alert', back_populates='evidence', cascade='all, delete-orphan')
