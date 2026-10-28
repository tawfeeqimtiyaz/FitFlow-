import uuid
from datetime import datetime, date
from sqlalchemy import Column, String, Float, Integer, DateTime, Date, ForeignKey, Text, Uuid
from sqlalchemy.orm import relationship
from app.database import Base
import enum


# ==================== ENUMS ====================

class GoalType(str, enum.Enum):
    WEIGHT_LOSS  = "weight_loss"
    MUSCLE_GAIN  = "muscle_gain"
    MAINTENANCE  = "maintenance"
    KETO         = "keto"
    HIGH_PROTEIN = "high_protein"


class ActivityLevel(str, enum.Enum):
    SEDENTARY   = "sedentary"
    LIGHT       = "light"
    MODERATE    = "moderate"
    ACTIVE      = "active"
    VERY_ACTIVE = "very_active"


class MealType(str, enum.Enum):
    BREAKFAST = "breakfast"
    LUNCH     = "lunch"
    DINNER    = "dinner"
    SNACK     = "snack"


# ==================== MODELS ====================

class UserGoal(Base):
    __tablename__ = "user_goals"

    id      = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid, ForeignKey("users.id"), unique=True)

    # Goal Settings
    goal_type      = Column(String(50), default=GoalType.MAINTENANCE.value)
    target_weight  = Column(Float, nullable=True)
    activity_level = Column(String(50), default=ActivityLevel.MODERATE.value)

    # Calculated Targets
    daily_calories = Column(Integer, nullable=True)
    daily_protein  = Column(Integer, nullable=True)
    daily_carbs    = Column(Integer, nullable=True)
    daily_fat      = Column(Integer, nullable=True)
    daily_water    = Column(Float, default=2.5)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ✅ FIXED: matches user.py relationship name
    user = relationship("User", back_populates="user_goals")


class MealLog(Base):
    __tablename__ = "meal_logs"

    id      = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid, ForeignKey("users.id"))

    # Meal Info
    meal_type    = Column(String(50), default=MealType.SNACK.value)
    food_name    = Column(String(255), nullable=False)
    serving_size = Column(String(100), nullable=True)
    quantity     = Column(Float, default=1.0)

    # Nutrition
    calories = Column(Float, default=0)
    protein  = Column(Float, default=0)
    carbs    = Column(Float, default=0)
    fat      = Column(Float, default=0)
    fiber    = Column(Float, default=0)
    sugar    = Column(Float, default=0)
    sodium   = Column(Float, default=0)

    # Image & AI
    image_url   = Column(String(500), nullable=True)
    ai_detected = Column(String(255), nullable=True)
    confidence  = Column(Float, nullable=True)

    # Timestamps
    logged_at = Column(DateTime, default=datetime.utcnow)
    meal_date = Column(Date, default=date.today)
    notes     = Column(Text, nullable=True)

    # ✅ Correct
    user = relationship("User", back_populates="meal_logs")


class DailyIntake(Base):
    __tablename__ = "daily_intakes"

    id      = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid, ForeignKey("users.id"))

    intake_date = Column(Date, default=date.today, index=True)

    # Totals
    total_calories = Column(Float, default=0)
    total_protein  = Column(Float, default=0)
    total_carbs    = Column(Float, default=0)
    total_fat      = Column(Float, default=0)
    total_fiber    = Column(Float, default=0)
    water_intake   = Column(Float, default=0)
    meals_count    = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ✅ Correct
    user = relationship("User", back_populates="daily_intakes")


class WaterLog(Base):
    __tablename__ = "water_logs"

    id      = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid, ForeignKey("users.id"))

    amount    = Column(Float, nullable=False)  # in ml
    logged_at = Column(DateTime, default=datetime.utcnow)
    log_date  = Column(Date, default=date.today)

    # ✅ Correct
    user = relationship("User", back_populates="water_logs")