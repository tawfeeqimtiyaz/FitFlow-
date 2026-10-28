import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Uuid
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class EmailVerification(Base):
    """The pending email-verification code for one user.

    There is at most one row per user and it is updated in place on resend, so
    the per-hour send counter survives resends. Only a keyed hash of the code
    is stored, never the code itself.
    """

    __tablename__ = "email_verifications"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    code_hash = Column(String(64), nullable=False)          # HMAC-SHA256 hex digest
    expires_at = Column(DateTime(timezone=True), nullable=False)
    attempts = Column(Integer, nullable=False, default=0)   # wrong guesses against this code

    last_sent_at = Column(DateTime(timezone=True), nullable=True)
    send_count = Column(Integer, nullable=False, default=0)          # sends in the current hour window
    send_window_start = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="email_verification")
