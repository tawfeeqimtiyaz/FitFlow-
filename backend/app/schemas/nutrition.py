from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from uuid import UUID


class FoodLogCreate(BaseModel):
    image_url: Optional[str] = None
    detected_food: Optional[str] = None
    calories: Optional[float] = None
    protein: Optional[float] = None
    carbs: Optional[float] = None
    fat: Optional[float] = None
    notes: Optional[str] = None


class FoodLogResponse(BaseModel):
    id: UUID
    user_id: UUID
    image_url: Optional[str]
    detected_food: Optional[str]
    calories: Optional[float]
    protein: Optional[float]
    carbs: Optional[float]
    fat: Optional[float]
    notes: Optional[str]
    logged_at: datetime

    class Config:
        from_attributes = True


class CalorieDetectionResponse(BaseModel):
    detected_food: str
    calories: float
    protein: float
    carbs: float
    fat: float
    confidence: float


class WorkoutRecommendation(BaseModel):
    exercise_name: str
    duration_minutes: int
    calories_to_burn: float
    reason: str