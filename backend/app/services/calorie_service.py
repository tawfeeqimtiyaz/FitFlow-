from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional, List
from datetime import date, datetime
from uuid import UUID

from app.models.calorie import UserGoal, MealLog, DailyIntake, WaterLog
from app.models.user import UserProfile
from app.schemas.calorie import GoalCreate, GoalUpdate, MealLogCreate, WaterLogCreate
from app.services.food_ai_service import FoodAIService


class CalorieService:

    @staticmethod
    async def get_or_create_goal(db: AsyncSession, user_id: str) -> UserGoal:
        """Get user's goal or create default one"""
        # Cast string → UUID for user lookup
        user_uuid = UUID(user_id)

        result = await db.execute(
            select(UserGoal).where(UserGoal.user_id == user_uuid)
        )
        goal = result.scalar_one_or_none()

        if not goal:
            goal = UserGoal(
                user_id=user_uuid,
                goal_type="maintenance",
                activity_level="moderate",
                daily_calories=2000,
                daily_protein=150,
                daily_carbs=200,
                daily_fat=65,
                daily_water=2.5
            )
            db.add(goal)
            await db.commit()
            await db.refresh(goal)

        return goal

    @staticmethod
    async def create_goal(
        db: AsyncSession, user_id: str, goal_data: GoalCreate
    ) -> UserGoal:
        """Create or update user's nutrition goal"""
        user_uuid = UUID(user_id)                   # str -> UUID

        result = await db.execute(
            select(UserGoal).where(UserGoal.user_id == user_uuid)
        )
        existing_goal = result.scalar_one_or_none()

        # Get user profile for calculations
        profile_result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == user_uuid)
        )
        profile = profile_result.scalar_one_or_none()

        # Calculate targets if profile exists
        targets = {}
        if profile and profile.weight and profile.height and profile.age:
            targets = FoodAIService.calculate_daily_targets(
                weight=profile.weight,
                height=profile.height,
                age=profile.age,
                gender="male",
                activity_level=goal_data.activity_level.value,
                goal_type=goal_data.goal_type.value
            )

        goal_values = {
            "goal_type":      goal_data.goal_type.value,
            "target_weight":  goal_data.target_weight,
            "activity_level": goal_data.activity_level.value,
            "daily_calories": targets.get("daily_calories", 2000),
            "daily_protein":  targets.get("daily_protein", 150),
            "daily_carbs":    targets.get("daily_carbs", 200),
            "daily_fat":      targets.get("daily_fat", 65),
            "daily_water":    targets.get("daily_water", 2.5),
        }

        if existing_goal:
            for field, value in goal_values.items():
                setattr(existing_goal, field, value)
            await db.commit()
            await db.refresh(existing_goal)
            return existing_goal
        else:
            goal = UserGoal(user_id=user_uuid, **goal_values)
            db.add(goal)
            await db.commit()
            await db.refresh(goal)
            return goal

    @staticmethod
    async def update_goal(
        db: AsyncSession, user_id: str, goal_data: GoalUpdate
    ) -> Optional[UserGoal]:
        """Update user's nutrition goal"""
        user_uuid = UUID(user_id)                   # str -> UUID

        result = await db.execute(
            select(UserGoal).where(UserGoal.user_id == user_uuid)
        )
        goal = result.scalar_one_or_none()

        if not goal:
            return None

        update_data = goal_data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                setattr(goal, field, value.value if hasattr(value, 'value') else value)

        await db.commit()
        await db.refresh(goal)
        return goal

    @staticmethod
    async def log_meal(
        db: AsyncSession, user_id: str, meal_data: MealLogCreate
    ) -> MealLog:
        """Log a meal entry"""
        user_uuid = UUID(user_id)                   # str -> UUID
        meal_date = meal_data.meal_date or date.today()

        meal = MealLog(
            user_id=user_uuid,
            meal_type=meal_data.meal_type.value,
            food_name=meal_data.food_name,
            serving_size=meal_data.serving_size,
            quantity=meal_data.quantity,
            calories=meal_data.calories * meal_data.quantity,
            protein=meal_data.protein  * meal_data.quantity,
            carbs=meal_data.carbs    * meal_data.quantity,
            fat=meal_data.fat      * meal_data.quantity,
            fiber=meal_data.fiber    * meal_data.quantity,
            sugar=meal_data.sugar    * meal_data.quantity,
            sodium=meal_data.sodium   * meal_data.quantity,
            image_url=meal_data.image_url,
            ai_detected=meal_data.ai_detected,
            confidence=meal_data.confidence,
            notes=meal_data.notes,
            meal_date=meal_date
        )

        db.add(meal)
        await db.commit()
        await db.refresh(meal)

        await CalorieService._update_daily_intake(db, user_uuid, meal_date)
        return meal

    @staticmethod
    async def _update_daily_intake(
        db: AsyncSession, user_id: UUID, intake_date: date
    ):
        """Update daily intake totals"""
        result = await db.execute(
            select(MealLog).where(
                MealLog.user_id == user_id,
                MealLog.meal_date == intake_date
            )
        )
        meals = result.scalars().all()

        total_calories = sum(m.calories for m in meals)
        total_protein  = sum(m.protein  for m in meals)
        total_carbs    = sum(m.carbs    for m in meals)
        total_fat      = sum(m.fat      for m in meals)
        total_fiber    = sum(m.fiber    for m in meals)

        intake_result = await db.execute(
            select(DailyIntake).where(
                DailyIntake.user_id == user_id,
                DailyIntake.intake_date == intake_date
            )
        )
        daily_intake = intake_result.scalar_one_or_none()

        if daily_intake:
            daily_intake.total_calories = total_calories
            daily_intake.total_protein  = total_protein
            daily_intake.total_carbs    = total_carbs
            daily_intake.total_fat      = total_fat
            daily_intake.total_fiber    = total_fiber
            daily_intake.meals_count    = len(meals)
        else:
            daily_intake = DailyIntake(
                user_id=user_id,
                intake_date=intake_date,
                total_calories=total_calories,
                total_protein=total_protein,
                total_carbs=total_carbs,
                total_fat=total_fat,
                total_fiber=total_fiber,
                meals_count=len(meals)
            )
            db.add(daily_intake)

        await db.commit()

    @staticmethod
    async def get_meals_by_date(
        db: AsyncSession, user_id: str, meal_date: date
    ) -> List[MealLog]:
        """Get all meals for a specific date"""
        user_uuid = UUID(user_id)                   # str -> UUID

        result = await db.execute(
            select(MealLog).where(
                MealLog.user_id == user_uuid,
                MealLog.meal_date == meal_date
            ).order_by(MealLog.logged_at.desc())
        )
        return result.scalars().all()

    @staticmethod
    async def get_daily_intake(
        db: AsyncSession, user_id: str, intake_date: date
    ) -> Optional[DailyIntake]:
        """Get daily intake for a specific date"""
        user_uuid = UUID(user_id)                   # str -> UUID

        result = await db.execute(
            select(DailyIntake).where(
                DailyIntake.user_id == user_uuid,
                DailyIntake.intake_date == intake_date
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def get_daily_progress(
        db: AsyncSession, user_id: str, progress_date: date = None
    ) -> dict:
        """Get daily progress including goals and intake"""
        if progress_date is None:
            progress_date = date.today()

        goal   = await CalorieService.get_or_create_goal(db, user_id)
        intake = await CalorieService.get_daily_intake(db, user_id, progress_date)

        # ✅ FIXED: Was creating unsaved ORM object — use plain dict instead
        #           Unsaved ORM objects cause DetachedInstanceError on serialize
        if not intake:
            intake_data = {
                "total_calories": 0,
                "total_protein":  0,
                "total_carbs":    0,
                "total_fat":      0,
                "total_fiber":    0,
                "water_intake":   0,
                "meals_count":    0,
            }
        else:
            intake_data = {
                "total_calories": intake.total_calories,
                "total_protein":  intake.total_protein,
                "total_carbs":    intake.total_carbs,
                "total_fat":      intake.total_fat,
                "total_fiber":    intake.total_fiber,
                "water_intake":   intake.water_intake,
                "meals_count":    intake.meals_count,
            }

        daily_calories = goal.daily_calories or 2000
        daily_protein  = goal.daily_protein  or 150
        daily_carbs    = goal.daily_carbs    or 200
        daily_fat      = goal.daily_fat      or 65
        daily_water    = goal.daily_water    or 2.5

        return {
            "date":  progress_date,
            "goals": goal,
            "intake": intake_data,                 # ✅ plain dict, safe to serialize
            "calories_remaining": round(daily_calories - intake_data["total_calories"], 1),
            "protein_remaining":  round(daily_protein  - intake_data["total_protein"],  1),
            "carbs_remaining":    round(daily_carbs    - intake_data["total_carbs"],    1),
            "fat_remaining":      round(daily_fat      - intake_data["total_fat"],      1),
            "water_remaining":    round(daily_water    - intake_data["water_intake"],   2),
            "progress_percentage": round(
                min(100, (intake_data["total_calories"] / daily_calories) * 100), 1
            )
        }

    @staticmethod
    async def log_water(
        db: AsyncSession, user_id: str, water_data: WaterLogCreate
    ) -> WaterLog:
        """Log water intake"""
        user_uuid = UUID(user_id)                   # str -> UUID
        log_date  = date.today()

        water_log = WaterLog(
            user_id=user_uuid,
            amount=water_data.amount,
            log_date=log_date
        )

        db.add(water_log)
        await db.commit()
        await db.refresh(water_log)

        await CalorieService._update_daily_water(db, user_uuid, log_date)
        return water_log

    @staticmethod
    async def _update_daily_water(
        db: AsyncSession, user_id: UUID, log_date: date
    ):
        """Update daily water intake total"""
        result = await db.execute(
            select(func.sum(WaterLog.amount)).where(
                WaterLog.user_id == user_id,
                WaterLog.log_date == log_date
            )
        )
        total_water        = result.scalar() or 0
        total_water_liters = total_water / 1000     # ml → liters

        intake_result = await db.execute(
            select(DailyIntake).where(
                DailyIntake.user_id == user_id,
                DailyIntake.intake_date == log_date
            )
        )
        daily_intake = intake_result.scalar_one_or_none()

        if daily_intake:
            daily_intake.water_intake = total_water_liters
        else:
            daily_intake = DailyIntake(
                user_id=user_id,
                intake_date=log_date,
                water_intake=total_water_liters
            )
            db.add(daily_intake)

        await db.commit()

    @staticmethod
    async def get_calorie_balance(db: AsyncSession, user_id: str) -> dict:
        """Get calorie balance and exercise recommendations"""
        progress = await CalorieService.get_daily_progress(db, user_id)

        excess_calories = -(progress["calories_remaining"])

        profile_result = await db.execute(
            select(UserProfile).where(UserProfile.user_id == UUID(user_id))   # ✅
        )
        profile = profile_result.scalar_one_or_none()
        fitness_level = profile.fitness_level if profile else "beginner"

        recommendations = FoodAIService.get_exercise_recommendations(
            excess_calories=excess_calories,
            fitness_level=fitness_level
        )

        if excess_calories > 0:
            message = (
                f"You've consumed {round(excess_calories)} calories over your target. "
                f"Here are some exercises to balance it out!"
            )
        elif excess_calories < -500:
            message = (
                f"You have {round(abs(excess_calories))} calories remaining. "
                f"Make sure to eat enough!"
            )
        else:
            message = "You're on track! Keep up the good work."

        return {
            "consumed_calories":    progress["intake"]["total_calories"],  # ✅ dict access
            "target_calories":      progress["goals"].daily_calories,
            "excess_calories":      max(0, excess_calories),
            "recommended_exercises": recommendations,
            "message":              message
        }

    @staticmethod
    async def delete_meal(
        db: AsyncSession, user_id: str, meal_id: str
    ) -> bool:
        """Delete a meal log"""
        # Both IDs cast to UUID; a malformed id simply means "not found"
        try:
            user_uuid = UUID(user_id)
            meal_uuid = UUID(meal_id)
        except ValueError:
            return False

        result = await db.execute(
            select(MealLog).where(
                MealLog.id      == meal_uuid,
                MealLog.user_id == user_uuid
            )
        )
        meal = result.scalar_one_or_none()

        if not meal:
            return False

        meal_date = meal.meal_date
        await db.delete(meal)
        await db.commit()

        await CalorieService._update_daily_intake(db, user_uuid, meal_date)
        return True