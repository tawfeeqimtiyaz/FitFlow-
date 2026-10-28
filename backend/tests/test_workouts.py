import unittest
import uuid

from tests.support import client, new_user, run_async

from app.database import AsyncSessionLocal
from app.models.exercise import Exercise, ExerciseCategory


async def _seed_exercise(difficulty="beginner", kcal_per_min=5):
    async with AsyncSessionLocal() as db:
        category = ExerciseCategory(name=f"Core-{uuid.uuid4().hex[:6]}")
        db.add(category)
        await db.flush()
        exercise = Exercise(
            category_id=category.id, name="Plank", difficulty_level=difficulty,
            calories_burn_per_minute=kcal_per_min,
        )
        db.add(exercise)
        await db.commit()
        return str(category.id), str(exercise.id)


class WorkoutTests(unittest.TestCase):
    def test_catalogue_endpoints_are_public_and_filter(self):
        category_id, exercise_id = run_async(_seed_exercise, "intermediate")
        self.assertIn(category_id, [c["id"] for c in client.get("/api/workouts/categories").json()])

        in_category = client.get(f"/api/workouts/categories/{category_id}/exercises").json()
        self.assertEqual([e["id"] for e in in_category], [exercise_id])
        by_level = client.get("/api/workouts/difficulty/intermediate").json()
        self.assertIn(exercise_id, [e["id"] for e in by_level])
        self.assertEqual(client.get("/api/workouts/difficulty/impossible").status_code, 400)

    def test_session_start_end_computes_calories_and_appears_in_history(self):
        user = new_user("wk")
        _, exercise_id = run_async(_seed_exercise, "beginner", 5)

        started = client.post(
            "/api/workouts/sessions/start", headers=user.headers, json={"exercise_id": exercise_id}
        )
        self.assertEqual(started.status_code, 200, started.text)
        self.assertEqual(started.json()["user_id"], user.id)
        session_id = started.json()["id"]

        ended = client.post(
            f"/api/workouts/sessions/{session_id}/end",
            headers=user.headers,
            json={"duration_seconds": 600, "completed": True},
        )
        self.assertEqual(ended.status_code, 200, ended.text)
        self.assertEqual(ended.json()["calories_burned"], 50)  # 10 min x 5 kcal/min
        self.assertTrue(ended.json()["completed"])

        history = client.get("/api/workouts/history", headers=user.headers).json()
        self.assertEqual([h["id"] for h in history], [session_id])

    def test_other_users_session_cannot_be_ended(self):
        owner, intruder = new_user("wk-own"), new_user("wk-bad")
        _, exercise_id = run_async(_seed_exercise)
        session_id = client.post(
            "/api/workouts/sessions/start", headers=owner.headers, json={"exercise_id": exercise_id}
        ).json()["id"]

        r = client.post(
            f"/api/workouts/sessions/{session_id}/end",
            headers=intruder.headers,
            json={"duration_seconds": 60},
        )
        self.assertEqual(r.status_code, 404)

    def test_malformed_ids_are_validation_errors_not_server_errors(self):
        user = new_user("wk-bad-id")
        self.assertEqual(
            client.post(
                "/api/workouts/sessions/not-a-uuid/end", headers=user.headers, json={"duration_seconds": 1}
            ).status_code,
            422,
        )
        self.assertEqual(client.get("/api/workouts/categories/not-a-uuid/exercises").status_code, 422)


class MindfulnessTests(unittest.TestCase):
    def test_session_lifecycle_and_stats(self):
        user = new_user("mind")
        started = client.post(
            "/api/mindfulness/sessions/start", headers=user.headers, json={"session_type": "meditation"}
        )
        self.assertEqual(started.status_code, 200, started.text)
        self.assertEqual(started.json()["user_id"], user.id)

        ended = client.post(
            f"/api/mindfulness/sessions/{started.json()['id']}/end",
            headers=user.headers,
            json={"duration_seconds": 300},
        )
        self.assertEqual(ended.status_code, 200)

        stats = client.get("/api/mindfulness/stats", headers=user.headers).json()
        self.assertEqual(stats["total_sessions"], 1)
        self.assertEqual(stats["total_minutes"], 5)
        self.assertEqual(stats["meditation_sessions"], 1)

        missing = client.post(
            f"/api/mindfulness/sessions/{uuid.uuid4()}/end", headers=user.headers, json={"duration_seconds": 1}
        )
        self.assertEqual(missing.status_code, 404)


if __name__ == "__main__":
    unittest.main()
