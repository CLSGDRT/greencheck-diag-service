import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Column, String, Float, DateTime, func
from sqlalchemy.orm import declarative_base
from .db import db

Base = db.Model

class DiagResult(Base):
    __tablename__ = "diag_results"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    image_id = Column(String, nullable=False)            # UUID de l'image stockée
    user_text = Column(String, nullable=True)           # Texte de l'utilisateur
    score = Column(Float, nullable=True)                # Note de santé de la plante (0-5)
    disease = Column(String, nullable=True)             # Maladie identifiée
    advice = Column(String, nullable=True)              # Conseils de traitement
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return (
            f"<DiagResult(id={self.id}, image_id={self.image_id}, score={self.score}, "
            f"disease={self.disease})>"
        )

