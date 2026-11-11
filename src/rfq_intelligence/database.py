
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

DATABASE_CONNECT_TIMEOUT_SECONDS = 5

type SessionFactory = sessionmaker[Session]


def create_database_engine(
    database_url: str,
) -> Engine:
    return create_engine(
        database_url,
        poolclass=NullPool,
        connect_args={
            "connect_timeout": (DATABASE_CONNECT_TIMEOUT_SECONDS),
        },
    )


def create_session_factory(
    engine: Engine,
) -> SessionFactory:
    return sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )
