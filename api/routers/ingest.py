from fastapi import APIRouter

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/text")
async def ingest_text() -> dict[str, str]:
    return {"status": "scaffold"}
