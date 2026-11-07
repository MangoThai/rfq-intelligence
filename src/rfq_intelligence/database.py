from typing import TypeAlias

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

SessionFactory: TypeAlias = sessionmaker[Session]


def create_database_engine(
    database_url: str,
) -> Engine:
    return create_engine(
        database_url,
        pool_pre_ping=True,
    )


def create_session_factory(
    engine: Engine,
) -> SessionFactory:
    return sessionmaker(
        bind=engine,
        autoflush=False,
        expire_on_commit=False,
    )
