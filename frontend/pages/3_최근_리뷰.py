"""최근 리뷰 10개 (`심화` 요건).

표시 항목은 가이드가 지정한 영화 ID · 등록일 · 리뷰 내용 · 감성 분석 결과 4종이다.
임의로 늘리거나 줄이지 않는다.
"""
from __future__ import annotations

import streamlit as st

from lib import api_client, components
from lib.formatting import SENTIMENT_DISPLAY, format_datetime, is_uncertain, truncate

components.page_setup("최근 리뷰 10개")

try:
    data = api_client.list_recent_reviews(limit=10, offset=0)
except api_client.ApiError as error:
    components.show_error(error)
    st.stop()

reviews = data["items"]
if not reviews:
    st.info("등록된 리뷰가 없습니다.")
    st.stop()


def _sentiment_text(review: dict) -> str:
    label = review.get("sentiment_label")
    if label is None:
        return "분석 실패"
    text = SENTIMENT_DISPLAY.get(label, (label,))[0]
    # 표 안에서는 배지 두 개가 좁으므로 저확신을 기호로 압축한다
    return f"{text} ⚠" if is_uncertain(review.get("confidence")) else text


st.dataframe(
    [
        {
            "영화 ID": review["movie_id"],
            "등록일": format_datetime(review["created_at"], "%m-%d %H:%M"),
            "리뷰 내용": truncate(review["content"], 40),
            "감성": _sentiment_text(review),
        }
        for review in reviews
    ],
    width='stretch',
    hide_index=True,
)

st.caption("⚠ 는 확신도가 낮아 판정이 애매한 예측입니다.")

st.divider()
st.markdown("##### 영화 상세로 이동")
movie_ids = sorted({review["movie_id"] for review in reviews})
columns = st.columns(min(len(movie_ids), 8))
for column, movie_id in zip(columns, movie_ids):
    with column:
        if st.button(f"ID {movie_id}", key=f"goto_{movie_id}", width='stretch'):
            # 페이지 전환은 query param을 비우므로 switch_page에 직접 넘겨야 한다
            st.switch_page("app.py", query_params={"movie_id": str(movie_id)})
