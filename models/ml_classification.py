from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from models.base import Base

class MLClassification(Base):
    __tablename__ = 'ml_classifications'

    result_id = Column(Integer, primary_key=True, index=True)
    evidence_id = Column(Integer, ForeignKey('evidence.evidence_id'), unique=True, nullable=False)
    label = Column(String(50), nullable=False)               # Abusive, Non-Abusive
    confidence_score = Column(Float, nullable=False)        # 0.0 - 1.0
    threat_level = Column(String(20), default='Low')        # None, Low, Medium, High, Critical
    model_version = Column(String(50), default='v2.0-tfidf-nb')
    # Comma-separated abuse categories predicted by the multiclass model, e.g.
    # "Physical Violence / Life Threat, Blackmail / Non-Consensual Extortion".
    detected_categories = Column(Text, nullable=True)
    classified_at = Column(DateTime, default=datetime.utcnow)

    evidence = relationship('Evidence', back_populates='classification')
