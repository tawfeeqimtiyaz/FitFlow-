from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime, date
from uuid import UUID
from enum import Enum


# ==================== ENUMS ====================

class GoalType(str, Enum):
    WEIGHT_LOSS  = "weight_loss"
    MUSCLE_GAIN  = "muscle_gain"
    MAINTENANCE  = "maintenance"
    KETO         = "keto"
    HIGH_PROTEIN = "high_protein"


class ActivityLevel(str, Enum):
    SEDENTARY   = "sedentary"
    LIGHT       = "light"
    MODERATE    = "moderate"
    ACTIVE      = "active"
    VERY_ACTIVE = "very_active"


class MealType(str, Enum):
    BREAKFAST = "breakfast"
    LUNCH     = "lunch"
    DINNER    = "dinner"
    SNACK     = "snack"


# ==================== GOAL SCHEMAS ====================

class GoalCreate(BaseModel):
    goal_type:      GoalType      = GoalType.MAINTENANCE
    target_weight:  Optional[float] = None
    activity_level: ActivityLevel = ActivityLevel.MODERATE


class GoalUpdate(BaseModel):
    goal_type:      Optional[GoalType]      = None
    target_weight:  Optional[float]         = None
    activity_level: Optional[ActivityLevel] = None
    daily_calories: Optional[int]           = None
    daily_protein:  Optional[int]           = None
    daily_carbs:    Optional[int]           = None
    daily_fat:      Optional[int]           = None
    daily_water:    Optional[float]         = None


class GoalResponse(BaseModel):
    id:             UUID
    user_id:        int
    goal_type:      str
    target_weight:  Optional[float] = None
    activity_level: str
    daily_calories: Optional[int]   = None
    daily_protein:  Optional[int]   = None
    daily_carbs:    Optional[int]   = None
    daily_fat:      Optional[int]   = None
    daily_water:    float           = 2.5
    created_at:     datetime

    class Config:
        from_attributes = True


# ==================== FOOD DETECTION SCHEMAS ====================

class FoodDetectionRequest(BaseModel):
    image_base64: str = Field(..., description="Base64 encoded image")


class DetectedFood(BaseModel):
    name:       str
    confidence: float


class FoodDetectionResponse(BaseModel):
    detected_foods: List[DetectedFood]
    top_food:       str
    confidence:     float


# ==================== NUTRITION SCHEMAS ====================

class NutritionRequest(BaseModel):
    food_name:    str
    serving_size: Optional[str] = None


class NutritionData(BaseModel):
    food_name:    str
    serving_size: str
    serving_qty:  float
    calories:     float
    protein:      float
    carbs:        float
    fat:          float
    fiber:        float
    sugar:        float
    sodium:       float
    image_url:    Optional[str] = None


class NutritionResponse(BaseModel):
    foods:          List[NutritionData]
    total_calories: float
    total_protein:  float
    total_carbs:    float
    total_fat:      float


# ==================== MEAL LOG SCHEMAS ====================

class MealLogCreate(BaseModel):
    meal_type:    MealType      = MealType.SNACK
    food_name:    str
    serving_size: Optional[str]   = None
    quantity:     float           = 1.0
    calories:     float           = 0
    protein:      float           = 0
    carbs:        float           = 0
    fat:          float           = 0
    fiber:        float           = 0
    sugar:        float           = 0
    sodium:       float           = 0
    image_url:    Optional[str]   = None
    ai_detected:  Optional[str]   = None
    confidence:   Optional[float] = None
    notes:        Optional[str]   = None
    meal_date:    Optional[date]  = None


class MealLogResponse(BaseModel):
    id:           UUID
    user_id:      int
    meal_type:    str
    food_name:    str
    serving_size: Optional[str]   = None    # ✅ Added defaults
    quantity:     float
    calories:     float
    protein:      float
    carbs:        float
    fat:          float
    fiber:        float
    image_url:    Optional[str]   = None    # ✅ Added defaults
    ai_detected:  Optional[str]   = None    # ✅ Added defaults
    confidence:   Optional[float] = None    # ✅ Added defaults
    logged_at:    datetime
    meal_date:    date
    notes:        Optional[str]   = None    # ✅ Added defaults

    class Config:
        from_attributes = True


# ==================== DAILY INTAKE SCHEMAS ====================

class DailyIntakeResponse(BaseModel):
    id:             Optional[UUID] = None   # ✅ FIXED: None when no DB row exists
    user_id:        Optional[int] = None    # ✅ FIXED: None for empty days
    intake_date:    date
    total_calories: float = 0
    total_protein:  float = 0
    total_carbs:    float = 0
    total_fat:      float = 0
    total_fiber:    float = 0
    water_intake:   float = 0
    meals_count:    int   = 0

    class Config:
        from_attributes = True


class DailyProgressResponse(BaseModel):
    date:                date
    goals:               Optional[GoalResponse] = None
    intake:              Any                    #  dict or DailyIntake ORM
    calories_remaining:  float
    protein_remaining:   float
    carbs_remaining:     float
    fat_remaining:       float
    water_remaining:     float
    progress_percentage: float


# ==================== WATER LOG SCHEMAS ====================

class WaterLogCreate(BaseModel):
    amount: float = Field(..., description="Amount in ml")


class WaterLogResponse(BaseModel):
    id:        UUID
    user_id:   int
    amount:    float
    logged_at: datetime
    log_date:  date

    class Config:
        from_attributes = True


# ==================== EXERCISE / BALANCE SCHEMAS ====================

class ExerciseRecommendation(BaseModel):
    exercise_name:     str
    duration_minutes:  int
    calories_burn:     float
    intensity:         str
    description:       str


class CalorieBalanceResponse(BaseModel):
    consumed_calories:      float
    target_calories:        Optional[float] = None   # ✅ Can be None if no goal set
    excess_calories:        float
    recommended_exercises:  List[ExerciseRecommendation]
    message:                str