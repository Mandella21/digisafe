from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from models.base import Base

class Report(Base):
    __tablename__ = 'reports'

    report_id = Column(Integer, primary_key=True, index=True)
    evidence_id = Column(Integer, ForeignKey('evidence.evidence_id'), nullable=False)
    victim_id = Column(Integer, ForeignKey('users.user_id'), nullable=False)
    file_path = Column(String(500), nullable=False)
    generated_at = Column(DateTime, default=datetime.utcnow)

    evidence = relationship('Evidence', back_populates='reports')
    victim = relationship('User', back_populates='reports')
