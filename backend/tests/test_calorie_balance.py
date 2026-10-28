import unittest
import uuid

from tests.support import client, new_user

BEGINNER = {"Walking", "Light Cycling", "Yoga"}
ADVANCED = {"Running", "HIIT", "Boxing"}


def log_meal(user, calories, name="Test meal"):
    r = client.post(
        "/api/calorie/meals",
        headers=user.headers,
        json={"food_name": name, "calories": calories, "meal_type": "dinner"},
    )
    assert r.status_code == 200, r.text
    return r.json()


def balance(user):
    r = client.get("/api/calorie/balance", headers=user.headers)
    assert r.status_code == 200, r.text
    return r.json()


class CalorieBalanceTests(unittest.TestCase):
    def test_new_user_gets_default_goal_and_light_walk(self):
        user = new_user("bal-new")
        body = balance(user)
        self.assertEqual(body["target_calories"], 2000)
        self.assertEqual(body["consumed_calories"], 0)
        self.assertEqual(body["excess_calories"], 0)
        self.assertIn("remaining", body["message"])
        self.assertEqual(body["recommended_exercises"][0]["exercise_name"], "Light Walk")

    def test_close_to_target_is_on_track(self):
        user = new_user("bal-track")
        log_meal(user, 1800)
        body = balance(user)
        self.assertEqual(body["consumed_calories"], 1800)
        self.assertEqual(body["excess_calories"], 0)
        self.assertIn("on track", body["message"])

    def test_over_target_recommends_exercises_for_fitness_level(self):
        user = new_user("bal-over")
        log_meal(user, 2500)
        body = balance(user)
        self.assertEqual(body["excess_calories"], 500)
        names = {e["exercise_name"] for e in body["recommended_exercises"]}
        self.assertEqual(names, BEGINNER)  # default level is beginner
        self.assertIn("over your target", body["message"])

    def test_recommendations_follow_profile_fitness_level(self):
        user = new_user("bal-adv")
        client.put("/api/users/me/profile", headers=user.headers, json={"fitness_level": "advanced"})
        log_meal(user, 2600)
        names = {e["exercise_name"] for e in balance(user)["recommended_exercises"]}
        self.assertEqual(names, ADVANCED)

    def test_meal_quantity_multiplies_nutrition(self):
        user = new_user("bal-qty")
        r = client.post(
            "/api/calorie/meals",
            headers=user.headers,
            json={"food_name": "Rice", "calories": 200, "protein": 4, "quantity": 2.5},
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["calories"], 500)
        self.assertEqual(r.json()["protein"], 10)

    def test_progress_reflects_logged_meal_and_water(self):
        user = new_user("bal-prog")
        log_meal(user, 500)
        water = client.post("/api/calorie/water", headers=user.headers, json={"amount": 750})
        self.assertEqual(water.status_code, 200)
        body = client.get("/api/calorie/progress", headers=user.headers).json()
        self.assertEqual(body["intake"]["total_calories"], 500)
        self.assertEqual(body["intake"]["meals_count"], 1)
        self.assertAlmostEqual(body["intake"]["water_intake"], 0.75)
        self.assertEqual(body["calories_remaining"], 1500)

    def test_delete_meal_updates_totals_and_bad_id_is_404(self):
        user = new_user("bal-del")
        meal = log_meal(user, 900)
        gone = client.delete(f"/api/calorie/meals/{meal['id']}", headers=user.headers)
        self.assertEqual(gone.status_code, 200)
        self.assertEqual(balance(user)["consumed_calories"], 0)

        for bad in ("not-a-uuid", str(uuid.uuid4())):
            with self.subTest(meal_id=bad):
                r = client.delete(f"/api/calorie/meals/{bad}", headers=user.headers)
                self.assertEqual(r.status_code, 404)

    def test_other_users_meal_cannot_be_deleted(self):
        owner, intruder = new_user("bal-own"), new_user("bal-bad")
        meal = log_meal(owner, 400)
        r = client.delete(f"/api/calorie/meals/{meal['id']}", headers=intruder.headers)
        self.assertEqual(r.status_code, 404)
        self.assertEqual(balance(owner)["consumed_calories"], 400)

    def test_goals_are_calculated_from_profile(self):
        user = new_user("bal-goal")
        client.put(
            "/api/users/me/profile",
            headers=user.headers,
            json={"age": 30, "height": 180, "weight": 80},
        )
        r = client.post(
            "/api/calorie/goals",
            headers=user.headers,
            json={"goal_type": "weight_loss", "activity_level": "moderate"},
        )
        self.assertEqual(r.status_code, 200, r.text)
        # Mifflin-St Jeor (male): 10*80 + 6.25*180 - 5*30 + 5 = 1780; x1.55 - 500
        self.assertEqual(r.json()["daily_calories"], round(1780 * 1.55 - 500))
        self.assertEqual(balance(user)["target_calories"], round(1780 * 1.55 - 500))


if __name__ == "__main__":
    unittest.main()
