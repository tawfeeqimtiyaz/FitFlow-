<div align="center">

# FitFlow AI

**An AI-powered, all-in-one fitness and wellness platform: guided workouts, AI meal-photo calorie analysis, post-meal "burn it off" decisions, a symptom-aware medical assistant, and mindfulness, in one app.**

![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.135-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0_async-D71F00)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-asyncpg-4169E1?logo=postgresql&logoColor=white)
![Gemini](https://img.shields.io/badge/Google-Gemini-8E75B2?logo=googlegemini&logoColor=white)
![Clarifai](https://img.shields.io/badge/Clarifai-Food_Recognition-FF6B00)

</div>

---

## Table of Contents

1. [Overview](#1-overview)
2. [Feature Modules](#2-feature-modules)
3. [System Architecture](#3-system-architecture)
4. [How the AI Works](#4-how-the-ai-works)
5. [Data Model](#5-data-model)
6. [API Reference](#6-api-reference)
7. [Project Structure](#7-project-structure)
8. [Local Development](#8-local-development)
9. [Configuration](#9-configuration)
10. [Security & Compliance](#10-security--compliance)
11. [Known Limitations & Roadmap](#11-known-limitations--roadmap)
12. [Disclaimer](#12-disclaimer)

---

## 1. Overview

FitFlow AI covers the whole daily health loop in one place:

```
 Train  ──►  Eat  ──►  Analyse  ──►  Decide  ──►  Recover
   │          │           │             │            │
Workouts   Snap a     Clarifai +     Calorie       Medical AI +
by level   meal photo  Gemini macros  balance →     mindfulness
                                      exercise plan
```

| Layer | Technology |
|---|---|
| Frontend | React 19 (Create React App), React Router 7, Axios, CSS variables (light/dark themes) |
| Backend | FastAPI (async), Pydantic v2, SQLAlchemy 2.0 async ORM, Uvicorn |
| Database | PostgreSQL via `asyncpg` (production) · SQLite via `aiosqlite` (local dev) |
| Auth | OAuth2 password flow, JWT (HS256, `python-jose`), bcrypt (`passlib`) |
| AI: vision | Clarifai `food-item-recognition` model (top-5 food concepts with confidence) |
| AI: language | Google Gemini for nutrition estimation (structured JSON) and the medical chat assistant |
| Resilience | Every AI integration has a deterministic offline fallback, so the app keeps working without API keys |

---

## 2. Feature Modules

### Workouts
- Three difficulty tracks (**Beginner**, **Intermediate**, **Advanced**) with 6 exercises each across Chest, Legs, Core and Cardio.
- A live session timer (`useTimer` hook), animated exercise visualisation (`WorkoutAnimation`), per-session completion tracking and a completion screen.
- Backend session tracking: `start → end` lifecycle, with calories burned computed from duration × the exercise's `calories_burn_per_minute`.

### AI Calorie Analyser
- **Scan tab**: capture a meal with the device camera (`getUserMedia`, front/back camera toggle, canvas frame capture) or upload a photo.
- **One-shot pipeline** (`POST /api/calorie/quick-analyze`): image → food recognition → nutrition breakdown (calories, protein, carbs, fat, fiber, sugar, sodium).
- **Manual tab**: type any food ("2 idli with sambar") and get AI nutrition data.
- **Meal log**: tag meals as breakfast, lunch, dinner or snack, set a quantity multiplier, and delete entries; daily totals recompute automatically.
- **Progress tab**: calories and macros remaining against goal, percentage progress, and water tracking (ml in, litres in totals).
- **Goals tab**: weight loss, muscle gain, maintenance, keto or high-protein × five activity levels. Targets are calculated with Mifflin-St Jeor + TDEE.

### Post-Meal Decision Engine
- `GET /api/calorie/balance` compares today's intake with the target and decides:
  - **Over target** → a personalised exercise plan scaled to the user's fitness level, sized to burn the surplus.
  - **More than 500 kcal under** → a nudge to eat enough.
  - **Otherwise** → "on track", with a light digestion walk.

### Medical Tracking
- **AI Medical Assistant**: a context-aware chat that runs a three-stage clinical-style flow, *symptoms → doctor referral → post-diagnosis exercise guidance* (see [§4.4](#44-medical-assistant-state-machine)).
- Structured output: doctor specialty plus urgency (low/medium/high), and exercise tips split into ❌ Avoid / ✅ Recommended / 💡 Tips.
- **Medication Tracker**: name, dosage, frequency, dates, prescriber, purpose, side effects, and an active/inactive filter.
- Backend records for **symptoms** (1–10 severity), **doctor visits** (diagnosis, prescription, follow-up), **medications** and **medication reminders**.

### Mindfulness
- **Meditation timer** with ambient soundscapes (rain, forest, ocean, fireplace, wind, silence) and volume control.
- **Guided breathing**: Relaxing (4-7-8), Energizing, Calming and Box Breathing, with animated phase guidance and cycle counting.
- **Quotes**: categorised motivational quotes with favourites and sharing.
- Backend session logging and stats (total sessions, minutes, meditation vs. mini-game split).

### Platform
- JWT-protected routes (`ProtectedRoute`), with auto-logout and redirect on `401` through an Axios interceptor.
- Light/dark theme that follows the OS preference and remembers the user's choice.
- Responsive navbar with a mobile menu.
- Interactive API docs at `/docs` (Swagger) and `/redoc`.

---

## 3. System Architecture

```mermaid
flowchart LR
    subgraph Client["Browser (React SPA)"]
        UI[Pages & Components]
        CTX[AuthContext / ThemeContext]
        AX[Axios client<br/>JWT interceptor]
        UI --> CTX --> AX
    end

    subgraph API["FastAPI service"]
        R[Routers<br/>auth · users · workouts · calorie<br/>nutrition · medical · mindfulness]
        DEP[get_current_user<br/>JWT → User]
        S[Services<br/>AuthService · CalorieService<br/>FoodAIService · AIService<br/>WorkoutService · UserService]
        R --> DEP
        R --> S
    end

    DB[(PostgreSQL / SQLite<br/>SQLAlchemy async)]
    CL[[Clarifai<br/>food-item-recognition]]
    GM[[Google Gemini]]

    AX -- "HTTPS JSON / multipart<br/>Bearer token" --> R
    S --> DB
    S -- "base64 image" --> CL
    S -- "nutrition prompt / chat" --> GM
```

**Request lifecycle**

1. The SPA calls `REACT_APP_API_URL` (default `http://localhost:8000/api`). The Axios request interceptor attaches `Authorization: Bearer <jwt>` from `localStorage`.
2. FastAPI's `CORSMiddleware` allows `localhost:3000` and `FRONTEND_URL`.
3. Protected routes resolve `get_current_user`: decode the JWT, convert `sub` to a UUID, load the `User`, and reject inactive users.
4. Routers delegate to stateless service classes, which use an `AsyncSession` from `get_db()`.
5. On startup, the `lifespan` hook runs `Base.metadata.create_all`. On shutdown, it disposes of the connection pool.

---

## 4. How the AI Works

### 4.1 Meal photo → nutrition pipeline

```mermaid
sequenceDiagram
    participant U as User (Calories page)
    participant API as FastAPI /api/calorie/quick-analyze
    participant CL as Clarifai
    participant GM as Gemini
    U->>API: multipart image (camera capture or upload)
    API->>API: validate image/* → base64 encode
    API->>CL: food-item-recognition (base64)
    CL-->>API: concepts[] (name, value)
    API->>API: top-5 foods, confidence % → pick top_food
    API->>GM: "Return ONLY JSON nutrition for {top_food}" (temperature 0.1)
    GM-->>API: JSON (calories, protein, carbs, fat, fiber, sugar, sodium)
    API->>API: strip ``` fences → json.loads → coerce floats
    API-->>U: detected_food, confidence, all_detected, nutrition, totals
    U->>API: POST /meals (macros × quantity)
    API->>API: recompute DailyIntake for that date
```

Design choices:
- **Low temperature (0.1)** and a JSON-only prompt with an explicit schema example keep the output deterministic and parseable.
- **Defensive parsing**: markdown fences are stripped, every numeric field is coerced to `float`, and a parse failure falls back to the offline nutrition table.
- **Aggregation by recomputation**: after every meal insert or delete, `DailyIntake` is rebuilt from that day's `MealLog` rows instead of being incremented, which keeps totals self-healing.

### 4.2 Goal engine (personalised targets)

`FoodAIService.calculate_daily_targets`:

| Step | Formula |
|---|---|
| BMR (Mifflin-St Jeor) | `10·kg + 6.25·cm − 5·age + 5` (male) / `− 161` (female) |
| TDEE | `BMR × {sedentary 1.2, light 1.375, moderate 1.55, active 1.725, very_active 1.9}` |
| Calorie target | `TDEE + {weight_loss −500, muscle_gain +300, maintenance 0, keto −200, high_protein 0}` |
| Macros | protein / carbs at 4 kcal/g, fat at 9 kcal/g, using goal-specific splits (e.g. keto 25/5/70) |
| Water | `0.033 L × body weight (kg)` |

If the profile is missing weight, height or age, sensible defaults apply (2000 kcal, 150 g P, 200 g C, 65 g F, 2.5 L).

### 4.3 Post-meal decision engine

```
excess = consumed_today − daily_target

excess > 0      → pick 3 exercises for the user's fitness level
                  duration = min(60, excess / kcal_per_min)
                  beginner:     Walking 4 · Light Cycling 5 · Yoga 3      kcal/min
                  intermediate: Jogging 8 · Cycling 7 · Jump Rope 10
                  advanced:     Running 12 · HIIT 14 · Boxing 11
excess < −500   → "You have N calories remaining. Make sure to eat enough!"
otherwise       → "You're on track!" + 15-min light walk
```

Workout sessions close the loop: `calories_burned = (duration_seconds / 60) × exercise.calories_burn_per_minute`.

### 4.4 Medical assistant state machine

```mermaid
stateDiagram-v2
    [*] --> greeting
    greeting --> symptom: user greets
    symptom --> diagnosis: specialist detected in reply
    diagnosis --> tips: user reports confirmed diagnosis
    tips --> [*]
```

- **Gemini mode**: a system prompt casts the model as a fitness-aware medical assistant. It requires a "not a substitute for professional advice" disclaimer, escalates urgency for chest pain, palpitations and severe dizziness, and asks for a structured ❌/✅/💡 format. The last 10 chat turns are replayed as history for conversational memory.
- **Context-specific prompting**: `context="symptom"` asks for a specialist plus an urgency level. `context="diagnosis"` asks for exercises to avoid, safe exercises and recovery tips.
- **Post-processing**: free text is mined into structured `suggestions` (Orthopedic, Physiotherapist, Cardiologist, Podiatrist, Neurologist, General Physician, each with urgency) and `exercise_tips` (avoid / recommended / tips) for rich UI cards. The API returns the next `context`, so the frontend drives the state machine.
- **Keyword fallback**: if Gemini is unavailable, a rule engine maps symptom keywords to five specialties (joint/bone, muscle/soft-tissue, cardiovascular, systemic fatigue/dizziness, foot/lower-leg), each with curated avoid/recommend/tip lists.

### 4.5 Graceful degradation

| Missing dependency | Behaviour |
|---|---|
| `CLARIFAI_PAT` unset, or Clarifai error | Mock detection (`mixed food`, `rice`, `curry`), flagged `is_mock: true` |
| `GEMINI_API_KEY` unset, or Gemini error | Offline nutrition table (rice, roti, dal, biryani, paneer, dosa, idli, pizza, burger, fruit and more), flagged `is_mock: true` |
| Gemini unavailable for chat | Keyword-based medical assistant |
| `DEBUG=True` with a Supabase `DATABASE_URL` | Automatically swaps to local SQLite (`backend/fitflow.db`) |

---

## 5. Data Model

```mermaid
erDiagram
    USERS ||--o| USER_PROFILES : has
    USERS ||--o| USER_GOALS : sets
    USERS ||--o{ MEAL_LOGS : logs
    USERS ||--o{ DAILY_INTAKES : aggregates
    USERS ||--o{ WATER_LOGS : logs
    USERS ||--o{ FOOD_LOGS : logs
    USERS ||--o{ WORKOUT_SESSIONS : performs
    USERS ||--o{ MEDITATION_SESSIONS : completes
    USERS ||--o{ SYMPTOMS : reports
    USERS ||--o{ DOCTOR_VISITS : records
    USERS ||--o{ MEDICATIONS : takes
    USERS ||--o{ MEDICATION_REMINDERS : schedules
    MEDICATIONS ||--o{ MEDICATION_REMINDERS : triggers
    EXERCISE_CATEGORIES ||--o{ EXERCISES : groups
    EXERCISES ||--o{ WORKOUT_SESSIONS : "used in"

    USERS { uuid id PK; string email UK; string username UK; string hashed_password; bool is_active }
    USER_PROFILES { uuid id PK; uuid user_id FK; int age; string gender; float height_cm; float weight_kg; string fitness_goal; string activity_level }
    USER_GOALS { uuid id PK; uuid user_id FK; string goal_type; string activity_level; int daily_calories; int daily_protein; int daily_carbs; int daily_fat; float daily_water }
    MEAL_LOGS { uuid id PK; uuid user_id FK; string meal_type; string food_name; float quantity; float calories; float protein; float carbs; float fat; string ai_detected; float confidence; date meal_date }
    DAILY_INTAKES { uuid id PK; uuid user_id FK; date intake_date; float total_calories; float water_intake; int meals_count }
    WORKOUT_SESSIONS { uuid id PK; uuid user_id FK; uuid exercise_id FK; int duration_seconds; int calories_burned; bool completed }
    MEDICATIONS { int id PK; int user_id FK; string name; string dosage; string frequency; bool is_active }
```

---

## 6. API Reference

Base URL: `http://localhost:8000`. Full interactive docs are at **`/docs`**. 🔒 marks endpoints that need `Authorization: Bearer <token>`.

<details>
<summary><b>Health & Auth</b></summary>

| Method | Path | Description |
|---|---|---|
| GET | `/` | Service banner |
| GET | `/health` | Health probe (use this for load-balancer checks) |
| POST | `/api/auth/signup` | Register with `{email, password}`. Also creates an empty profile and a unique username |
| POST | `/api/auth/login` | OAuth2 form login (`username`=email, `password`) → `{access_token}` |
| POST | `/api/auth/login/json` | JSON login `{email, password}` → `{access_token}` |
</details>

<details>
<summary><b>Users</b> 🔒</summary>

| Method | Path | Description |
|---|---|---|
| GET | `/api/users/me` | Current user |
| GET / POST / PUT | `/api/users/me/profile` | Read / create / update profile |
</details>

<details>
<summary><b>Calorie & Nutrition</b> 🔒</summary>

| Method | Path | Description |
|---|---|---|
| GET / POST / PUT | `/api/calorie/goals` | Get (auto-creates defaults) / calculate / override goals |
| POST | `/api/calorie/detect-food` | Detect food from `{image_base64}` |
| POST | `/api/calorie/detect-food/upload` | Detect food from a multipart image |
| POST | `/api/calorie/quick-analyze` | **Image → detection → nutrition in one call** |
| POST | `/api/calorie/nutrition` | Nutrition for `{food_name, serving_size?}` |
| GET | `/api/calorie/nutrition/search?query=` | Nutrition search |
| POST / GET | `/api/calorie/meals` | Log a meal / list meals (`?meal_date=YYYY-MM-DD`) |
| DELETE | `/api/calorie/meals/{meal_id}` | Delete a meal (totals recompute) |
| GET | `/api/calorie/daily-intake` | Daily totals (`?intake_date=`) |
| GET | `/api/calorie/progress` | Goal vs. intake, remaining macros, % progress |
| POST | `/api/calorie/water` | Log water `{amount}` in ml |
| GET | `/api/calorie/balance` | **Post-meal decision**: surplus and an exercise plan |
| POST | `/api/nutrition/detect`, `/log`, `/recommendations` · GET `/history` | Legacy nutrition endpoints |
</details>

<details>
<summary><b>Workouts</b></summary>

| Method | Path | Description |
|---|---|---|
| GET | `/api/workouts/categories` | Exercise categories |
| GET | `/api/workouts/categories/{id}/exercises?difficulty=` | Exercises in a category |
| GET | `/api/workouts/difficulty/{beginner\|intermediate\|advanced}` | Exercises by level |
| POST 🔒 | `/api/workouts/sessions/start` | Start a session `{exercise_id}` |
| POST 🔒 | `/api/workouts/sessions/{id}/end` | End a session `{duration_seconds, completed}` → calories burned |
| GET 🔒 | `/api/workouts/history?limit=20` | Session history |
</details>

<details>
<summary><b>Medical</b> 🔒</summary>

| Method | Path | Description |
|---|---|---|
| POST | `/api/medical/chat` | `{message, context?, history?}` → `{reply, suggestions, exercise_tips, context}` |
| POST / GET | `/api/medical/symptoms` | Report / list symptoms |
| POST / GET | `/api/medical/doctor-visits` | Log / list doctor visits |
| POST / GET | `/api/medical/medications` | Add / list (`?active_only=true`) |
| PUT / DELETE | `/api/medical/medications/{id}` | Update / delete a medication |
| POST / GET | `/api/medical/reminders` | Add / list reminders |
| DELETE | `/api/medical/reminders/{id}` | Delete a reminder |
</details>

<details>
<summary><b>Mindfulness</b> 🔒</summary>

| Method | Path | Description |
|---|---|---|
| POST | `/api/mindfulness/sessions/start` | Start a session `{session_type: meditation\|minigame}` |
| POST | `/api/mindfulness/sessions/{id}/end` | End a session `{duration_seconds, completed}` |
| GET | `/api/mindfulness/sessions?limit=20` | Session history |
| GET | `/api/mindfulness/stats` | Totals and breakdown |
</details>

**Example: analyse a meal photo**

```bash
TOKEN=$(curl -s -X POST localhost:8000/api/auth/login \
  -d "username=me@example.com&password=secret" | jq -r .access_token)

curl -X POST localhost:8000/api/calorie/quick-analyze \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@lunch.jpg"
```

---

## 7. Project Structure

```
FitFlow-Ai/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, lifespan, CORS, router registration
│   │   ├── config.py            # Pydantic Settings (reads backend/.env)
│   │   ├── database.py          # Async engine, session factory, SQLite dev fallback
│   │   ├── models/              # SQLAlchemy ORM: user, calorie, exercise, workout,
│   │   │                        #   nutrition, medical, mindfulness
│   │   ├── schemas/             # Pydantic request/response contracts
│   │   ├── routers/             # HTTP layer, one module per domain
│   │   ├── services/
│   │   │   ├── auth_service.py      # signup, login, JWT issue
│   │   │   ├── calorie_service.py   # goals, meals, daily aggregation, balance
│   │   │   ├── food_ai_service.py   # Clarifai vision, Gemini nutrition, BMR/TDEE
│   │   │   ├── ai_service.py        # Gemini medical chat + keyword fallback
│   │   │   ├── workout_service.py   # sessions & calorie burn
│   │   │   └── user_service.py      # profile CRUD
│   │   └── utils/               # bcrypt/JWT helpers, get_current_user dependency
│   └── requirements.txt
└── frontend/
    ├── public/
    └── src/
        ├── App.js               # Router + ProtectedRoute
        ├── context/             # AuthContext, ThemeContext
        ├── hooks/useTimer.js
        ├── services/            # Axios client + per-domain API wrappers
        ├── pages/               # Home, Login, Signup, Dashboard, Workouts,
        │                        #   Calories, Medical, Mindfulness
        ├── components/          # common/, workout/, medical/, mindfulness/
        └── styles/              # design tokens (variables.css), global styles
```

---

## 8. Local Development

### Prerequisites
- Python **3.11+**
- Node.js **18+** and npm
- (Optional) PostgreSQL 14+. SQLite works out of the box.
- (Optional) A [Google AI Studio](https://aistudio.google.com/) API key and a [Clarifai](https://clarifai.com/) Personal Access Token

### Backend

```bash
cd backend
python -m venv venv
# Windows: venv\Scripts\activate    macOS/Linux: source venv/bin/activate
pip install -r requirements.txt

# Create backend/.env (see §9). Minimal local setup:
#   DATABASE_URL=sqlite+aiosqlite:///./fitflow.db
#   SECRET_KEY=<output of: python -c "import secrets; print(secrets.token_urlsafe(64))">

uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000/docs. Tables are created automatically on first start.

### Frontend

```bash
cd frontend
npm install
echo "REACT_APP_API_URL=http://localhost:8000/api" > .env
npm start            # http://localhost:3000
```

### Build

```bash
cd frontend && npm run build   # static bundle in frontend/build/
cd frontend && npm test        # Jest + React Testing Library
```

---

## 9. Configuration

### Backend (`backend/.env`)

| Variable | Required | Default | Description |
|---|---|---|---|
| `APP_NAME` | | `FitFlow` | Shown in API banner and docs |
| `DEBUG` | | `True` | Enables SQL echo and the SQLite fallback. **Set `False` in production.** |
| `DATABASE_URL` | ✅ | | `postgresql+asyncpg://user:pass@host:5432/fitflow` or `sqlite+aiosqlite:///./fitflow.db` |
| `SECRET_KEY` | ✅ | | JWT signing key (64+ random chars) |
| `ALGORITHM` | | `HS256` | JWT algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | | `30` | Token lifetime |
| `GEMINI_API_KEY` | | | Enables AI nutrition and the AI medical chat |
| `CLARIFAI_PAT` | | | Enables real food-image recognition |
| `FRONTEND_URL` | | `http://localhost:3000` | Added to the CORS allow-list. Set it to your production domain. |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | | | Reserved for Google OAuth (not yet wired) |
| `NUTRITIONIX_APP_ID` / `NUTRITIONIX_APP_KEY` | | | Legacy, superseded by Gemini |

### Frontend (`frontend/.env`)

| Variable | Description |
|---|---|
| `REACT_APP_API_URL` | API base **including `/api`**, e.g. `https://api.fitflow.example.com/api`. This is baked in at **build time**. |

---

## 10. Security & Compliance

- Passwords are hashed with **bcrypt**. JWTs are signed with `SECRET_KEY`, and every protected route validates the token, the user's existence and the active flag.
- Every query is scoped to `current_user.id`, so users can only read or modify their own records.
- **Never commit `.env` files.** Keep production secrets in your hosting platform's secret store, and rotate any key that has appeared in git history.
- Health data (symptoms, diagnoses, medications) is sensitive. Encrypt it at rest, enforce TLS everywhere, and restrict database access to the API server only. If you operate under **HIPAA**, **GDPR** or India's **DPDP Act**, review the data-retention, consent and BAA requirements before launch.
- Restrict CORS to your production domain through `FRONTEND_URL`.

---

## 11. Known Limitations & Roadmap

FitFlow AI is under active development. The table lists known gaps with recommended fixes.

| Area | Current state | Recommended fix |
|---|---|---|
| **Schema: medical** | `symptoms`, `doctor_visits`, `medications` and `medication_reminders` declare `user_id` as `Integer`, but `users.id` is a `UUID`. PostgreSQL rejects the foreign key, and inserts fail. | Change these columns to `UUID(as_uuid=True)` and the response schemas to `UUID` |
| **Schema: profile** | `user_service`, `routers/users.py` and `CalorieService.get_calorie_balance` read and write `UserProfile.fitness_level` / `profile_image`, which don't exist on the model. As a result, profile create/update and `/api/calorie/balance` raise errors. | Add both columns to `UserProfile` |
| **Gemini model** | Hard-coded to `gemini-1.5-flash`, which Google has retired. Calls fail and silently fall back to mock or keyword logic. | Move the model id to config and use a current model (e.g. `gemini-2.5-flash`). Consider migrating from `google-generativeai` to the `google-genai` SDK. |
| **Migrations** | Tables are created with `create_all` at startup | Adopt **Alembic** with versioned migrations |
| **Goal engine** | BMR always uses the male formula | Use `UserProfile.gender` |
| **Workouts** | The UI uses a static, in-component exercise list. The `exercises` tables aren't seeded. `workoutService.js` targets routes that don't exist (`/workouts/sessions`, `/workouts/exercises`). | Seed the catalogue and wire the UI to `/sessions/start`, `/sessions/{id}/end` and `/difficulty/{level}` |
| **Medication tracker** | The UI persists to `localStorage` instead of the existing `/api/medical/medications` API | Switch to `medicalService` so data syncs across devices |
| **Mindfulness** | The UI is fully client-side. `mindfulnessService.js` targets routes that don't exist. `current_streak` is always `0`. | Wire to `/sessions/start` and `/end`, and compute streaks from daily sessions |
| **Post-meal decision UI** | `/api/calorie/balance` is not yet surfaced on the Calories page | Add a "Burn it off" card in the Progress tab |
| **Auth** | JWT in `localStorage`, 30-minute tokens with no refresh, Google OAuth config unused | Refresh tokens or httpOnly cookies, then Google sign-in |
| **AI key handling** | The Gemini key is sent as a URL query parameter | Send it in the `x-goog-api-key` header |
| **Quality** | No backend tests or CI | pytest + httpx `AsyncClient`, run on every push with GitHub Actions |

---

## 12. Disclaimer

FitFlow AI's medical assistant provides **general wellness guidance only**. It is **not a medical device** and is **not a substitute for professional diagnosis or treatment**. Anyone with chest pain, palpitations, fainting or other severe symptoms should seek emergency care immediately.

---

<div align="center">

Built with FastAPI, React, Gemini and Clarifai.

</div>
