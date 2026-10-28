from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from uuid import UUID
from app.database import get_db
from app.models.user import User
from app.schemas.exercise import ExerciseCategoryResponse, ExerciseResponse
from app.schemas.workout import WorkoutSessionCreate, WorkoutSessionEnd, WorkoutSessionResponse
from app.services.workout_service import WorkoutService
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/workouts", tags=["Workouts"])


@router.get("/categories", response_model=List[ExerciseCategoryResponse])
async def get_categories(db: AsyncSession = Depends(get_db)):
    """Get all exercise categories"""
    categories = await WorkoutService.get_all_categories(db)
    return categories


@router.get("/categories/{category_id}/exercises", response_model=List[ExerciseResponse])
async def get_exercises_by_category(
    category_id: UUID,
    difficulty: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get exercises by category"""
    exercises = await WorkoutService.get_exercises_by_category(db, category_id, difficulty)
    return exercises


@router.get("/difficulty/{level}", response_model=List[ExerciseResponse])
async def get_exercises_by_difficulty(
    level: str,
    db: AsyncSession = Depends(get_db)
):
    """Get exercises by difficulty (beginner, intermediate, advanced)"""
    if level not in ["beginner", "intermediate", "advanced"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid difficulty level"
        )
    
    exercises = await WorkoutService.get_exercises_by_difficulty(db, level)
    return exercises


@router.post("/sessions/start", response_model=WorkoutSessionResponse)
async def start_workout(
    session_data: WorkoutSessionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Start a workout session"""
    session = await WorkoutService.start_workout_session(
        db, str(current_user.id), str(session_data.exercise_id)
    )
    return session


@router.post("/sessions/{session_id}/end", response_model=WorkoutSessionResponse)
async def end_workout(
    session_id: UUID,
    session_data: WorkoutSessionEnd,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """End a workout session"""
    session = await WorkoutService.end_workout_session(
        db,
        session_id,
        str(current_user.id),
        session_data.duration_seconds,
        session_data.completed
    )
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    return session


@router.get("/history", response_model=List[WorkoutSessionResponse])
async def get_workout_history(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get workout history"""
    history = await WorkoutService.get_user_workout_history(db, str(current_user.id), limit)
    return history