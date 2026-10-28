from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID


class WorkoutSessionCreate(BaseModel):
    exercise_id: UUID


class WorkoutSessionEnd(BaseModel):
    duration_seconds: int
    completed: bool = True


class WorkoutSessionResponse(BaseModel):
    id: UUID
    user_id: UUID
    exercise_id: UUID
    started_at: datetime
    ended_at: Optional[datetime]
    duration_seconds: Optional[int]
    calories_burned: Optional[int]
    completed: bool

    class Config:
        from_attributes = True


class WorkoutHistoryResponse(BaseModel):
    id: UUID
    exercise_name: str
    category_name: str
    duration_seconds: Optional[int]
    calories_burned: Optional[int]
    completed: bool
    started_at: datetime

    class Config:
        from_attributes = True