from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID


class MeditationSessionCreate(BaseModel):
    session_type: str = "meditation"  # meditation, minigame


class MeditationSessionEnd(BaseModel):
    duration_seconds: int
    completed: bool = True


class MeditationSessionResponse(BaseModel):
    id: UUID
    user_id: UUID
    session_type: str
    duration_seconds: Optional[int]
    completed: bool
    started_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class MindfulnessStats(BaseModel):
    total_sessions: int
    total_minutes: int
    meditation_sessions: int
    minigame_sessions: int
    current_streak: int