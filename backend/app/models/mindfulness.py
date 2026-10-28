import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Boolean, Uuid
from sqlalchemy.orm import relationship
from app.database import Base


class MeditationSession(Base):
    __tablename__ = "meditation_sessions"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid, ForeignKey("users.id"))
    session_type = Column(String(50), default="meditation")  # meditation, minigame
    duration_seconds = Column(Integer, nullable=True)
    completed = Column(Boolean, default=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    # Relationships
    user = relationship("User", back_populates="meditation_sessions")