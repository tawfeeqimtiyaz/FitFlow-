from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime, date, time
from uuid import UUID


# --- Symptom Schemas ---

class SymptomCreate(BaseModel):
    name: str
    severity: Optional[int] = None
    description: Optional[str] = None
    started_at: Optional[datetime] = None


class SymptomResponse(BaseModel):
    id: int
    user_id: UUID
    name: str
    severity: Optional[int]
    description: Optional[str]
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class DoctorSuggestion(BaseModel):
    doctor_type: str
    reason: str
    urgency: str


# --- Doctor Visit Schemas ---

class DoctorVisitCreate(BaseModel):
    doctor_name: str
    specialty: Optional[str] = None
    visit_date: date
    reason: Optional[str] = None
    diagnosis: Optional[str] = None
    prescription: Optional[str] = None
    follow_up_date: Optional[date] = None
    notes: Optional[str] = None


class DoctorVisitResponse(BaseModel):
    id: int
    user_id: UUID
    doctor_name: str
    specialty: Optional[str]
    visit_date: date
    reason: Optional[str]
    diagnosis: Optional[str]
    prescription: Optional[str]
    follow_up_date: Optional[date]
    notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# --- Medication Schemas ---

class MedicationCreate(BaseModel):
    name: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    prescribed_by: Optional[str] = None
    purpose: Optional[str] = None
    side_effects: Optional[str] = None


class MedicationUpdate(BaseModel):
    name: Optional[str] = None
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    prescribed_by: Optional[str] = None
    purpose: Optional[str] = None
    side_effects: Optional[str] = None
    is_active: Optional[bool] = None


class MedicationResponse(BaseModel):
    id: int
    user_id: UUID
    name: str
    dosage: Optional[str]
    frequency: Optional[str]
    start_date: Optional[date]
    end_date: Optional[date]
    prescribed_by: Optional[str]
    purpose: Optional[str]
    side_effects: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# --- Reminder Schemas ---

class ReminderCreate(BaseModel):
    medication_id: int
    reminder_time: time
    is_active: bool = True


class ReminderResponse(BaseModel):
    id: int
    medication_id: int
    user_id: UUID
    reminder_time: time
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# --- Chat Schemas ---

class ChatMessage(BaseModel):
    message: str
    context: Optional[str] = None
    history: Optional[List[Dict[str, Any]]] = None  # ← for Gemini memory


class ChatResponse(BaseModel):
    reply: str
    suggestions: Optional[List[DoctorSuggestion]] = None
    exercise_tips: Optional[Dict[str, Any]] = None
    context: Optional[str] = None