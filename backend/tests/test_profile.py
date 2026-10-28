import unittest

from tests.support import client, new_user


class ProfileTests(unittest.TestCase):
    def test_signup_creates_default_profile(self):
        user = new_user("prof")
        r = client.get("/api/users/me/profile", headers=user.headers)
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertEqual(body["user_id"], user.id)
        self.assertEqual(body["fitness_level"], "beginner")
        self.assertIsNone(body["profile_picture"])

    def test_update_persists_fitness_level_and_picture(self):
        user = new_user("upd")
        payload = {
            "age": 31,
            "height": 178.5,
            "weight": 72.4,
            "fitness_level": "advanced",
            "profile_picture": "https://example.com/me.png",
        }
        r = client.put("/api/users/me/profile", headers=user.headers, json=payload)
        self.assertEqual(r.status_code, 200, r.text)

        again = client.get("/api/users/me/profile", headers=user.headers).json()
        self.assertEqual(again["age"], 31)
        self.assertEqual(again["height"], 178.5)
        self.assertEqual(again["weight"], 72.4)
        self.assertEqual(again["fitness_level"], "advanced")
        self.assertEqual(again["profile_picture"], "https://example.com/me.png")

    def test_partial_update_keeps_other_fields(self):
        user = new_user("partial")
        client.put("/api/users/me/profile", headers=user.headers, json={"age": 40, "weight": 80})
        client.put("/api/users/me/profile", headers=user.headers, json={"weight": 78})
        body = client.get("/api/users/me/profile", headers=user.headers).json()
        self.assertEqual(body["age"], 40)
        self.assertEqual(body["weight"], 78)

    def test_username_update_is_reflected_in_profile(self):
        user = new_user("uname")
        r = client.put(
            "/api/users/me/profile", headers=user.headers, json={"username": "iron_ivy"}
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["username"], "iron_ivy")

    def test_create_profile_twice_is_a_400(self):
        user = new_user("twice")
        r = client.post("/api/users/me/profile", headers=user.headers, json={"age": 20})
        self.assertEqual(r.status_code, 400)

    def test_profiles_are_isolated_between_users(self):
        a, b = new_user("iso-a"), new_user("iso-b")
        client.put("/api/users/me/profile", headers=a.headers, json={"age": 25, "fitness_level": "advanced"})
        other = client.get("/api/users/me/profile", headers=b.headers).json()
        self.assertEqual(other["user_id"], b.id)
        self.assertIsNone(other["age"])
        self.assertEqual(other["fitness_level"], "beginner")


if __name__ == "__main__":
    unittest.main()
