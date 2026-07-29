"""리뷰 등록 화면 (`심화` 요건).

영화 선택 UI를 갖춘 독립 화면 하나만 두고, 상세에서 진입하면 선택값을 미리 채운다.
"""
from __future__ import annotations

import streamlit as st

from lib import api_client, components
from lib.formatting import badge_html, is_uncertain

if components.page_setup("리뷰 등록"):
    # 지난 등록 결과가 새로 들어온 화면에 남아 있으면 방금 등록한 것으로 오해한다
    st.session_state.pop("last_review", None)

try:
    movies = api_client.list_movies(limit=100, offset=0)["items"]
except api_client.ApiError as error:
    components.show_error(error)
    st.stop()

if not movies:
    st.info("등록된 영화가 없습니다. 먼저 영화를 추가해 주세요.")
    st.page_link("pages/1_영화_추가.py", label="영화 추가로 이동")
    st.stop()

# 상세 화면에서 넘어온 경우 해당 영화를 미리 선택한다
preselected = st.session_state.pop("preselected_movie_id", None)
options = [m["id"] for m in movies]
labels = {m["id"]: m["title"] for m in movies}
default_index = options.index(preselected) if preselected in options else 0

with st.form("review_form"):
    movie_id = st.selectbox(
        "영화 *", options=options, index=default_index,
        format_func=lambda mid: labels[mid],
    )
    author = st.text_input("작성자 *", max_chars=50)
    title = st.text_input("제목", max_chars=200)
    content = st.text_area("내용 *", max_chars=2000, height=160)
    submitted = st.form_submit_button("등록", type="primary")

if submitted:
    if not author.strip() or not content.strip():
        st.error("작성자와 내용은 필수입니다.")
        st.stop()

    payload = {
        "movie_id": int(movie_id),
        "author": author.strip(),
        "title": title.strip() or None,
        "content": content.strip(),
    }
    try:
        review = api_client.create_review(payload)
    except api_client.ApiError as error:
        components.show_error(error)
        st.stop()

    api_client.clear_cache()
    st.session_state["last_review"] = review

# 등록 결과는 rerun 이후에도 남도록 세션에서 읽어 그린다
review = st.session_state.get("last_review")
if review:
    st.divider()
    with st.container(border=True):
        st.markdown("#### 감성 분석 결과")

        if review.get("sentiment_label") is None:
            st.warning(
                "리뷰는 저장되었으나 감성 분석에 실패했습니다. 이 리뷰는 평점에 반영되지 않습니다."
            )
        else:
            st.markdown(
                badge_html(review["sentiment_label"], review.get("confidence")),
                unsafe_allow_html=True,
            )
            confidence = review.get("confidence")
            if confidence is not None:
                st.caption(f"확신도 {confidence:.2f}")
                if is_uncertain(confidence):
                    st.caption("확신도가 낮아 판정이 애매합니다. 모델 판단은 그대로 표시합니다.")
            st.write(f"이 리뷰는 **{labels.get(review['movie_id'], '해당 영화')}**의 평점에 반영되었습니다.")

        st.page_link("app.py", label="영화 목록으로 이동")
