"""최근 리뷰 10개 (`심화` 요건).

표시 항목은 가이드가 지정한 영화 ID · 등록일 · 리뷰 내용 · 감성 분석 결과 4종이다.
임의로 늘리거나 줄이지 않는다.
"""
from __future__ import annotations

import streamlit as st

from lib import api_client, components
from lib.formatting import SENTIMENT_DISPLAY, format_datetime, is_uncertain, truncate

# 제목이 붙으면 버튼이 길어진다. 한 줄에 4개까지만 둔다
GOTO_COLUMNS = 4

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

# 표의 `영화 ID`만으로는 어떤 영화인지 알 수 없다. 제목을 함께 붙인다.
# 조회에 실패해도 이동 자체는 막지 않는다 — ID 표기로 물러선다
try:
    titles = {m["id"]: m["title"] for m in api_client.list_movies(limit=100)["items"]}
except api_client.ApiError:
    titles = {}

movie_ids = sorted({review["movie_id"] for review in reviews})
for row_start in range(0, len(movie_ids), GOTO_COLUMNS):
    columns = st.columns(GOTO_COLUMNS)
    for column, movie_id in zip(columns, movie_ids[row_start:row_start + GOTO_COLUMNS]):
        title = titles.get(movie_id)
        with column:
            label = f"ID {movie_id} · {title}" if title else f"ID {movie_id}"
            if st.button(label, key=f"goto_{movie_id}", width='stretch'):
                # 페이지 전환은 query param을 비우므로 switch_page에 직접 넘겨야 한다
                st.switch_page("app.py", query_params={"movie_id": str(movie_id)})
