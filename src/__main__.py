import uvicorn

from src.config import settings

uvicorn.run(
    "src.app:app",
    host=settings.SERVER_HOST,
    port=settings.SERVER_PORT,
    reload=True,
)
