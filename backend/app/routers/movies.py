"""영화 라우터. 가이드의 필수 기능(등록 · 조회 · 삭제)을 담당한다."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from ..database import get_session
from ..schemas import (
    ErrorResponse,
    MovieCreate,
    MovieDetail,
    MovieRating,
    MovieSummary,
    Page,
    ReviewOut,
)
from ..services import movie_service, review_service

router = APIRouter(prefix="/movies", tags=["movies"])


@router.get(
    "",
    response_model=Page[MovieSummary],
    summary="영화 목록 조회",
    description=(
        "등록된 영화를 최신 등록순으로 반환한다. 각 항목에 리뷰 감성 스칼라의 "
        "산술평균(`sentiment_rating`, -1~+1)과 리뷰 수가 포함된다. "
        "리뷰가 없는 영화는 `sentiment_rating`이 `null`이며, 0(중립)과 구분된다. "
        "별점 환산은 표현 계층의 책임이므로 응답은 원값을 유지한다."
    ),
)
def list_movies(
    session: Session = Depends(get_session),
    limit: int = Query(default=50, ge=1, le=100, description="한 페이지 항목 수"),
    offset: int = Query(default=0, ge=0, description="건너뛸 항목 수"),
) -> Page[MovieSummary]:
    items, total = movie_service.list_movies(session, limit, offset)
    return Page[MovieSummary](items=items, total=total, limit=limit, offset=offset)


@router.post(
    "",
    response_model=MovieDetail,
    status_code=status.HTTP_201_CREATED,
    summary="영화 등록",
    description=(
        "새 영화를 등록한다. `tmdb_id` 또는 (제목, 개봉일) 조합이 이미 존재하면 409를 반환한다. "
        "`external_rating`은 TMDB 평점(0~10)이며 리뷰 기반 감성 평점과는 별개 필드다."
    ),
    responses={409: {"model": ErrorResponse, "description": "이미 등록된 영화"}},
)
def create_movie(
    payload: MovieCreate, session: Session = Depends(get_session)
) -> MovieDetail:
    try:
        return movie_service.create_movie(session, payload)
    except movie_service.DuplicateMovieError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"이미 등록된 영화입니다: {payload.title}",
        ) from exc


@router.get(
    "/{movie_id}",
    response_model=MovieDetail,
    summary="영화 단건 조회",
    description="영화 상세 정보와 감성 평점 · 리뷰 수를 반환한다.",
    responses={404: {"model": ErrorResponse, "description": "존재하지 않는 영화"}},
)
def get_movie(movie_id: int, session: Session = Depends(get_session)) -> MovieDetail:
    try:
        return movie_service.get_movie(session, movie_id)
    except movie_service.MovieNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"영화를 찾을 수 없습니다: id={movie_id}",
        ) from exc


@router.delete(
    "/{movie_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="영화 삭제",
    description=(
        "영화를 삭제한다. 해당 영화의 리뷰도 외래 키의 `ON DELETE CASCADE`로 "
        "함께 삭제되며 되돌릴 수 없다."
    ),
    responses={404: {"model": ErrorResponse, "description": "존재하지 않는 영화"}},
)
def delete_movie(movie_id: int, session: Session = Depends(get_session)) -> Response:
    try:
        movie_service.delete_movie(session, movie_id)
    except movie_service.MovieNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"영화를 찾을 수 없습니다: id={movie_id}",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{movie_id}/reviews",
    response_model=Page[ReviewOut],
    summary="영화별 리뷰 목록",
    description=(
        "특정 영화의 리뷰를 `created_at` 내림차순으로 반환한다. "
        "화면은 10개 단위로 페이지를 나누며, 총 페이지 수 계산을 위해 `total`을 함께 준다."
    ),
    responses={404: {"model": ErrorResponse, "description": "존재하지 않는 영화"}},
)
def list_movie_reviews(
    movie_id: int,
    session: Session = Depends(get_session),
    limit: int = Query(default=10, ge=1, le=100, description="한 페이지 항목 수"),
    offset: int = Query(default=0, ge=0, description="건너뛸 항목 수"),
) -> Page[ReviewOut]:
    try:
        items, total = review_service.list_by_movie(session, movie_id, limit, offset)
    except review_service.MovieNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"영화를 찾을 수 없습니다: id={movie_id}",
        ) from exc
    return Page[ReviewOut](items=items, total=total, limit=limit, offset=offset)


@router.get(
    "/{movie_id}/rating",
    response_model=MovieRating,
    summary="영화 평점 조회",
    description=(
        "리뷰 감성 점수(-1 · 0 · +1)의 산술평균을 반환한다. "
        "감성 분석에 실패한 리뷰는 평균에서 제외되므로 `review_count`와 "
        "`analyzed_count`가 다를 수 있다."
    ),
    responses={404: {"model": ErrorResponse, "description": "존재하지 않는 영화"}},
)
def get_movie_rating(movie_id: int, session: Session = Depends(get_session)) -> MovieRating:
    try:
        return movie_service.get_rating(session, movie_id)
    except movie_service.MovieNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"영화를 찾을 수 없습니다: id={movie_id}",
        ) from exc
