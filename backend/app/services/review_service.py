"""리뷰 서비스. 등록 시 감성 분석을 1회 수행하고 결과를 저장한다."""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy.orm import Session

from ..ml.loader import ModelBundle
from ..ml.predictor import predict
from ..models import Movie, Review
from ..repositories import review_repo
from ..schemas import ReviewCreate, ReviewOut

logger = logging.getLogger(__name__)


class ReviewNotFoundError(Exception):
    """존재하지 않는 리뷰 ID."""


class MovieNotFoundError(Exception):
    """리뷰를 붙일 영화가 없다."""


def list_by_movie(
    session: Session, movie_id: int, limit: int, offset: int
) -> tuple[list[ReviewOut], int]:
    if session.get(Movie, movie_id) is None:
        raise MovieNotFoundError(movie_id)
    rows, total = review_repo.list_by_movie(session, movie_id, limit, offset)
    return [ReviewOut.model_validate(r) for r in rows], total


def list_recent(session: Session, limit: int, offset: int) -> tuple[list[ReviewOut], int]:
    rows, total = review_repo.list_recent(session, limit, offset)
    return [ReviewOut.model_validate(r) for r in rows], total


def create_review(
    session: Session, payload: ReviewCreate, bundle: ModelBundle | None
) -> ReviewOut:
    """리뷰를 저장한다.

    추론이 실패해도 리뷰 저장 자체는 성공시킨다. 감성 필드만 null로 두며,
    평균 평점 집계에서는 자동으로 제외된다(AVG가 NULL 행을 건너뛴다).
    """
    if session.get(Movie, payload.movie_id) is None:
        raise MovieNotFoundError(payload.movie_id)

    review = Review(
        movie_id=payload.movie_id,
        author=payload.author,
        title=payload.title,
        content=payload.content,
        created_at=datetime.now(),
    )

    if bundle is None:
        logger.warning("모델 미로드 상태로 리뷰 저장 — 감성 필드 null")
    else:
        try:
            result = predict(bundle, payload.content)
            review.sentiment_label = result.label
            review.sentiment_score = result.score
            review.confidence = result.confidence
            review.model_version = result.model_version
        except Exception:
            # 추론 실패를 리뷰 저장 실패로 번지게 하지 않는다
            logger.exception("감성 분석 실패 — 감성 필드 null로 저장한다")

    return ReviewOut.model_validate(review_repo.create_review(session, review))


def delete_review(session: Session, review_id: int) -> None:
    if not review_repo.delete_review(session, review_id):
        raise ReviewNotFoundError(review_id)
