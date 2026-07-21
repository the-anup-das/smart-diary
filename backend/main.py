from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine
import models

import os
import time
from sqlalchemy.exc import OperationalError

# Self-healing schema bootstrap (Alembic), polling while Postgres boots in Docker
from run_migrations import run_migrations

for _ in range(15):
    try:
        run_migrations()
        break
    except OperationalError:
        print("Waiting for Postgres Docker Network to map...")
        time.sleep(2)
    except Exception as e:
        # A stale schema beats a crash loop on a home server — log and continue.
        print(f"[migrations] WARNING: migration failed, starting anyway: {e}")
        break

app = FastAPI(title="AI Diary Core API", version="1.0")

# Allow Next.js frontend to securely hit the API natively via CORS.
# Override for production deployments via CORS_ORIGINS (comma-separated list).
cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from routers import auth, entries, analyze, insights, users, decisions, voice, chat, feedback, ai_config

app.include_router(auth.router)
app.include_router(entries.router)
app.include_router(analyze.router)
app.include_router(insights.router)
app.include_router(users.router)
app.include_router(decisions.router)
app.include_router(voice.router)
app.include_router(chat.router)
app.include_router(feedback.router)
app.include_router(ai_config.router)
@app.get("/api/health")
async def health_check():
    return {"status": "operational", "engine": "FastAPI"}
