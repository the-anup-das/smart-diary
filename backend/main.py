from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine
import models

import time
from sqlalchemy.exc import OperationalError

# Intelligently builds tracking tables, gracefully polling if Postgres is computationally slow to boot inside Docker 
for _ in range(15):
    try:
        models.Base.metadata.create_all(bind=engine)
        break
    except OperationalError:
        print("Waiting for Postgres Docker Network to map...")
        time.sleep(2)

app = FastAPI(title="AI Diary Core API", version="1.0")

# Allow Next.js frontend to securely hit the API natively via CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from routers import auth, entries, analyze, insights, users, decisions

app.include_router(auth.router)
app.include_router(entries.router)
app.include_router(analyze.router)
app.include_router(insights.router)
app.include_router(users.router)
app.include_router(decisions.router)
@app.get("/api/health")
async def health_check():
    return {"status": "operational", "engine": "FastAPI"}
