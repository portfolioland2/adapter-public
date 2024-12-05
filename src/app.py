from fastapi import FastAPI

from src.api import router
from src.config import settings
from src.tracer import init_tracer
from src.utils.exceptions import (
    not_found_handler,
    NotFoundError,
    unprocessable_entity_handler,
    UnprocessableEntityError,
)


def create_app() -> FastAPI:
    path_prefix = "/dev" if settings.ENV == "dev" else ""
    app = FastAPI(
        title=f"RKeeper адаптер {path_prefix}",
        description="Сервис для синхронизации данных",
        version=settings.VERSION,
        root_path=path_prefix,
        openapi_prefix=path_prefix,
    )
    app.include_router(router)
    app.add_exception_handler(NotFoundError, not_found_handler)
    app.add_exception_handler(UnprocessableEntityError, unprocessable_entity_handler)

    @app.on_event("startup")
    def init_opentelemetry() -> None:
        init_tracer()

    return app


app = create_app()
