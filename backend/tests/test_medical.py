import unittest

from sqlalchemy import Uuid

from tests.support import client, new_user

import app.models  # noqa: F401  (registers every table on Base.metadata)
from app.database import Base


class UuidSchemaTests(unittest.TestCase):
    def test_every_foreign_key_to_users_is_a_uuid_column(self):
        # Regression: the medical tables declared Integer user_id columns
        # pointing at the UUID users.id, which PostgreSQL rejects.
        checked = []
        for table in Base.metadata.sorted_tables:
            for fk in table.foreign_keys:
                if fk.column.table.name == "users":
                    checked.append(f"{table.name}.{fk.parent.name}")
                    self.assertIsInstance(
                        fk.parent.type, Uuid, f"{table.name}.{fk.parent.name} is not a UUID column"
                    )
        for expected in (
            "symptoms.user_id", "doctor_visits.user_id",
            "medications.user_id", "medication_reminders.user_id",
        ):
            self.assertIn(expected, checked)

    def test_profile_has_fitness_level_and_profile_image(self):
        columns = Base.metadata.tables["user_profiles"].c
        self.assertIn("fitness_level", columns)
        self.assertIn("profile_image", columns)


class MedicalEndpointTests(unittest.TestCase):
    def test_symptom_round_trip_carries_uuid_user_id(self):
        user = new_user("med-sym")
        made = client.post(
            "/api/medical/symptoms",
            headers=user.headers,
            json={"name": "knee pain", "severity": 6, "description": "after squats"},
        )
        self.assertEqual(made.status_code, 200, made.text)
        self.assertEqual(made.json()["user_id"], user.id)

        listed = client.get("/api/medical/symptoms", headers=user.headers).json()
        self.assertEqual([s["name"] for s in listed], ["knee pain"])

    def test_doctor_visit_round_trip(self):
        user = new_user("med-doc")
        made = client.post(
            "/api/medical/doctor-visits",
            headers=user.headers,
            json={"doctor_name": "Dr. Rao", "visit_date": "2026-10-01", "follow_up_date": "2026-11-01"},
        )
        self.assertEqual(made.status_code, 200, made.text)
        self.assertEqual(made.json()["user_id"], user.id)
        visits = client.get("/api/medical/doctor-visits", headers=user.headers).json()
        self.assertEqual(visits[0]["visit_date"], "2026-10-01")

    def test_medication_lifecycle_and_active_filter(self):
        user = new_user("med-med")
        med = client.post(
            "/api/medical/medications", headers=user.headers, json={"name": "Vitamin D", "dosage": "1000 IU"}
        ).json()
        self.assertEqual(med["user_id"], user.id)
        self.assertTrue(med["is_active"])

        upd = client.put(
            f"/api/medical/medications/{med['id']}", headers=user.headers, json={"is_active": False}
        )
        self.assertEqual(upd.status_code, 200)
        self.assertFalse(upd.json()["is_active"])
        self.assertEqual(upd.json()["dosage"], "1000 IU")  # untouched fields survive

        active = client.get("/api/medical/medications?active_only=true", headers=user.headers).json()
        self.assertEqual(active, [])
        everything = client.get("/api/medical/medications", headers=user.headers).json()
        self.assertEqual(len(everything), 1)

        deleted = client.delete(f"/api/medical/medications/{med['id']}", headers=user.headers)
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(client.get("/api/medical/medications", headers=user.headers).json(), [])

    def test_reminder_is_linked_to_medication_and_user(self):
        user = new_user("med-rem")
        med = client.post("/api/medical/medications", headers=user.headers, json={"name": "Iron"}).json()
        rem = client.post(
            "/api/medical/reminders",
            headers=user.headers,
            json={"medication_id": med["id"], "reminder_time": "08:30:00"},
        )
        self.assertEqual(rem.status_code, 200, rem.text)
        self.assertEqual(rem.json()["user_id"], user.id)
        self.assertEqual(rem.json()["medication_id"], med["id"])
        self.assertEqual(rem.json()["reminder_time"], "08:30:00")

        listed = client.get("/api/medical/reminders", headers=user.headers).json()
        self.assertEqual(len(listed), 1)
        gone = client.delete(f"/api/medical/reminders/{rem.json()['id']}", headers=user.headers)
        self.assertEqual(gone.status_code, 200)

    def test_records_are_isolated_between_users(self):
        owner, other = new_user("med-own"), new_user("med-oth")
        med = client.post("/api/medical/medications", headers=owner.headers, json={"name": "Private"}).json()
        client.post("/api/medical/symptoms", headers=owner.headers, json={"name": "Private symptom"})

        self.assertEqual(client.get("/api/medical/medications", headers=other.headers).json(), [])
        self.assertEqual(client.get("/api/medical/symptoms", headers=other.headers).json(), [])
        self.assertEqual(
            client.put(
                f"/api/medical/medications/{med['id']}", headers=other.headers, json={"name": "Hijack"}
            ).status_code,
            404,
        )
        self.assertEqual(
            client.delete(f"/api/medical/medications/{med['id']}", headers=other.headers).status_code, 404
        )


if __name__ == "__main__":
    unittest.main()
