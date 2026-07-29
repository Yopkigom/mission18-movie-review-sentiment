"""영화 DB 접근. 평점 집계 쿼리를 포함한다."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Movie, Review

# 평점 집계 컬럼. 감성 분석에 실패한 리뷰(sentiment_score IS NULL)는
# AVG에서 자동으로 제외된다 — 실패한 리뷰가 평균을 0으로 끌어당기지 않는다.
_RATING = func.avg(Review.sentiment_score).label("sentiment_rating")
_REVIEW_COUNT = func.count(Review.id).label("review_count")
_ANALYZED_COUNT = func.count(Review.sentiment_score).label("analyzed_count")


def _base_query():
    """영화 + 평점 집계. 리뷰가 없어도 영화가 빠지지 않도록 LEFT OUTER JOIN."""
    return (
        select(Movie, _RATING, _REVIEW_COUNT)
        .outerjoin(Review, Review.movie_id == Movie.id)
        .group_by(Movie.id)
    )


def list_movies(session: Session, limit: int, offset: int) -> tuple[list[tuple], int]:
    """영화 목록과 전체 건수를 함께 반환한다."""
    total = session.scalar(select(func.count(Movie.id))) or 0
    stmt = _base_query().order_by(Movie.id.desc()).limit(limit).offset(offset)
    return list(session.execute(stmt).all()), total


def get_movie(session: Session, movie_id: int) -> tuple | None:
    stmt = _base_query().where(Movie.id == movie_id)
    return session.execute(stmt).first()


def get_rating(session: Session, movie_id: int) -> tuple | None:
    """평점 조회. 영화 존재 여부를 함께 판단하기 위해 Movie.id를 함께 조회한다."""
    stmt = (
        select(Movie.id, _RATING, _REVIEW_COUNT, _ANALYZED_COUNT)
        .outerjoin(Review, Review.movie_id == Movie.id)
        .where(Movie.id == movie_id)
        .group_by(Movie.id)
    )
    return session.execute(stmt).first()


def find_duplicate(
    session: Session, *, tmdb_id: int | None, title: str, release_date
) -> Movie | None:
    """등록 전 중복 확인. UNIQUE 제약 위반을 409로 바꾸기 위한 사전 조회다."""
    conditions = [(Movie.title == title) & (Movie.release_date == release_date)]
    if tmdb_id is not None:
        conditions.append(Movie.tmdb_id == tmdb_id)

    stmt = select(Movie).where(conditions[0] if len(conditions) == 1 else
                               conditions[0] | conditions[1])
    return session.scalars(stmt).first()


def create_movie(session: Session, movie: Movie) -> Movie:
    session.add(movie)
    session.commit()
    session.refresh(movie)
    return movie


def delete_movie(session: Session, movie_id: int) -> bool:
    """영화 삭제. 리뷰는 FK의 ON DELETE CASCADE로 DB가 함께 제거한다."""
    movie = session.get(Movie, movie_id)
    if movie is None:
        return False
    session.delete(movie)
    session.commit()
    return True
