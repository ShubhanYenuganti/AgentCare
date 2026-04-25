from fastapi import APIRouter

router = APIRouter(prefix="/actions", tags=["actions"])


@router.get("")
async def get_actions() -> list[dict]:
    return []
