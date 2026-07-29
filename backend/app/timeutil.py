"""저장 시각의 기준 — UTC 하나로 통일한다.

`datetime.now()`는 컨테이너의 TZ 설정에 좌우된다. 로컬(KST)에서 만든 시드와
Cloud Run(UTC)에서 등록한 리뷰가 9시간 어긋나면 `created_at` 내림차순 정렬이
뒤집혀 방금 쓴 리뷰가 최근 목록에 나타나지 않는다. 저장용 시각은 여기서만 만든다.

표시용 지역 시각 변환은 표현 계층(프론트엔드)의 몫이다.
"""
from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """현재 UTC 시각. DB 컬럼이 naive라 tzinfo를 떼고 돌려준다."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
