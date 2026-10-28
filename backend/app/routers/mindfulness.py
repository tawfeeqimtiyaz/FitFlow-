from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List
from uuid import UUID
from datetime import datetime
from app.database import get_db
from app.models.user import User
from app.models.mindfulness import MeditationSession
from app.schemas.mindfulness import (
    MeditationSessionCreate, MeditationSessionEnd, 
    MeditationSessionResponse, MindfulnessStats
)
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/api/mindfulness", tags=["Mindfulness"])


@router.post("/sessions/start", response_model=MeditationSessionResponse)
async def start_session(
    session_data: MeditationSessionCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Start a meditation/mindfulness session"""
    session = MeditationSession(
        user_id=current_user.id,
        session_type=session_data.session_type
    )
    
    db.add(session)
    await db.commit()
    await db.refresh(session)
    
    return session


@router.post("/sessions/{session_id}/end", response_model=MeditationSessionResponse)
async def end_session(
    session_id: UUID,
    session_data: MeditationSessionEnd,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """End a meditation session"""
    result = await db.execute(
        select(MeditationSession).where(
            MeditationSession.id == session_id,
            MeditationSession.user_id == current_user.id
        )
    )
    session = result.scalar_one_or_none()
    
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session.duration_seconds = session_data.duration_seconds
    session.completed = session_data.completed
    session.completed_at = datetime.utcnow()
    
    await db.commit()
    await db.refresh(session)
    
    return session


@router.get("/sessions", response_model=List[MeditationSessionResponse])
async def get_sessions(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get meditation session history"""
    result = await db.execute(
        select(MeditationSession)
        .where(MeditationSession.user_id == current_user.id)
        .order_by(MeditationSession.started_at.desc())
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/stats", response_model=MindfulnessStats)
async def get_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Get mindfulness statistics"""
    
    # Total sessions
    total_result = await db.execute(
        select(func.count(MeditationSession.id))
        .where(MeditationSession.user_id == current_user.id)
    )
    total_sessions = total_result.scalar() or 0
    
    # Total minutes
    minutes_result = await db.execute(
        select(func.sum(MeditationSession.duration_seconds))
        .where(MeditationSession.user_id == current_user.id)
    )
    total_seconds = minutes_result.scalar() or 0
    total_minutes = total_seconds // 60
    
    # Meditation sessions count
    meditation_result = await db.execute(
        select(func.count(MeditationSession.id))
        .where(
            MeditationSession.user_id == current_user.id,
            MeditationSession.session_type == "meditation"
        )
    )
    meditation_sessions = meditation_result.scalar() or 0
    
    # Minigame sessions count
    minigame_result = await db.execute(
        select(func.count(MeditationSession.id))
        .where(
            MeditationSession.user_id == current_user.id,
            MeditationSession.session_type == "minigame"
        )
    )
    minigame_sessions = minigame_result.scalar() or 0
    
    # Current streak (simplified - counts consecutive days)
    # For production, implement proper streak logic
    current_streak = 0
    
    return MindfulnessStats(
        total_sessions=total_sessions,
        total_minutes=total_minutes,
        meditation_sessions=meditation_sessions,
        minigame_sessions=minigame_sessions,
        current_streak=current_streak
    )