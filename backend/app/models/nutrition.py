import uuid
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Text, Integer, Uuid
from sqlalchemy.orm import relationship
from app.database import Base


class FoodLog(Base):
    __tablename__ = "food_logs"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid, ForeignKey("users.id"))
    image_url = Column(String(500), nullable=True)
    detected_food = Column(String(200), nullable=True)
    calories = Column(Float, nullable=True)
    protein = Column(Float, nullable=True)  # in grams
    carbs = Column(Float, nullable=True)  # in grams
    fat = Column(Float, nullable=True)  # in grams
    notes = Column(Text, nullable=True)
    logged_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="food_logs")