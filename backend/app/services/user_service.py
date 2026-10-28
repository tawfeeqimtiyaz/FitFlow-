from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from app.models.user import User, UserProfile
from app.schemas.user import ProfileCreate, ProfileUpdate
from app.utils.ids import to_uuid


# ── Field name map ────────────────────────────────────────────────────────────
# Schema name        →   Model column name
# profile_picture    →   profile_image
# username           →   lives on User, not UserProfile
#
SCHEMA_TO_MODEL = {
    "profile_picture": "profile_image",   # ✅ remap on write
}

PROFILE_ONLY_FIELDS = {                   # ✅ skip fields not on UserProfile
    "username",                           #    username lives on User model
}
# ─────────────────────────────────────────────────────────────────────────────


class UserService:

    @staticmethod
    async def get_profile(
        db: AsyncSession, user_id: str
    ) -> Optional[UserProfile]:
        """Get user profile"""
        user_id = to_uuid(user_id)
        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def create_profile(
        db: AsyncSession,
        user_id: str,
        profile_data: ProfileCreate
    ) -> UserProfile:
        """Create user profile"""
        user_id = to_uuid(user_id)

        # Check if profile already exists
        existing = await UserService.get_profile(db, user_id)
        if existing:
            raise ValueError("Profile already exists")

        # ✅ FIXED: was setting username (not on UserProfile)
        #           was setting profile_picture (wrong column name)
        profile = UserProfile(
            user_id=user_id,
            age=profile_data.age,
            height=profile_data.height,
            weight=profile_data.weight,
            profile_image=profile_data.profile_picture,  # ✅ remapped
            fitness_level=profile_data.fitness_level or "beginner",
        )

        # ✅ Handle username — update User model, not UserProfile
        if profile_data.username:
            user_result = await db.execute(
                select(User).where(User.id == user_id)
            )
            user = user_result.scalar_one_or_none()
            if user:
                user.username = profile_data.username

        db.add(profile)
        await db.commit()
        await db.refresh(profile)

        return profile

    @staticmethod
    async def update_profile(
        db: AsyncSession,
        user_id: str,
        profile_data: ProfileUpdate
    ) -> Optional[UserProfile]:
        """Update user profile"""
        user_id = to_uuid(user_id)

        result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == user_id)
        )
        profile = result.scalar_one_or_none()

        if not profile:
            return None

        update_data = profile_data.model_dump(exclude_unset=True)

        # ✅ FIXED: Handle username + field name remapping
        for schema_field, value in update_data.items():

            if schema_field in PROFILE_ONLY_FIELDS:
                # username → update User model instead
                if schema_field == "username" and value is not None:
                    user_result = await db.execute(
                        select(User).where(User.id == user_id)
                    )
                    user = user_result.scalar_one_or_none()
                    if user:
                        user.username = value
                continue                              # skip setting on profile

            # Remap schema field name → model column name if needed
            model_field = SCHEMA_TO_MODEL.get(schema_field, schema_field)

            if value is not None:
                setattr(profile, model_field, value)  # ✅ uses model name

        await db.commit()
        await db.refresh(profile)

        return profile