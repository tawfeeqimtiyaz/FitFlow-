import uuid

from sqlalchemy import Boolean, Column, Integer, String, DateTime, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    profile = relationship("UserProfile", back_populates="user", uselist=False)
    workout_sessions = relationship("WorkoutSession", back_populates="user")
    food_logs = relationship("FoodLog", back_populates="user")
    meal_logs = relationship("MealLog", back_populates="user")
    daily_intakes = relationship("DailyIntake", back_populates="user")
    water_logs = relationship("WaterLog", back_populates="user")
    meditation_sessions = relationship("MeditationSession", back_populates="user")
    user_goals = relationship("UserGoal", back_populates="user")

    # Medical Relationships
    symptoms = relationship("Symptom", back_populates="user")
    doctor_visits = relationship("DoctorVisit", back_populates="user")
    medications = relationship("Medication", back_populates="user")
    medication_reminders = relationship("MedicationReminder", back_populates="user")


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True)

    # Personal Info
    age = Column(Integer, nullable=True)
    gender = Column(String, nullable=True)
    height = Column(Float, nullable=True)       # in cm
    weight = Column(Float, nullable=True)       # in kg

    # Fitness Info
    fitness_goal = Column(String, nullable=True)
    activity_level = Column(String, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship back to User
    user = relationship("User", back_populates="profile")