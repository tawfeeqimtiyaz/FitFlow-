from contextlib import asynccontextmanager          # ✅ Added for lifespan
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine, Base

# Import all routers
from app.routers.auth import router as auth_router
from app.routers.users import router as users_router
from app.routers.workouts import router as workouts_router
from app.routers.nutrition import router as nutrition_router
from app.routers.medical import router as medical_router
from app.routers.mindfulness import router as mindfulness_router
from app.routers.calorie import router as calorie_router


# ✅ FIXED: @app.on_event("startup") deprecated in FastAPI 0.93+
#           lifespan is the modern replacement
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)  # ✅ create tables
    print(f"{settings.APP_NAME} started - tables ready")
    
    yield  # ← app runs here

    # ── Shutdown ──────────────────────────────────────────
    await engine.dispose()                         # ✅ clean DB connection pool
    print(f"{settings.APP_NAME} shutting down")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="AI-Powered Fitness and Wellness Application",
    version="1.0.0",
    lifespan=lifespan,                             # ✅ FIXED: replaces on_event
    docs_url="/docs",                              # ✅ Swagger UI
    redoc_url="/redoc",                            # ✅ ReDoc UI
)


# ✅ FIXED: CORS origins pulled from config
#           Covers both dev variants + env-configured frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        settings.FRONTEND_URL,                     # ✅ env-configurable for prod
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # Browsers hide non-standard response headers from cross-origin JS unless
    # they are exposed; the verification UI reads Retry-After for its cooldown.
    expose_headers=["Retry-After"],
)


# ── Health Routes ─────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
async def root():
    return {
        "message": f"Welcome to {settings.APP_NAME} API",
        "status": "running",
        "version": "1.0.0"
    }


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "debug": settings.DEBUG,                   # ✅ useful for diagnostics
    }


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(workouts_router)
app.include_router(nutrition_router)
app.include_router(medical_router)
app.include_router(mindfulness_router)
app.include_router(calorie_router)