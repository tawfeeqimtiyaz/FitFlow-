from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime
from uuid import UUID


# --- User Schemas ---

class UserCreate(BaseModel):
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class GoogleLogin(BaseModel):
    token: str


class VerifyOtpRequest(BaseModel):
    email: EmailStr
    # Plain str on purpose: format is checked in the service so a bad value
    # never gets echoed back in a validation error.
    otp: str


class ResendOtpRequest(BaseModel):
    email: EmailStr


class MessageResponse(BaseModel):
    message: str


class UserResponse(BaseModel):
    id: UUID
    email: str
    is_active: bool
    is_verified: bool = False
    created_at: datetime
    auth_provider: Optional[str] = None  # ✅ Not in model, kept optional

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[str] = None


# --- Profile Schemas ---

class ProfileCreate(BaseModel):
    username: Optional[str] = None       # stored on User model
    age: Optional[int] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    profile_picture: Optional[str] = None  # maps to profile_image in DB
    fitness_level: Optional[str] = "beginner"


class ProfileUpdate(BaseModel):
    username: Optional[str] = None
    age: Optional[int] = None
    height: Optional[float] = None
    weight: Optional[float] = None
    profile_picture: Optional[str] = None
    fitness_level: Optional[str] = None


class ProfileResponse(BaseModel):
    id: UUID
    user_id: UUID
    username: Optional[str] = None       # ✅ Added default
    age: Optional[int] = None            # ✅ Added default
    height: Optional[float] = None       # ✅ Added default
    weight: Optional[float] = None       # ✅ Added default
    profile_picture: Optional[str] = None  # ✅ Added default (maps to profile_image)
    fitness_level: str = "beginner"      # ✅ Added default
    created_at: datetime

    class Config:
        from_attributes = True

    # ✅ Handles profile_image → profile_picture name mismatch
    @classmethod
    def from_orm_profile(cls, profile):
        return cls(
            id=profile.id,
            user_id=profile.user_id,
            username=None,               # pulled from User model separately
            age=profile.age,
            height=profile.height,
            weight=profile.weight,
            profile_picture=profile.profile_image,  # ✅ remapped here
            fitness_level=profile.fitness_level or "beginner",
            created_at=profile.created_at,
        )


class UserWithProfile(BaseModel):
    id: UUID
    email: str
    profile: Optional[ProfileResponse] = None  # ✅ Added default

    class Config:
        from_attributes = True