"""Org router — live SQLite-backed reads/writes."""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from agents.shared.db import get_org_profile, get_setup_status, update_org_profile

router = APIRouter(prefix="/org", tags=["org"])


def ok(data) -> dict:
    return {"success": True, "data": data}


def err(message: str) -> dict:
    return {"success": False, "error": message}


@router.get("/setup-status")
async def setup_status():
    try:
        return ok(get_setup_status())
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(str(exc)))


@router.get("")
async def fetch_org():
    try:
        return ok(get_org_profile())
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(str(exc)))


@router.patch("")
async def patch_org(body: dict):
    try:
        update_org_profile(body)
        return ok(get_org_profile())
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(str(exc)))


@router.put("")
async def put_org(body: dict):
    try:
        update_org_profile(body)
        return ok(get_org_profile())
    except Exception as exc:
        return JSONResponse(status_code=500, content=err(str(exc)))
