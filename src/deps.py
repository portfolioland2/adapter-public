from typing import Generator

from fastapi import (
    Security,
    HTTPException,
    Depends,
)
from fastapi.security import APIKeyHeader
from starlette.status import HTTP_403_FORBIDDEN

from src.core.repositories.client import ClientRepository
from sqlalchemy.orm import Session

from src.db import SessionLocal
from src.models import Client


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_client_by_api_key(
    authorization: str = Security(
        APIKeyHeader(
            name="Authorization",
            description="Ключ API, используемый для интеграции. Передается в заголовках запросов в виде "
            "`{'Authorization': $API_KEY}`. Для получения обращаться по почте integration@starterapp.ru",
            auto_error=True,
        )
    ),
    db: Session = Depends(get_db),
) -> Client:
    client = ClientRepository(db).get_client_by_api_key(authorization)
    if client:
        return client

    raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Not valid credentials")
