from fastapi import APIRouter

from src.api.common import common_router
from src.api.order import order_router
from src.api.project import project_router

router = APIRouter()
router.include_router(order_router, prefix="/api")
router.include_router(common_router, prefix="/api")
router.include_router(project_router, prefix="/api")
