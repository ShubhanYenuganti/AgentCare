"""FastAPI scaffold entrypoint for Sprint 1."""

from __future__ import annotations

import json
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.mock_apis import router as mock_router
from api.routers import actions, caregivers, ingest, notifications, org, patients, scheduling

app = FastAPI(title="MACOS API Scaffold")

_cors_origins = json.loads(os.getenv("CORS_ORIGINS", '["*"]'))
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(actions.router)
app.include_router(caregivers.router)
app.include_router(ingest.router)
app.include_router(notifications.router)
app.include_router(org.router)
app.include_router(patients.router)
app.include_router(scheduling.router)
app.include_router(mock_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
