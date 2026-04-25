from fastapi import APIRouter

router = APIRouter(prefix="/org", tags=["org"])


@router.get("")
async def get_org() -> dict[str, str]:
    return {"org_name": "Sunrise Care Org (Scaffold)"}
