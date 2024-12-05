import pytest
import redis
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from src.config import settings
from src.db import Base
from src.core.repositories.client import ClientRepository


SQLALCHEMY_DATABASE_URI = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URI, connect_args={"check_same_thread": False})

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@event.listens_for(engine, "connect")
def do_connect(dbapi_connection, connection_record):
    dbapi_connection.isolation_level = None


@event.listens_for(engine, "begin")
def do_begin(conn):
    conn.exec_driver_sql("BEGIN")


@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def end_savepoint(session, transaction):
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def redis_client():
    client = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=0)

    yield client

    client.flushdb()
    client.close()
