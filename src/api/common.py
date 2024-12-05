from fastapi import APIRouter

common_router = APIRouter(tags=["system"])


@common_router.get("/ping", response_model=str)
async def ping() -> str:
    return "pong"
