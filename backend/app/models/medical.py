from sqlalchemy import (
    Boolean, Column, Integer, String,
    DateTime, Float, Text, ForeignKey, Date, Time, Uuid
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class Symptom(Base):
    __tablename__ = "symptoms"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Uuid, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    severity = Column(Integer, nullable=True)  # 1-10 scale
    description = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # ✅ back_populates must match User.symptoms
    user = relationship("User", back_populates="symptoms")


class DoctorVisit(Base):
    __tablename__ = "doctor_visits"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Uuid, ForeignKey("users.id"), nullable=False)
    doctor_name = Column(String, nullable=False)
    specialty = Column(String, nullable=True)
    visit_date = Column(Date, nullable=False)
    reason = Column(Text, nullable=True)
    diagnosis = Column(Text, nullable=True)
    prescription = Column(Text, nullable=True)
    follow_up_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # ✅ back_populates must match User.doctor_visits
    user = relationship("User", back_populates="doctor_visits")


class Medication(Base):
    __tablename__ = "medications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Uuid, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    dosage = Column(String, nullable=True)
    frequency = Column(String, nullable=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    prescribed_by = Column(String, nullable=True)
    purpose = Column(Text, nullable=True)
    side_effects = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # ✅ back_populates must match User.medications
    user = relationship("User", back_populates="medications")
    reminders = relationship("MedicationReminder", back_populates="medication")


class MedicationReminder(Base):
    __tablename__ = "medication_reminders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Uuid, ForeignKey("users.id"), nullable=False)
    medication_id = Column(Integer, ForeignKey("medications.id"), nullable=False)
    reminder_time = Column(Time, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # ✅ back_populates must match User.medication_reminders
    user = relationship("User", back_populates="medication_reminders")
    medication = relationship("Medication", back_populates="reminders")