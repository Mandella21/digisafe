from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from models.base import Base

class Alert(Base):
    __tablename__ = 'alerts'

    alert_id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.user_id'), nullable=True)
    evidence_id = Column(Integer, ForeignKey('evidence.evidence_id'), nullable=True)
    message = Column(Text, nullable=False)
    severity = Column(String(20), default='Medium') # Low, Medium, High, Critical
    acknowledged = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    evidence = relationship('Evidence', back_populates='alerts')
