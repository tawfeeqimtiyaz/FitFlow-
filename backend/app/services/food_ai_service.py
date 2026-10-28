import base64
import httpx
import json
import re
from typing import List, Dict, Optional
from app.config import settings


class FoodAIService:

    # ✅ FIXED: Correct Clarifai API URL with user/app path
    CLARIFAI_API_URL = (
        "https://api.clarifai.com/v2/users/clarifai/apps/main/"
        "models/food-item-recognition/outputs"
    )
    GEMINI_API_URL = (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/{settings.GEMINI_MODEL}:generateContent"
    )

    # ================================================================
    # FOOD DETECTION
    # ================================================================

    @staticmethod
    async def detect_food_from_image(image_base64: str) -> Dict:
        """Detect food from image using Clarifai"""

        if not settings.CLARIFAI_PAT:
            print("⚠️  No CLARIFAI_PAT — using mock detection")
            return FoodAIService._get_mock_detection()

        headers = {
            "Authorization": f"Key {settings.CLARIFAI_PAT}",
            "Content-Type":  "application/json"
        }

        payload = {
            "user_app_id": {                   # ✅ ADDED: required by Clarifai v2
                "user_id": "clarifai",
                "app_id":  "main"
            },
            "inputs": [{
                "data": {
                    "image": {"base64": image_base64}
                }
            }]
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    FoodAIService.CLARIFAI_API_URL,
                    headers=headers,
                    json=payload
                )

                print(f"Clarifai status: {response.status_code}")

                if response.status_code == 200:
                    data     = response.json()
                    concepts = (
                        data.get("outputs", [{}])[0]
                            .get("data", {})
                            .get("concepts", [])
                    )

                    if not concepts:
                        print("Clarifai returned no concepts")
                        return FoodAIService._get_mock_detection()

                    detected_foods = [
                        {
                            "name":       c.get("name", "Unknown"),
                            "confidence": round(c.get("value", 0) * 100, 2)
                        }
                        for c in concepts[:5]
                    ]

                    return {
                        "success":        True,
                        "detected_foods": detected_foods,
                        "top_food":       detected_foods[0]["name"],
                        "confidence":     detected_foods[0]["confidence"]
                    }

                else:
                    # ✅ Log the actual error for debugging
                    print(f"Clarifai error: {response.status_code} — {response.text}")
                    return FoodAIService._get_mock_detection()

        except Exception as e:
            print(f"Clarifai exception: {e}")
            return FoodAIService._get_mock_detection()

    # ================================================================
    # NUTRITION — Gemini
    # ================================================================

    @staticmethod
    async def get_nutrition_data(
        food_name: str,
        serving_size: Optional[str] = None
    ) -> Dict:
        if settings.GEMINI_API_KEY:
            return await FoodAIService._get_nutrition_from_gemini(
                food_name, serving_size
            )
        return FoodAIService._get_mock_nutrition(food_name)

    @staticmethod
    async def _get_nutrition_from_gemini(
        food_name: str,
        serving_size: Optional[str] = None
    ) -> Dict:

        serving_text = f"({serving_size})" if serving_size else "(1 standard serving)"

        prompt = f"""
You are a nutrition expert. Provide accurate nutrition data for:
Food: {food_name} {serving_text}

Respond ONLY with a valid JSON object — no markdown, no extra text:
{{
  "food_name": "{food_name}",
  "serving_size": "1 serving",
  "serving_qty": 1,
  "calories": 250,
  "protein": 12.5,
  "carbs": 30.2,
  "fat": 8.1,
  "fiber": 3.2,
  "sugar": 5.1,
  "sodium": 450.0
}}
"""

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature":     0.1,
                "maxOutputTokens": 512,
            }
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{FoodAIService.GEMINI_API_URL}?key={settings.GEMINI_API_KEY}",
                    headers={"Content-Type": "application/json"},
                    json=payload
                )

                if response.status_code == 200:
                    data = response.json()
                    text = (
                        data.get("candidates", [{}])[0]
                            .get("content", {})
                            .get("parts", [{}])[0]
                            .get("text", "")
                    )
                    nutrition = FoodAIService._parse_gemini_json(text)
                    if nutrition:
                        return {
                            "success":        True,
                            "foods":          [nutrition],
                            "total_calories": nutrition["calories"],
                            "total_protein":  nutrition["protein"],
                            "total_carbs":    nutrition["carbs"],
                            "total_fat":      nutrition["fat"],
                        }

                print(f"Gemini error: {response.status_code}")
                return FoodAIService._get_mock_nutrition(food_name)

        except Exception as e:
            print(f"Gemini exception: {e}")
            return FoodAIService._get_mock_nutrition(food_name)

    @staticmethod
    def _parse_gemini_json(text: str) -> Optional[Dict]:
        if not text:
            return None
        text = text.strip()
        text = re.sub(r'^```(?:json)?\s*', '', text)
        text = re.sub(r'\s*```$', '',       text)
        text = text.strip()

        try:
            data = json.loads(text)
            for field in ["calories", "protein", "carbs", "fat",
                          "fiber", "sugar", "sodium", "serving_qty"]:
                data[field] = float(data.get(field, 0))
            data["image_url"] = None
            return data
        except Exception as e:
            print(f"JSON parse error: {e} | text: {text}")
            return None

    # ================================================================
    # MOCK FALLBACKS
    # ================================================================

    @staticmethod
    def _get_mock_detection() -> Dict:
        return {
            "success":        True,
            "detected_foods": [
                {"name": "mixed food", "confidence": 85.0},
                {"name": "rice",       "confidence": 72.0},
                {"name": "curry",      "confidence": 65.0}
            ],
            "top_food":   "mixed food",
            "confidence": 85.0,
            "is_mock":    True
        }

    @staticmethod
    def _get_mock_nutrition(food_name: str) -> Dict:
        db = {
            "rice":          {"calories": 130, "protein": 2.7, "carbs": 28,  "fat": 0.3,  "fiber": 0.4},
            "roti":          {"calories": 71,  "protein": 2.7, "carbs": 15,  "fat": 0.4,  "fiber": 1.9},
            "dal":           {"calories": 198, "protein": 14,  "carbs": 34,  "fat": 0.8,  "fiber": 8},
            "chicken curry": {"calories": 243, "protein": 25,  "carbs": 8,   "fat": 12,   "fiber": 2},
            "biryani":       {"calories": 290, "protein": 12,  "carbs": 45,  "fat": 8,    "fiber": 2},
            "paneer":        {"calories": 265, "protein": 18,  "carbs": 4,   "fat": 20,   "fiber": 0},
            "samosa":        {"calories": 262, "protein": 4,   "carbs": 24,  "fat": 17,   "fiber": 2},
            "dosa":          {"calories": 168, "protein": 4,   "carbs": 29,  "fat": 4,    "fiber": 1},
            "idli":          {"calories": 39,  "protein": 2,   "carbs": 8,   "fat": 0.1,  "fiber": 0.4},
            "pizza":         {"calories": 266, "protein": 11,  "carbs": 33,  "fat": 10,   "fiber": 2},
            "burger":        {"calories": 295, "protein": 17,  "carbs": 24,  "fat": 14,   "fiber": 1},
            "salad":         {"calories": 65,  "protein": 3,   "carbs": 12,  "fat": 0.5,  "fiber": 4},
            "egg":           {"calories": 155, "protein": 13,  "carbs": 1,   "fat": 11,   "fiber": 0},
            "apple":         {"calories": 95,  "protein": 0.5, "carbs": 25,  "fat": 0.3,  "fiber": 4.4},
            "banana":        {"calories": 105, "protein": 1.3, "carbs": 27,  "fat": 0.4,  "fiber": 3.1},
            "milk":          {"calories": 149, "protein": 8,   "carbs": 12,  "fat": 8,    "fiber": 0},
            "mixed food":    {"calories": 250, "protein": 12,  "carbs": 35,  "fat": 8,    "fiber": 3},
        }

        food_lower = food_name.lower()
        nutrition  = None
        for key in db:
            if key in food_lower or food_lower in key:
                nutrition = db[key]
                break
        if not nutrition:
            nutrition = db["mixed food"]

        return {
            "success": True,
            "foods": [{
                "food_name":    food_name,
                "serving_size": "1 serving",
                "serving_qty":  1,
                "calories":     nutrition["calories"],
                "protein":      nutrition["protein"],
                "carbs":        nutrition["carbs"],
                "fat":          nutrition["fat"],
                "fiber":        nutrition["fiber"],
                "sugar":        2.0,
                "sodium":       500.0,
                "image_url":    None
            }],
            "total_calories": nutrition["calories"],
            "total_protein":  nutrition["protein"],
            "total_carbs":    nutrition["carbs"],
            "total_fat":      nutrition["fat"],
            "is_mock":        True
        }

    # ================================================================
    # CALCULATIONS (unchanged)
    # ================================================================

    @staticmethod
    def calculate_daily_targets(
        weight: float, height: float, age: int,
        gender: str, activity_level: str, goal_type: str
    ) -> Dict:
        if gender.lower() == "male":
            bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
        else:
            bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161

        multipliers = {
            "sedentary": 1.2, "light": 1.375, "moderate": 1.55,
            "active": 1.725, "very_active": 1.9
        }
        tdee = bmr * multipliers.get(activity_level, 1.55)

        adjustments = {
            "weight_loss":  {"calories": -500, "protein": 0.40, "carbs": 0.30, "fat": 0.30},
            "muscle_gain":  {"calories":  300, "protein": 0.30, "carbs": 0.50, "fat": 0.20},
            "maintenance":  {"calories":    0, "protein": 0.30, "carbs": 0.40, "fat": 0.30},
            "keto":         {"calories": -200, "protein": 0.25, "carbs": 0.05, "fat": 0.70},
            "high_protein": {"calories":    0, "protein": 0.45, "carbs": 0.35, "fat": 0.20},
        }
        adj = adjustments.get(goal_type, adjustments["maintenance"])
        cal = round(tdee + adj["calories"])

        return {
            "bmr":            round(bmr),
            "tdee":           round(tdee),
            "daily_calories": cal,
            "daily_protein":  round((cal * adj["protein"]) / 4),
            "daily_carbs":    round((cal * adj["carbs"])   / 4),
            "daily_fat":      round((cal * adj["fat"])     / 9),
            "daily_water":    round(weight * 0.033, 1)
        }

    @staticmethod
    def get_exercise_recommendations(
        excess_calories: float,
        fitness_level: str = "beginner"
    ) -> List[Dict]:
        if excess_calories <= 0:
            return [{
                "exercise_name": "Light Walk", "duration_minutes": 15,
                "calories_burn": 50, "intensity": "low",
                "description": "You're within your goal! A light walk aids digestion."
            }]

        exercises = {
            "beginner":     [
                {"name": "Walking",       "cal_per_min": 4,  "intensity": "low"},
                {"name": "Light Cycling", "cal_per_min": 5,  "intensity": "low"},
                {"name": "Yoga",          "cal_per_min": 3,  "intensity": "low"},
            ],
            "intermediate": [
                {"name": "Jogging",       "cal_per_min": 8,  "intensity": "moderate"},
                {"name": "Cycling",       "cal_per_min": 7,  "intensity": "moderate"},
                {"name": "Jump Rope",     "cal_per_min": 10, "intensity": "moderate"},
            ],
            "advanced":     [
                {"name": "Running",       "cal_per_min": 12, "intensity": "high"},
                {"name": "HIIT",          "cal_per_min": 14, "intensity": "high"},
                {"name": "Boxing",        "cal_per_min": 11, "intensity": "high"},
            ]
        }

        recs = []
        for ex in exercises.get(fitness_level, exercises["beginner"])[:3]:
            dur = min(60, round(excess_calories / ex["cal_per_min"]))
            recs.append({
                "exercise_name":    ex["name"],
                "duration_minutes": dur,
                "calories_burn":    round(dur * ex["cal_per_min"]),
                "intensity":        ex["intensity"],
                "description": (
                    f"{dur} mins of {ex['name'].lower()} burns "
                    f"~{round(dur * ex['cal_per_min'])} calories."
                )
            })
        return recs