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
![AWS](https://img.shields.io/badge/Deploy-AWS-FF9900?logo=amazonaws&logoColor=white)

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
10. [Deploying to AWS](#10-deploying-to-aws)
11. [Security & Compliance](#11-security--compliance)
12. [Known Limitations & Roadmap](#12-known-limitations--roadmap)
13. [Disclaimer](#13-disclaimer)

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

## 10. Deploying to AWS

### 10.1 Target architecture

```mermaid
flowchart TB
    User((Users)) --> R53[Route 53<br/>fitflow.example.com<br/>api.fitflow.example.com]
    R53 --> CF[CloudFront + ACM TLS<br/>SPA hosting]
    CF --> S3[(S3 bucket<br/>React build, private, OAC)]
    R53 --> ALB[Application Load Balancer<br/>HTTPS :443, ACM cert]
    subgraph VPC
        subgraph Public subnets
            ALB
            NAT[NAT Gateway]
        end
        subgraph Private subnets
            ECS[ECS Fargate service<br/>FastAPI container ×2+<br/>autoscaling]
            RDS[(RDS PostgreSQL<br/>Multi-AZ, encrypted)]
        end
    end
    ALB --> ECS --> RDS
    ECS -- outbound via NAT --> AI[[Gemini / Clarifai APIs]]
    SM[Secrets Manager] -. injected at task start .-> ECS
    ECS -. logs/metrics .-> CW[CloudWatch]
    ECR[(ECR image registry)] -. pull .-> ECS
```

| Concern | AWS service | Why |
|---|---|---|
| Static frontend | **S3 + CloudFront** | Global CDN, cheap, HTTPS, SPA fallback routing |
| API compute | **ECS on Fargate** behind an **ALB** | Serverless containers, rolling deploys, autoscaling, health checks on `/health` |
| Database | **RDS for PostgreSQL** | Managed backups, Multi-AZ, encryption at rest. The app already ships `asyncpg`. |
| Secrets | **Secrets Manager** | `SECRET_KEY`, `DATABASE_URL` and AI keys never live in images or git |
| Images | **ECR** | Private container registry with image scanning |
| TLS / DNS | **ACM + Route 53** | Free certificates and managed DNS |
| Observability | **CloudWatch Logs, Metrics, Alarms** | Container logs, 5xx and latency alarms |
| Protection (recommended) | **AWS WAF** on CloudFront and the ALB | Rate-limit the AI endpoints, managed rule sets |

> **Simpler alternatives:** **AWS Amplify Hosting** can replace S3 + CloudFront for the frontend with Git-push deploys. **AWS App Runner** can replace ECS + ALB for the backend: point it at the ECR image, set the env/secrets, and it handles TLS and scaling. On a tight budget, see [§10.10](#1010-budget-option-single-ec2-instance).

### 10.2 Pre-flight checklist (do this first)

- [ ] **Fix the PostgreSQL schema blockers** in [§12](#12-known-limitations--roadmap). The medical tables use an `Integer` `user_id` that references a `UUID` key, so `create_all` fails on PostgreSQL. `UserProfile` is also missing `fitness_level` and `profile_image`.
- [ ] Update the Gemini model id (`gemini-1.5-flash` has been retired) in `ai_service.py` and `food_ai_service.py`.
- [ ] Set `DEBUG=False`.
- [ ] Generate a new `SECRET_KEY`, and rotate every key that has ever been committed to git.
- [ ] Make sure `backend/.env` is **not** tracked (`git rm --cached backend/.env`).

### 10.3 Containerise the backend

Create `backend/Dockerfile`:

```dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN useradd --create-home appuser
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers"]
```

Create `backend/.dockerignore`:

```
venv/
__pycache__/
*.db
.env
```

Test locally:

```bash
docker build -t fitflow-api ./backend
docker run --rm -p 8000:8000 --env-file backend/.env fitflow-api
```

### 10.4 Push the image to ECR

```bash
export AWS_REGION=ap-south-1                      # choose your region
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export ECR=$ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com

aws ecr create-repository --repository-name fitflow-api --image-scanning-configuration scanOnPush=true
aws ecr get-login-password | docker login --username AWS --password-stdin $ECR

docker build -t $ECR/fitflow-api:v1 ./backend
docker push $ECR/fitflow-api:v1
```

### 10.5 Networking and database

1. **VPC**: use the VPC wizard ("VPC and more") to create 2 AZs, 2 public subnets, 2 private subnets and 1 NAT gateway. The NAT gateway lets private tasks reach the Gemini and Clarifai APIs.
2. **Security groups**:
   - `sg-alb`: inbound 443 (and 80 for redirect) from `0.0.0.0/0`
   - `sg-api`: inbound 8000 **from `sg-alb` only**
   - `sg-db`: inbound 5432 **from `sg-api` only**
3. **RDS PostgreSQL 16**: private subnet group, `sg-db`, storage encryption on, automated backups of 7+ days, Multi-AZ for production, and no public access.

```bash
aws rds create-db-instance \
  --db-instance-identifier fitflow-db \
  --engine postgres --engine-version 16 \
  --db-instance-class db.t4g.micro \
  --allocated-storage 20 --storage-encrypted \
  --master-username fitflow --manage-master-user-password \
  --db-name fitflow \
  --vpc-security-group-ids <sg-db> \
  --db-subnet-group-name <private-subnet-group> \
  --no-publicly-accessible --backup-retention-period 7
```

The connection string format is:

```
postgresql+asyncpg://fitflow:<password>@<rds-endpoint>:5432/fitflow?ssl=require
```

### 10.6 Secrets

```bash
aws secretsmanager create-secret --name fitflow/prod --secret-string '{
  "DATABASE_URL":   "postgresql+asyncpg://fitflow:<pw>@<endpoint>:5432/fitflow?ssl=require",
  "SECRET_KEY":     "<64+ random chars>",
  "GEMINI_API_KEY": "<key>",
  "CLARIFAI_PAT":   "<pat>"
}'
```

### 10.7 ECS Fargate service + ALB

1. **Cluster**: `aws ecs create-cluster --cluster-name fitflow`
2. **IAM**: the task *execution* role needs `AmazonECSTaskExecutionRolePolicy` plus `secretsmanager:GetSecretValue` on `fitflow/prod*`.
3. **Task definition** (`taskdef.json`, abridged):

```json
{
  "family": "fitflow-api",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "512",
  "memory": "1024",
  "executionRoleArn": "arn:aws:iam::<ACCOUNT_ID>:role/ecsTaskExecutionRole",
  "containerDefinitions": [{
    "name": "api",
    "image": "<ECR>/fitflow-api:v1",
    "portMappings": [{ "containerPort": 8000 }],
    "environment": [
      { "name": "DEBUG",        "value": "False" },
      { "name": "APP_NAME",     "value": "FitFlow" },
      { "name": "FRONTEND_URL", "value": "https://fitflow.example.com" }
    ],
    "secrets": [
      { "name": "DATABASE_URL",   "valueFrom": "arn:aws:secretsmanager:<region>:<acct>:secret:fitflow/prod:DATABASE_URL::" },
      { "name": "SECRET_KEY",     "valueFrom": "arn:aws:secretsmanager:<region>:<acct>:secret:fitflow/prod:SECRET_KEY::" },
      { "name": "GEMINI_API_KEY", "valueFrom": "arn:aws:secretsmanager:<region>:<acct>:secret:fitflow/prod:GEMINI_API_KEY::" },
      { "name": "CLARIFAI_PAT",   "valueFrom": "arn:aws:secretsmanager:<region>:<acct>:secret:fitflow/prod:CLARIFAI_PAT::" }
    ],
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "/ecs/fitflow-api",
        "awslogs-region": "<region>",
        "awslogs-stream-prefix": "api",
        "awslogs-create-group": "true"
      }
    }
  }]
}
```

```bash
aws ecs register-task-definition --cli-input-json file://taskdef.json
```

4. **Load balancer**: create an internet-facing ALB in the public subnets with `sg-alb`. Add a target group of type `ip` on port 8000 with health check path **`/health`**. Add an HTTPS :443 listener with an ACM certificate for `api.fitflow.example.com`, and an HTTP :80 listener that redirects to 443.
5. **Service**: launch type Fargate, private subnets, `sg-api`, no public IP, desired count 2, attached to the target group. Enable the **deployment circuit breaker with rollback**. Add target-tracking autoscaling at about 60% CPU, with 2–6 tasks.
6. **DNS**: create a Route 53 alias record `api.fitflow.example.com` → the ALB.

Verify with `curl https://api.fitflow.example.com/health`.

### 10.8 Frontend: S3 + CloudFront

```bash
cd frontend
REACT_APP_API_URL=https://api.fitflow.example.com/api npm run build

aws s3 mb s3://fitflow-web-<unique>
aws s3 sync build/ s3://fitflow-web-<unique> --delete \
  --cache-control "public,max-age=31536000,immutable" --exclude index.html
aws s3 cp build/index.html s3://fitflow-web-<unique>/index.html \
  --cache-control "no-cache"
```

Set up the CloudFront distribution:
- **Origin**: the S3 bucket with **Origin Access Control**. Keep the bucket private and block all public access.
- **Default root object**: `index.html`.
- **Custom error responses** (required for React Router deep links such as `/calories`): map **403 → `/index.html` (200)** and **404 → `/index.html` (200)**.
- **Viewer protocol**: redirect HTTP to HTTPS. Add the ACM certificate (it must be issued in **us-east-1**) and the alternate domain `fitflow.example.com`.
- Add a Route 53 alias `fitflow.example.com` → the distribution.

After each deploy, invalidate `index.html`:

```bash
aws cloudfront create-invalidation --distribution-id <ID> --paths "/index.html"
```

The camera capture on the Calories page uses `getUserMedia`, which browsers only allow over **HTTPS**. CloudFront provides that.

### 10.9 CI/CD with GitHub Actions (OIDC, no long-lived keys)

`.github/workflows/deploy.yml` (sketch):

```yaml
name: deploy
on: { push: { branches: [main] } }
permissions: { id-token: write, contents: read }

jobs:
  api:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with: { role-to-assume: "${{ secrets.AWS_DEPLOY_ROLE }}", aws-region: ap-south-1 }
      - uses: aws-actions/amazon-ecr-login@v2
        id: ecr
      - run: |
          IMG=${{ steps.ecr.outputs.registry }}/fitflow-api:${{ github.sha }}
          docker build -t $IMG ./backend && docker push $IMG
          echo "IMG=$IMG" >> $GITHUB_ENV
      - uses: aws-actions/amazon-ecs-render-task-definition@v1
        id: td
        with: { task-definition: taskdef.json, container-name: api, image: "${{ env.IMG }}" }
      - uses: aws-actions/amazon-ecs-deploy-task-definition@v2
        with:
          task-definition: ${{ steps.td.outputs.task-definition }}
          service: fitflow-api
          cluster: fitflow
          wait-for-service-stability: true

  web:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20, cache: npm, cache-dependency-path: frontend/package-lock.json }
      - uses: aws-actions/configure-aws-credentials@v4
        with: { role-to-assume: "${{ secrets.AWS_DEPLOY_ROLE }}", aws-region: ap-south-1 }
      - run: |
          cd frontend && npm ci
          REACT_APP_API_URL=https://api.fitflow.example.com/api npm run build
          aws s3 sync build/ s3://${{ secrets.WEB_BUCKET }} --delete
          aws cloudfront create-invalidation --distribution-id ${{ secrets.CF_DIST_ID }} --paths "/index.html"
```

### 10.10 Budget option: single EC2 instance

This option is for demos, portfolios and student projects:

1. Launch a **t3.small** (Amazon Linux 2023 or Ubuntu) with an Elastic IP. Open ports 22 (your IP only), 80 and 443.
2. Install Docker and run the API container. Use the instance's local PostgreSQL in Docker, or RDS on the free tier.
3. Put **Nginx** in front: serve `frontend/build/` as static files with `try_files $uri /index.html;`, and `proxy_pass` `/api/` to `127.0.0.1:8000`. In that setup, build the frontend with `REACT_APP_API_URL=/api`.
4. Use **Certbot** for a free Let's Encrypt certificate, which the HTTPS camera access needs.

This trades high availability for a much lower and simpler bill. Move to the ECS architecture when you need uptime guarantees.

### 10.11 Operations

- **Logs**: CloudWatch log group `/ecs/fitflow-api`.
- **Alarms**: ALB `HTTPCode_Target_5XX_Count`, `TargetResponseTime` p95, ECS CPU/memory, RDS `FreeStorageSpace` and `CPUUtilization`.
- **Backups**: RDS automated backups plus a manual snapshot before each schema change.
- **Cost control**: AWS Budgets alert. Rate-limit `/api/calorie/quick-analyze` and `/api/medical/chat` with WAF, because they call paid third-party AI APIs.

---

## 11. Security & Compliance

- Passwords are hashed with **bcrypt**. JWTs are signed with `SECRET_KEY`, and every protected route validates the token, the user's existence and the active flag.
- Every query is scoped to `current_user.id`, so users can only read or modify their own records.
- **Never commit `.env` files.** Store production secrets in AWS Secrets Manager, and rotate any key that has appeared in git history.
- Health data (symptoms, diagnoses, medications) is sensitive. Encrypt it at rest (RDS encryption), enforce TLS everywhere, restrict database access to the API security group, and enable CloudTrail. If you operate under **HIPAA**, **GDPR** or India's **DPDP Act**, review the data-retention, consent and BAA requirements before launch.
- Restrict CORS to your production domain through `FRONTEND_URL`.

---

## 12. Known Limitations & Roadmap

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
| **Quality** | No backend tests or CI | pytest + httpx `AsyncClient`, plus the GitHub Actions pipeline in §10.9 |

---

## 13. Disclaimer

FitFlow AI's medical assistant provides **general wellness guidance only**. It is **not a medical device** and is **not a substitute for professional diagnosis or treatment**. Anyone with chest pain, palpitations, fainting or other severe symptoms should seek emergency care immediately.

---

<div align="center">

Built with FastAPI, React, Gemini and Clarifai.

</div>
