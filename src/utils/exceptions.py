from starlette import status
from starlette.requests import Request
from starlette.responses import JSONResponse


class NotFoundError(Exception):
    def __init__(self, entity: str) -> None:
        self.entity = entity


class UnprocessableEntityError(Exception):
    def __init__(self, content: str) -> None:
        self.content = content


async def not_found_handler(request: Request, exc: NotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"message": f"{exc.entity} not exists."},
    )


async def unprocessable_entity_handler(request: Request, exc: UnprocessableEntityError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"message": f"{exc.content}"},
    )
