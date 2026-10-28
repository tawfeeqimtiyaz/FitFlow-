from typing import Dict, List, Optional
import random
from app.config import settings

try:
    import google.generativeai as genai
except Exception:
    genai = None

# ── Configure Gemini ──────────────────────────────────────────────────────────
if genai is not None and settings.GEMINI_API_KEY:
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
    except Exception:
        genai = None


class AIService:
    """
    AI Service for FitFlow.
    - Food detection & workout recommendations (existing, unchanged)
    - Medical chatbot powered by Gemini 1.5 Flash
    """

    # ── Food Database (unchanged) ─────────────────────────────────────────────
    FOOD_DATABASE = {
        "pizza":    {"calories": 285, "protein": 12, "carbs": 36, "fat": 10},
        "burger":   {"calories": 354, "protein": 20, "carbs": 29, "fat": 17},
        "salad":    {"calories": 152, "protein": 5,  "carbs": 12, "fat": 9},
        "rice":     {"calories": 206, "protein": 4,  "carbs": 45, "fat": 0.4},
        "chicken":  {"calories": 239, "protein": 27, "carbs": 0,  "fat": 14},
        "pasta":    {"calories": 288, "protein": 10, "carbs": 56, "fat": 2},
        "sandwich": {"calories": 252, "protein": 10, "carbs": 32, "fat": 9},
        "soup":     {"calories": 150, "protein": 8,  "carbs": 18, "fat": 5},
        "fruit":    {"calories": 95,  "protein": 1,  "carbs": 25, "fat": 0.3},
        "egg":      {"calories": 155, "protein": 13, "carbs": 1,  "fat": 11},
    }

    # ── Gemini System Prompt ──────────────────────────────────────────────────
    MEDICAL_SYSTEM_PROMPT = """
You are a FitFlow Medical Assistant — a friendly, knowledgeable AI health companion 
integrated into a fitness app. Your role is to:

1. Listen to users describe their workout-related symptoms (joint pain, muscle soreness, 
   dizziness, chest tightness, etc.)
2. Suggest which type of doctor they should consult (e.g. Orthopedic, Physiotherapist, 
   Cardiologist, General Physician, Podiatrist)
3. After the user confirms their diagnosis from a doctor, provide:
   - Exercises to AVOID with their condition
   - RECOMMENDED safe exercises
   - Recovery and lifestyle TIPS

IMPORTANT RULES:
- Always add a disclaimer that you are NOT a substitute for professional medical advice
- Be empathetic and supportive
- Keep responses concise and structured
- For HIGH urgency symptoms (chest pain, palpitations, severe dizziness) — 
  strongly urge immediate medical attention
- Always end symptom analysis by asking if they've confirmed with a doctor
- Format responses clearly with emojis for readability
- When giving exercise tips, use clear sections: 
  ❌ Avoid, ✅ Recommended, 💡 Tips

You are part of a fitness app so always tie advice back to safe fitness practices.
"""

    # ── Gemini Medical Chat ───────────────────────────────────────────────────
    @staticmethod
    async def medical_chat(
        message: str,
        context: Optional[str] = None,
        chat_history: Optional[List[Dict]] = None
    ) -> Dict:
        """
        Gemini-powered medical chatbot.
        Falls back to keyword-based logic if Gemini API key is not set.
        """

        if not settings.GEMINI_API_KEY or genai is None:
            # Fallback to keyword logic if no API key or Gemini runtime is unavailable
            return AIService._keyword_chat(message, context)

        try:
            model = genai.GenerativeModel(
                model_name="gemini-1.5-flash",
                system_instruction=AIService.MEDICAL_SYSTEM_PROMPT
            )

            # Build conversation history for context
            history = []
            if chat_history:
                for msg in chat_history:
                    history.append({
                        "role": msg["role"],
                        "parts": [msg["text"]]
                    })

            chat = model.start_chat(history=history)

            # Build context-aware prompt
            if context == "diagnosis":
                prompt = (
                    f"The user has confirmed their diagnosis: '{message}'. "
                    "Now provide specific exercise recommendations including: "
                    "1) Exercises to avoid, 2) Safe recommended exercises, "
                    "3) Recovery tips. Be specific and practical."
                )
            elif context == "symptom":
                prompt = (
                    f"The user is describing their symptoms: '{message}'. "
                    "Analyze and suggest which doctor specialist they should see, "
                    "explain why, and mention the urgency level (low/medium/high). "
                    "Ask them to confirm with a doctor before you give exercise advice."
                )
            else:
                prompt = message

            response = await chat.send_message_async(prompt)
            reply_text = response.text

            # Detect if response contains exercise tips (post-diagnosis)
            exercise_tips = None
            suggestions = None

            if context == "diagnosis" or any(
                word in reply_text.lower()
                for word in ["avoid", "recommended", "recovery tip", "safe exercise"]
            ):
                exercise_tips = AIService._extract_exercise_tips(reply_text)

            if context == "symptom" or any(
                word in reply_text.lower()
                for word in ["orthopedic", "cardiologist", "physiotherapist",
                             "general physician", "podiatrist", "specialist"]
            ):
                suggestions = AIService._extract_suggestions(reply_text)

            # Determine next context
            next_context = "diagnosis" if suggestions else ("tips" if exercise_tips else context)

            return {
                "reply": reply_text,
                "suggestions": suggestions,
                "exercise_tips": exercise_tips,
                "context": next_context
            }

        except Exception as e:
            print(f"Gemini API error: {e}")
            # Fallback to keyword logic on error
            return AIService._keyword_chat(message, context)

    # ── Extract structured data from Gemini response ──────────────────────────
    @staticmethod
    def _extract_suggestions(text: str) -> Optional[List[Dict]]:
        """Try to extract doctor suggestions from Gemini's response text"""
        suggestions = []
        text_lower = text.lower()

        doctor_map = [
            ("orthopedic",      "Orthopedic Specialist",  "medium"),
            ("physiotherapist", "Physiotherapist",         "low"),
            ("cardiologist",    "Cardiologist",            "high"),
            ("podiatrist",      "Podiatrist",              "low"),
            ("neurologist",     "Neurologist",             "medium"),
            ("general physician","General Physician",      "low"),
            ("general practitioner","General Physician",   "low"),
        ]

        for keyword, doctor_type, default_urgency in doctor_map:
            if keyword in text_lower:
                # Try to detect urgency from text
                urgency = default_urgency
                if any(w in text_lower for w in ["urgent", "immediately", "emergency", "high urgency"]):
                    urgency = "high"
                elif any(w in text_lower for w in ["soon", "medium", "moderate"]):
                    urgency = "medium"

                suggestions.append({
                    "doctor_type": doctor_type,
                    "reason": f"Based on your symptoms, consulting a {doctor_type} is recommended.",
                    "urgency": urgency
                })
                break  # One suggestion at a time is cleaner UX

        return suggestions if suggestions else None

    @staticmethod
    def _extract_exercise_tips(text: str) -> Optional[Dict]:
        """
        Return exercise tips dict.
        Since Gemini formats nicely, we just pass the full text
        and let the frontend render it — but we also try to parse sections.
        """
        avoid = []
        recommended = []
        tips = []

        lines = text.split('\n')
        current_section = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            line_lower = line.lower()

            if any(w in line_lower for w in ['avoid', '❌', 'do not', "don't"]):
                current_section = 'avoid'
            elif any(w in line_lower for w in ['recommended', '✅', 'safe', 'can do']):
                current_section = 'recommended'
            elif any(w in line_lower for w in ['tip', '💡', 'recovery', 'advice']):
                current_section = 'tips'
            elif line.startswith(('-', '•', '*', '1', '2', '3', '4', '5')):
                clean = line.lstrip('-•*0123456789.) ').strip()
                if clean and current_section == 'avoid':
                    avoid.append(clean)
                elif clean and current_section == 'recommended':
                    recommended.append(clean)
                elif clean and current_section == 'tips':
                    tips.append(clean)

        # If parsing failed, return generic structure with full text
        if not avoid and not recommended:
            return {
                "avoid": ["High-impact exercises until cleared by doctor"],
                "recommended": ["Light stretching", "Walking", "Swimming"],
                "tips": ["Always consult your doctor before resuming intense exercise",
                         "Listen to your body and stop if pain occurs"]
            }

        return {
            "avoid": avoid if avoid else ["High-impact activities"],
            "recommended": recommended if recommended else ["Light exercise as tolerated"],
            "tips": tips if tips else ["Consult your doctor regularly"]
        }

    # ── Keyword Fallback (when no Gemini key) ─────────────────────────────────
    SYMPTOM_MAP = [
        {
            "keywords": ["joint", "knee", "ankle", "bone", "fracture",
                         "wrist", "elbow", "hip", "shoulder"],
            "doctor_type": "Orthopedic Specialist",
            "reason": "Joint or bone-related symptoms detected",
            "urgency": "medium",
            "avoid": ["High-impact exercises", "Running", "Jumping",
                      "Heavy weight lifting", "Squats with weight"],
            "recommended": ["Swimming", "Cycling (low resistance)",
                            "Upper body light stretching", "Chair yoga",
                            "Walking in pool"],
            "tips": ["Apply ice pack for 15 mins after activity",
                     "Keep the joint elevated when resting",
                     "Use compression bandage if swollen",
                     "Consult before resuming heavy training"]
        },
        {
            "keywords": ["muscle", "strain", "sprain", "cramp", "pull",
                         "sore", "stiff", "neck", "back pain", "lower back"],
            "doctor_type": "Physiotherapist",
            "reason": "Muscle or soft tissue issue detected",
            "urgency": "low",
            "avoid": ["Heavy deadlifts", "Intense HIIT",
                      "Any exercise causing sharp pain",
                      "Sit-ups if lower back pain"],
            "recommended": ["Gentle stretching", "Foam rolling",
                            "Light walking", "Heat therapy exercises",
                            "Yoga (beginner)"],
            "tips": ["Warm up properly before any activity",
                     "Use heat pack for chronic muscle pain",
                     "Rest the affected muscle group 48 hours",
                     "Stay hydrated to reduce cramps"]
        },
        {
            "keywords": ["breath", "chest", "heart", "palpitation",
                         "shortness", "tightness"],
            "doctor_type": "Cardiologist",
            "reason": "Cardiovascular symptoms detected — please seek care soon",
            "urgency": "high",
            "avoid": ["ALL intense cardio", "Heavy lifting",
                      "High-intensity interval training", "Exercise in heat"],
            "recommended": ["Very light walking only", "Breathing exercises",
                            "Seated stretches",
                            "Rest until cleared by doctor"],
            "tips": ["Stop exercise immediately if chest pain occurs",
                     "Monitor resting heart rate daily",
                     "Avoid caffeine before workouts",
                     "URGENT: See a doctor before resuming exercise"]
        },
        {
            "keywords": ["dizzy", "headache", "fatigue", "weak",
                         "tired", "exhausted", "faint", "nausea"],
            "doctor_type": "General Physician",
            "reason": "Could be dehydration, overtraining or nutritional deficiency",
            "urgency": "low",
            "avoid": ["Overtraining", "Skipping meals before workout",
                      "Training in heat", "Intense cardio"],
            "recommended": ["Light yoga", "Walking", "Adequate sleep",
                            "Rest day", "Hydration focused recovery"],
            "tips": ["Drink at least 2.5L water daily",
                     "Eat a balanced meal 1-2 hours before exercise",
                     "Take rest days seriously",
                     "Check iron and vitamin D levels"]
        },
        {
            "keywords": ["shin", "calf", "foot", "heel",
                         "plantar", "arch"],
            "doctor_type": "Podiatrist",
            "reason": "Lower leg or foot related symptoms detected",
            "urgency": "low",
            "avoid": ["Running on hard surfaces", "High impact jumping",
                      "Barefoot running", "Steep inclines"],
            "recommended": ["Swimming", "Cycling", "Calf stretches",
                            "Foot strengthening exercises"],
            "tips": ["Replace running shoes every 500km",
                     "Stretch calves daily",
                     "Avoid running downhill",
                     "Rest 2-3 days and ice the area"]
        },
    ]

    @staticmethod
    def _keyword_chat(message: str, context: Optional[str] = None) -> Dict:
        """Fallback keyword-based chat when Gemini is unavailable"""
        msg = message.lower().strip()

        greetings = ["hi", "hello", "hey", "good morning", "good evening"]
        if any(g in msg for g in greetings) and not context:
            return {
                "reply": (
                    "👋 Hello! I'm your FitFlow Medical Assistant.\n\n"
                    "Tell me about any symptoms you're experiencing during "
                    "or after your workout and I'll help guide you! 🩺"
                ),
                "suggestions": None,
                "exercise_tips": None,
                "context": "symptom"
            }

        if context == "diagnosis":
            return AIService._get_exercise_tips_keyword(msg)

        matched = None
        for entry in AIService.SYMPTOM_MAP:
            if any(kw in msg for kw in entry["keywords"]):
                matched = entry
                break

        if matched:
            urgency_emoji = {
                "high": "🚨", "medium": "⚠️", "low": "ℹ️"
            }.get(matched["urgency"], "ℹ️")

            return {
                "reply": (
                    f"I understand you're experiencing these symptoms.\n\n"
                    f"{urgency_emoji} I recommend consulting a "
                    f"**{matched['doctor_type']}**.\n\n"
                    f"📋 Reason: {matched['reason']}\n\n"
                    "⚕️ This is not a medical diagnosis. Always consult a "
                    "qualified doctor.\n\n"
                    "Once you've confirmed your diagnosis, type it here "
                    "and I'll give you exercise recommendations! 💪"
                ),
                "suggestions": [{
                    "doctor_type": matched["doctor_type"],
                    "reason": matched["reason"],
                    "urgency": matched["urgency"]
                }],
                "exercise_tips": None,
                "context": "diagnosis"
            }

        return {
            "reply": (
                "Could you describe your symptoms in more detail?\n\n"
                "For example:\n"
                "• 'I have knee pain during running'\n"
                "• 'My lower back hurts after lifting'\n"
                "• 'I feel dizzy during workouts'\n\n"
                "The more detail you give, the better I can help! 🩺"
            ),
            "suggestions": None,
            "exercise_tips": None,
            "context": "symptom"
        }

    @staticmethod
    def _get_exercise_tips_keyword(diagnosis: str) -> Dict:
        matched = None
        for entry in AIService.SYMPTOM_MAP:
            if any(kw in diagnosis for kw in entry["keywords"]):
                matched = entry
                break

        if not matched:
            matched = {
                "avoid": ["High-impact activities", "Overtraining",
                          "Exercising through sharp pain"],
                "recommended": ["Light walking", "Gentle stretching",
                                "Swimming", "Yoga"],
                "tips": ["Listen to your body", "Rest when needed",
                         "Stay hydrated",
                         "Consult your doctor regularly"]
            }

        return {
            "reply": "Here are your personalized exercise recommendations! 🏋️",
            "suggestions": None,
            "exercise_tips": {
                "avoid":       matched["avoid"],
                "recommended": matched["recommended"],
                "tips":        matched["tips"]
            },
            "context": "tips"
        }

    # ── Existing methods (unchanged) ──────────────────────────────────────────
    @staticmethod
    async def detect_food_from_image(image_url: str) -> Dict:
        foods = list(AIService.FOOD_DATABASE.keys())
        detected_food = random.choice(foods)
        nutrition = AIService.FOOD_DATABASE[detected_food]
        return {
            "detected_food": detected_food,
            "calories":      nutrition["calories"],
            "protein":       nutrition["protein"],
            "carbs":         nutrition["carbs"],
            "fat":           nutrition["fat"],
            "confidence":    round(random.uniform(0.75, 0.98), 2)
        }

    @staticmethod
    def get_workout_recommendation(
        calories: float, user_weight: float = 70
    ) -> List[Dict]:
        calories_to_burn = calories * 0.3
        exercises = [
            {"name": "Push Ups",      "calories_per_min": 7},
            {"name": "Jumping Jacks", "calories_per_min": 10},
            {"name": "Running",       "calories_per_min": 12},
            {"name": "Squats",        "calories_per_min": 8},
            {"name": "Plank",         "calories_per_min": 5},
        ]
        recommendations = []
        for exercise in exercises[:3]:
            duration = int(calories_to_burn / exercise["calories_per_min"])
            recommendations.append({
                "exercise_name":    exercise["name"],
                "duration_minutes": duration,
                "calories_to_burn": round(calories_to_burn, 1),
                "reason": f"Burns ~{exercise['calories_per_min']} calories/minute"
            })
        return recommendations

    @staticmethod
    def analyze_symptoms(
        description: str, body_part: str = None
    ) -> List[Dict]:
        """Legacy method — kept for backward compatibility"""
        suggestions = []
        desc = description.lower() if description else ""

        for entry in AIService.SYMPTOM_MAP:
            if any(kw in desc for kw in entry["keywords"]):
                suggestions.append({
                    "doctor_type": entry["doctor_type"],
                    "reason":      entry["reason"],
                    "urgency":     entry["urgency"]
                })

        if not suggestions:
            suggestions.append({
                "doctor_type": "General Physician",
                "reason":      "General checkup recommended",
                "urgency":     "low"
            })
        return suggestions