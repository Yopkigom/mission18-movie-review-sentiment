"""표현 계층 유틸 — 별점 환산 · 말줄임 · 감성 표기.

별점 환산은 여기서만 한다. 환산 결과를 백엔드로 되돌려 보내지 않는다.
"""
from __future__ import annotations

from datetime import datetime

# `판정 애매` 임계값. model-eval.md C-b 실측 근거:
# confidence 0.90 미만 구간은 엄격 정확도가 0.5를 밑돌고 중립 예측이 40~55%를 차지한다
CONFIDENCE_THRESHOLD = 0.90

# 감성 라벨 → 화면 표기 · 색
SENTIMENT_DISPLAY = {
    "긍정": ("좋아요", "#1a7f37", "#e6f4ea"),
    "중립": ("보통", "#5f6368", "#eeeeee"),
    "부정": ("별로에요", "#c5221f", "#fce8e6"),
}


def to_stars(rating: float | None) -> str:
    """감성 평점(-1~+1)을 0~5 별점 문자열로 환산한다. 표시 전용."""
    if rating is None:
        return ""
    value = (rating + 1) / 2 * 5
    filled = int(round(value))
    return "★" * filled + "☆" * (5 - filled)


def to_score_5(rating: float | None) -> float | None:
    if rating is None:
        return None
    return round((rating + 1) / 2 * 5, 1)


def rating_text(rating: float | None, review_count: int) -> str:
    """리뷰 0건일 때 별 0개를 그리면 '최악의 평가'로 오독된다. 문구로 구분한다."""
    if rating is None:
        return f"평점 없음 (리뷰 {review_count}건)"
    return f"{to_stars(rating)}  {to_score_5(rating)} / 5  (리뷰 {review_count}건)"


def is_uncertain(confidence: float | None) -> bool:
    return confidence is not None and confidence < CONFIDENCE_THRESHOLD


def badge_html(label: str | None, confidence: float | None) -> str:
    """감성 배지. 저확신이면 `판정 애매`를 덧붙이되 라벨은 바꾸지 않는다."""
    if label is None:
        return _chip("분석 실패", "#5f6368", "#eeeeee")

    text, fg, bg = SENTIMENT_DISPLAY.get(label, (label, "#5f6368", "#eeeeee"))
    html = _chip(text, fg, bg)
    if is_uncertain(confidence):
        html += _chip("판정 애매", "#8a6d00", "#fef7e0")
    return html


def _chip(text: str, fg: str, bg: str) -> str:
    return (
        f"<span style='display:inline-block;padding:2px 10px;margin-right:4px;"
        f"border-radius:12px;font-size:0.82rem;font-weight:600;"
        f"color:{fg};background:{bg};'>{text}</span>"
    )


def truncate(text: str, length: int = 40) -> str:
    text = text.replace("\n", " ").strip()
    return text if len(text) <= length else text[: length - 1] + "…"


def format_datetime(value: str, fmt: str = "%Y-%m-%d %H:%M") -> str:
    try:
        return datetime.fromisoformat(value).strftime(fmt)
    except (TypeError, ValueError):
        return str(value)
