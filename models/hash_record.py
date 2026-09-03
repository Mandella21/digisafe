from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from models.base import Base

class HashRecord(Base):
    __tablename__ = 'hash_records'

    hash_id = Column(Integer, primary_key=True, index=True)
    evidence_id = Column(Integer, ForeignKey('evidence.evidence_id'), unique=True, nullable=False)
    hash_value = Column(String(64), nullable=False) # SHA-256 64-char hex digest
    algorithm = Column(String(20), default='SHA-256', nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    evidence = relationship('Evidence', back_populates='hash_record')
