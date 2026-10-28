import uuid

from sqlalchemy import Boolean, Column, Integer, String, DateTime, Float, ForeignKey, Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import false, func
from ..database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    # False until the emailed one-time code is confirmed (see EmailVerification)
    is_verified = Column(Boolean, nullable=False, default=False, server_default=false())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    profile = relationship("UserProfile", back_populates="user", uselist=False)
    email_verification = relationship(
        "EmailVerification", back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
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

    id = Column(Uuid, primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(Uuid, ForeignKey("users.id"), nullable=False, unique=True)

    # Personal Info
    age = Column(Integer, nullable=True)
    gender = Column(String, nullable=True)
    height = Column(Float, nullable=True)       # in cm
    weight = Column(Float, nullable=True)       # in kg

    # Fitness Info
    fitness_goal = Column(String, nullable=True)
    fitness_level = Column(String, nullable=True, default="beginner")  # beginner, intermediate, advanced
    activity_level = Column(String, nullable=True)

    # Avatar (exposed by the API as `profile_picture`)
    profile_image = Column(String, nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationship back to User
    user = relationship("User", back_populates="profile")