"""FastAPI scaffold entrypoint for Sprint 1."""

from __future__ import annotations

from fastapi import FastAPI

from api.mock_apis import router as mock_router
from api.routers import actions, caregivers, ingest, notifications, org, patients, scheduling

app = FastAPI(title="MACOS API Scaffold")
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
