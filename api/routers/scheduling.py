from fastapi import APIRouter

router = APIRouter(prefix="/scheduling", tags=["scheduling"])


@router.get("/tasks")
async def get_scheduling_tasks() -> list[dict]:
    return []
