"""리뷰 라우터. 등록 시 감성 분석이 자동 실행된다(`심화` 요건)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from ..database import get_session
from ..ml.loader import ModelBundle
from ..schemas import ErrorResponse, Page, ReviewCreate, ReviewOut
from ..services import review_service

router = APIRouter(prefix="/reviews", tags=["reviews"])


def get_bundle(request: Request) -> ModelBundle | None:
    """lifespan에서 1회 로드한 모델을 꺼낸다. 실패 시 None이다."""
    return getattr(request.app.state, "model_bundle", None)


@router.post(
    "",
    response_model=ReviewOut,
    status_code=status.HTTP_201_CREATED,
    summary="리뷰 등록 (감성 분석 자동 실행)",
    description=(
        "리뷰를 저장하면서 감성 분석을 1회 수행하고 결과를 함께 저장한다. "
        "조회할 때마다 다시 추론하지 않는다.\n\n"
        "추론에 실패하거나 모델이 로드되지 않은 경우에도 **201을 반환한다** — "
        "리뷰 저장 자체는 성공했기 때문이다. 이때 감성 필드는 `null`이며 "
        "평균 평점 계산에서 제외된다."
    ),
    responses={404: {"model": ErrorResponse, "description": "존재하지 않는 영화"}},
)
def create_review(
    payload: ReviewCreate,
    session: Session = Depends(get_session),
    bundle: ModelBundle | None = Depends(get_bundle),
) -> ReviewOut:
    try:
        return review_service.create_review(session, payload, bundle)
    except review_service.MovieNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"영화를 찾을 수 없습니다: id={payload.movie_id}",
        ) from exc


@router.get(
    "",
    response_model=Page[ReviewOut],
    summary="전체 리뷰 최신순 조회",
    description=(
        "모든 영화의 리뷰를 `created_at` 내림차순으로 반환한다. "
        "'최근 리뷰 10개' 화면이 `limit=10&offset=0`으로 호출한다."
    ),
)
def list_reviews(
    session: Session = Depends(get_session),
    limit: int = Query(default=10, ge=1, le=100, description="한 페이지 항목 수"),
    offset: int = Query(default=0, ge=0, description="건너뛸 항목 수"),
) -> Page[ReviewOut]:
    items, total = review_service.list_recent(session, limit, offset)
    return Page[ReviewOut](items=items, total=total, limit=limit, offset=offset)


@router.delete(
    "/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="리뷰 삭제",
    description="리뷰 1건을 삭제한다. 해당 영화의 평균 평점은 다음 조회 시 자동으로 다시 집계된다.",
    responses={404: {"model": ErrorResponse, "description": "존재하지 않는 리뷰"}},
)
def delete_review(review_id: int, session: Session = Depends(get_session)) -> Response:
    try:
        review_service.delete_review(session, review_id)
    except review_service.ReviewNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"리뷰를 찾을 수 없습니다: id={review_id}",
        ) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
