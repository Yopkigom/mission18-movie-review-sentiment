"""엔진 · 세션 · PRAGMA 설정.

SQLite는 외래 키 제약이 연결마다 꺼져 있다. `PRAGMA foreign_keys=ON`을 걸지 않으면
`ON DELETE CASCADE`가 조용히 무시되고 테스트에서도 통과해 버린다.
"""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


def create_db_engine(database_url: str) -> Engine:
    engine = create_engine(
        database_url,
        # Streamlit/uvicorn의 스레드 풀에서 동일 연결이 재사용될 수 있다
        connect_args={"check_same_thread": False},
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _record):  # noqa: ANN001
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            # 읽기 위주 워크로드에서 잠금 경합을 줄인다
            cursor.execute("PRAGMA journal_mode=WAL")
        finally:
            cursor.close()

    return engine


engine = create_db_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """FastAPI 의존성. 요청마다 세션을 열고 반드시 닫는다."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
