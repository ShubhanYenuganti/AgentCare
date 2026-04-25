from fastapi import APIRouter

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("")
async def get_patients() -> list[dict]:
    return []
