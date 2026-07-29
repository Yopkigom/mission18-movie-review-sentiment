"""영화 서비스. 라우터가 HTTP를, 이 계층이 규칙을 담당한다."""
from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..models import Movie
from ..repositories import movie_repo
from ..schemas import MovieCreate, MovieDetail, MovieRating, MovieSummary


class MovieNotFoundError(Exception):
    """존재하지 않는 영화 ID."""


class DuplicateMovieError(Exception):
    """tmdb_id 또는 (제목, 개봉일) 중복."""


def _to_summary(row) -> MovieSummary:
    movie, rating, review_count = row
    return MovieSummary(
        id=movie.id,
        title=movie.title,
        poster_url=movie.poster_url,
        # 리뷰가 없으면 AVG가 NULL을 돌려준다. 0으로 바꾸지 않는다 —
        # 0은 '중립'이라는 의미를 이미 갖고 있어 리뷰 없음과 구분되지 않는다
        sentiment_rating=float(rating) if rating is not None else None,
        review_count=int(review_count),
    )


def _to_detail(row) -> MovieDetail:
    movie, rating, review_count = row
    return MovieDetail(
        id=movie.id,
        title=movie.title,
        poster_url=movie.poster_url,
        sentiment_rating=float(rating) if rating is not None else None,
        review_count=int(review_count),
        release_date=movie.release_date,
        director=movie.director,
        genre=movie.genre,
        external_rating=movie.external_rating,
        tmdb_id=movie.tmdb_id,
    )


def list_movies(session: Session, limit: int, offset: int) -> tuple[list[MovieSummary], int]:
    rows, total = movie_repo.list_movies(session, limit, offset)
    return [_to_summary(r) for r in rows], total


def get_movie(session: Session, movie_id: int) -> MovieDetail:
    row = movie_repo.get_movie(session, movie_id)
    if row is None:
        raise MovieNotFoundError(movie_id)
    return _to_detail(row)


def get_rating(session: Session, movie_id: int) -> MovieRating:
    row = movie_repo.get_rating(session, movie_id)
    if row is None:
        raise MovieNotFoundError(movie_id)
    movie_id_, rating, review_count, analyzed_count = row
    return MovieRating(
        movie_id=int(movie_id_),
        sentiment_rating=float(rating) if rating is not None else None,
        review_count=int(review_count),
        analyzed_count=int(analyzed_count),
    )


def create_movie(session: Session, payload: MovieCreate) -> MovieDetail:
    existing = movie_repo.find_duplicate(
        session,
        tmdb_id=payload.tmdb_id,
        title=payload.title,
        release_date=payload.release_date,
    )
    if existing is not None:
        raise DuplicateMovieError(payload.title)

    movie = Movie(**payload.model_dump())
    try:
        movie = movie_repo.create_movie(session, movie)
    except IntegrityError as exc:
        # 사전 조회와 INSERT 사이의 경합. UNIQUE 제약이 최종 방어선이다
        session.rollback()
        raise DuplicateMovieError(payload.title) from exc

    return MovieDetail(
        id=movie.id,
        title=movie.title,
        poster_url=movie.poster_url,
        sentiment_rating=None,
        review_count=0,
        release_date=movie.release_date,
        director=movie.director,
        genre=movie.genre,
        external_rating=movie.external_rating,
        tmdb_id=movie.tmdb_id,
    )


def delete_movie(session: Session, movie_id: int) -> None:
    if not movie_repo.delete_movie(session, movie_id):
        raise MovieNotFoundError(movie_id)
