from fastapi import APIRouter

router = APIRouter(prefix="/caregivers", tags=["caregivers"])


@router.get("")
async def get_caregivers() -> list[dict]:
    return []
