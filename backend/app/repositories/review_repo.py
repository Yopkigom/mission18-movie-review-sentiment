"""리뷰 DB 접근."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import Review

# 같은 초에 생성된 시드 리뷰의 순서를 고정하기 위해 id를 보조 정렬 키로 둔다
_ORDER = (Review.created_at.desc(), Review.id.desc())


def list_by_movie(
    session: Session, movie_id: int, limit: int, offset: int
) -> tuple[list[Review], int]:
    total = session.scalar(
        select(func.count(Review.id)).where(Review.movie_id == movie_id)
    ) or 0
    stmt = (
        select(Review)
        .where(Review.movie_id == movie_id)
        .order_by(*_ORDER)
        .limit(limit)
        .offset(offset)
    )
    return list(session.scalars(stmt).all()), total


def list_recent(session: Session, limit: int, offset: int) -> tuple[list[Review], int]:
    """최근 리뷰. '최근 10개 리뷰' 화면이 limit=10으로 호출한다."""
    total = session.scalar(select(func.count(Review.id))) or 0
    stmt = select(Review).order_by(*_ORDER).limit(limit).offset(offset)
    return list(session.scalars(stmt).all()), total


def create_review(session: Session, review: Review) -> Review:
    session.add(review)
    session.commit()
    session.refresh(review)
    return review


def delete_review(session: Session, review_id: int) -> bool:
    review = session.get(Review, review_id)
    if review is None:
        return False
    session.delete(review)
    session.commit()
    return True
