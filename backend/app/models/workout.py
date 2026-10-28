import uuid
from datetime import datetime
from sqlalchemy import Column, Integer, Boolean, DateTime, ForeignKey, Uuid
from sqlalchemy.orm import relationship
from app.database import Base


class WorkoutSession(Base):
    __tablename__ = "workout_sessions"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid, ForeignKey("users.id"))
    exercise_id = Column(Uuid, ForeignKey("exercises.id"))
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    calories_burned = Column(Integer, nullable=True)
    completed = Column(Boolean, default=False)

    # Relationships
    user = relationship("User", back_populates="workout_sessions")
    exercise = relationship("Exercise", back_populates="workout_sessions")