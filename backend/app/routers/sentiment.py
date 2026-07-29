"""감성 분석 단독 엔드포인트. 저장 없이 모델만 호출한다."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from ..ml.loader import ModelBundle
from ..ml.predictor import predict
from ..schemas import ErrorResponse, SentimentRequest, SentimentResponse
from .reviews import get_bundle

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sentiment", tags=["sentiment"])


@router.post(
    "/analyze",
    response_model=SentimentResponse,
    summary="감성 분석 (저장 없음)",
    description=(
        "텍스트 1건의 감성을 분석한다. DB에 저장하지 않으므로 모델 동작만 확인할 때 쓴다.\n\n"
        "모델은 미션 13에서 학습·ONNX 변환한 ELECTRA 계열 3-class 분류기다. "
        "입력은 256 토큰 고정 길이이며, 초과분은 잘리고(`truncated=true`) 부족분은 패딩된다. "
        "`confidence`는 `max(softmax(logits))`이며 표기 전용이다 — 예측값을 보정하지 않는다."
    ),
    responses={503: {"model": ErrorResponse, "description": "모델 미로드 또는 추론 실패"}},
)
def analyze(
    payload: SentimentRequest, bundle: ModelBundle | None = Depends(get_bundle)
) -> SentimentResponse:
    if bundle is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="감성 분석 모델이 로드되지 않았습니다.",
        )
    try:
        result = predict(bundle, payload.text)
    except Exception as exc:
        logger.exception("감성 분석 실패")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="감성 분석에 실패했습니다.",
        ) from exc

    return SentimentResponse(
        label=result.label,
        score=result.score,
        confidence=result.confidence,
        probabilities=result.probabilities,
        model_version=result.model_version,
        truncated=result.truncated,
    )
