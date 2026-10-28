from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import datetime
from app.models.exercise import ExerciseCategory, Exercise
from app.models.workout import WorkoutSession
from app.utils.ids import to_uuid


class WorkoutService:
    
    @staticmethod
    async def get_all_categories(db: AsyncSession) -> List[ExerciseCategory]:
        """Get all exercise categories"""
        result = await db.execute(select(ExerciseCategory))
        return result.scalars().all()
    
    @staticmethod
    async def get_exercises_by_category(
        db: AsyncSession, 
        category_id: str, 
        difficulty: Optional[str] = None
    ) -> List[Exercise]:
        """Get exercises by category and optional difficulty"""
        
        query = select(Exercise).where(Exercise.category_id == to_uuid(category_id))
        
        if difficulty:
            query = query.where(Exercise.difficulty_level == difficulty)
        
        result = await db.execute(query)
        return result.scalars().all()
    
    @staticmethod
    async def get_exercises_by_difficulty(db: AsyncSession, difficulty: str) -> List[Exercise]:
        """Get all exercises by difficulty level"""
        result = await db.execute(
            select(Exercise).where(Exercise.difficulty_level == difficulty)
        )
        return result.scalars().all()
    
    @staticmethod
    async def start_workout_session(
        db: AsyncSession, 
        user_id: str, 
        exercise_id: str
    ) -> WorkoutSession:
        """Start a new workout session"""
        
        session = WorkoutSession(
            user_id=to_uuid(user_id),
            exercise_id=to_uuid(exercise_id),
            started_at=datetime.utcnow()
        )
        
        db.add(session)
        await db.commit()
        await db.refresh(session)
        
        return session
    
    @staticmethod
    async def end_workout_session(
        db: AsyncSession,
        session_id: str,
        user_id: str,
        duration_seconds: int,
        completed: bool = True
    ) -> Optional[WorkoutSession]:
        """End a workout session"""
        
        result = await db.execute(
            select(WorkoutSession).where(
                WorkoutSession.id == to_uuid(session_id),
                WorkoutSession.user_id == to_uuid(user_id)
            )
        )
        session = result.scalar_one_or_none()
        
        if not session:
            return None
        
        # Get exercise to calculate calories
        exercise_result = await db.execute(
            select(Exercise).where(Exercise.id == session.exercise_id)
        )
        exercise = exercise_result.scalar_one_or_none()
        
        calories_burned = 0
        if exercise:
            minutes = duration_seconds / 60
            calories_burned = int(minutes * exercise.calories_burn_per_minute)
        
        session.ended_at = datetime.utcnow()
        session.duration_seconds = duration_seconds
        session.calories_burned = calories_burned
        session.completed = completed
        
        await db.commit()
        await db.refresh(session)
        
        return session
    
    @staticmethod
    async def get_user_workout_history(
        db: AsyncSession, 
        user_id: str, 
        limit: int = 20
    ) -> List[WorkoutSession]:
        """Get user's workout history"""
        result = await db.execute(
            select(WorkoutSession)
            .where(WorkoutSession.user_id == to_uuid(user_id))
            .order_by(WorkoutSession.started_at.desc())
            .limit(limit)
        )
        return result.scalars().all()