"""테스트 픽스처. 임시 파일 DB를 쓰고 모델은 로드하지 않는다.

인메모리 DB는 연결마다 별도 DB가 되어 PRAGMA·CASCADE 검증이 무의미해지므로
파일 DB를 쓴다.
"""
from __future__ import annotations

import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import Base, create_db_engine, get_session  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def session_factory(tmp_path: Path) -> Iterator[sessionmaker]:
    engine = create_db_engine(f"sqlite:///{tmp_path / 'test.db'}")
    Base.metadata.create_all(bind=engine)
    yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    engine.dispose()


@pytest.fixture()
def client(session_factory: sessionmaker) -> Iterator[TestClient]:
    def _override() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_session] = _override
    # context manager를 쓰지 않아 lifespan이 실행되지 않는다 — 모델을 로드하지 않으므로
    # 테스트가 빠르고, 감성 필드 null 폴백 경로를 그대로 검증하게 된다.
    # 실제 추론 검증은 test_ml.py가 담당한다
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def movie_payload() -> dict:
    return {
        "title": "테스트 영화",
        "release_date": "2020-01-01",
        "director": "홍길동",
        "genre": "드라마",
        "poster_url": "https://example.com/poster.jpg",
        "external_rating": 7.5,
        "tmdb_id": 123456,
    }


def _mark_as_seed(client: TestClient, movie_id: int) -> None:
    """테스트 도우미 — 해당 영화를 시드 데이터로 표시한다."""
    from app.database import get_session
    from app.models import Movie

    session_gen = client.app.dependency_overrides[get_session]()
    session = next(session_gen)
    try:
        movie = session.get(Movie, movie_id)
        movie.is_seed = True
        session.commit()
    finally:
        session.close()
