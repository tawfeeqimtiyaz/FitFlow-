from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import settings
from app.database import get_db
from app.models.user import User
from app.schemas.user import (
    UserCreate, UserResponse, Token, UserLogin,
    VerifyOtpRequest, ResendOtpRequest, MessageResponse,
)
from app.services.auth_service import AuthService
from app.services.email_service import EmailDeliveryError, EmailSender, get_email_sender
from app.services.otp_service import (
    AlreadyVerified, EmailVerificationService, InvalidOtp,
    ResendTooSoon, SendLimitReached, TooManyAttempts,
)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# Wording is intentionally generic so responses do not reveal which accounts exist
RESEND_MESSAGE = "If this email has an unverified account, a new verification code has been sent."
NOT_VERIFIED_DETAIL = "Email not verified. Enter the verification code we emailed you, or request a new one."


def _require_email_service(sender: EmailSender) -> None:
    if settings.EMAIL_VERIFICATION_REQUIRED and not sender.is_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email verification is temporarily unavailable. Please try again later.",
        )


def _require_verified(user: User) -> None:
    if settings.EMAIL_VERIFICATION_REQUIRED and not user.is_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=NOT_VERIFIED_DETAIL)


def _rate_limited(detail: str, retry_after: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail=detail,
        headers={"Retry-After": str(retry_after)},
    )


@router.post("/signup", response_model=UserResponse)
async def signup(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db),
    sender: EmailSender = Depends(get_email_sender),
):
    """Register a new user and email them a verification code"""
    # Fail before creating anything if we could not deliver the code anyway.
    _require_email_service(sender)

    try:
        user = await AuthService.create_user(db, user_data)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    if settings.EMAIL_VERIFICATION_REQUIRED:
        try:
            await EmailVerificationService.issue(db, user, sender)
        except EmailDeliveryError:
            # The account exists but is unverified; the user can request a new code.
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="We could not send the verification email. Please request a new code.",
            )
        except (ResendTooSoon, SendLimitReached) as e:
            raise _rate_limited(str(e), e.retry_after)

    return user


@router.post("/verify-otp", response_model=MessageResponse)
async def verify_otp(body: VerifyOtpRequest, db: AsyncSession = Depends(get_db)):
    """Confirm the emailed code. The account can log in afterwards."""
    user = await AuthService.get_user_by_email(db, body.email)
    if user is None:
        # Same answer as a wrong code, so this cannot be used to probe for accounts.
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")

    try:
        await EmailVerificationService.verify(db, user, body.otp)
    except AlreadyVerified:
        raise HTTPException(status_code=400, detail="Email is already verified")
    except TooManyAttempts:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many incorrect attempts. Please request a new code.",
        )
    except InvalidOtp:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")

    return {"message": "Email verified. You can now log in."}


@router.post("/resend-otp", response_model=MessageResponse)
async def resend_otp(
    body: ResendOtpRequest,
    db: AsyncSession = Depends(get_db),
    sender: EmailSender = Depends(get_email_sender),
):
    """Send a fresh verification code (subject to a cooldown and an hourly cap)"""
    _require_email_service(sender)

    user = await AuthService.get_user_by_email(db, body.email)
    if user is None or user.is_verified or not settings.EMAIL_VERIFICATION_REQUIRED:
        return {"message": RESEND_MESSAGE}

    try:
        await EmailVerificationService.issue(db, user, sender)
    except ResendTooSoon as e:
        raise _rate_limited(f"Please wait {e.retry_after} seconds before requesting another code.", e.retry_after)
    except SendLimitReached as e:
        raise _rate_limited("Too many verification emails requested. Please try again later.", e.retry_after)
    except EmailDeliveryError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="We could not send the verification email. Please try again shortly.",
        )

    return {"message": RESEND_MESSAGE}


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """Login with email and password (form)"""
    user = await AuthService.authenticate_user(db, form_data.username, form_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    _require_verified(user)

    access_token = AuthService.create_token(user)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login/json", response_model=Token)
async def login_json(
    credentials: UserLogin,          # ✅ FIXED: Was (email: str, password: str)
    db: AsyncSession = Depends(get_db)  #          which made them QUERY PARAMS
):
    """Login with JSON body"""
    user = await AuthService.authenticate_user(
        db,
        credentials.email,           # ✅ Now properly parsed from JSON body
        credentials.password
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    _require_verified(user)

    access_token = AuthService.create_token(user)
    return {"access_token": access_token, "token_type": "bearer"}
