from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker, declarative_base


from src.config import settings
from src.logger import get_logger

logger = get_logger("db")

engine = create_engine(settings.SQLALCHEMY_DATABASE_URI, logging_name="db", pool_size=50)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

meta = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_`%(constraint_name)s`",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)
Base = declarative_base(metadata=meta)
