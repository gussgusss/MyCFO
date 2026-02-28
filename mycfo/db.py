from __future__ import annotations

from flask import Flask, g
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def init_db(app: Flask) -> None:
    connect_args = {}
    if app.config["DATABASE_URL"].startswith("sqlite"):
        connect_args["check_same_thread"] = False

    engine = create_engine(
        app.config["DATABASE_URL"],
        echo=app.config["SQLALCHEMY_ECHO"],
        future=True,
        pool_pre_ping=True,
        connect_args=connect_args,
    )
    app.extensions["db_engine"] = engine
    app.extensions["db_session_factory"] = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )


def get_db() -> Session:
    if "db_session" not in g:
        factory = g.app.extensions["db_session_factory"]
        g.db_session = factory()
    return g.db_session


def close_db(_: object | None = None) -> None:
    session = g.pop("db_session", None)
    if session is not None:
        session.close()
