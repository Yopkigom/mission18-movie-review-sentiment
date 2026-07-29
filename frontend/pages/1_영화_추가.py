"""영화 추가 화면 (필수 요건)."""
from __future__ import annotations

from datetime import date

import streamlit as st

from lib import api_client, components

components.page_setup("영화 추가")

# 포스터 미리보기는 폼 밖에 둔다 — 폼 안에서는 제출 전까지 값이 반영되지 않는다
preview_url = st.text_input(
    "포스터 URL", key="poster_url_input",
    placeholder="https://image.tmdb.org/t/p/w500/...",
    help="URL만 저장한다. 이미지 파일은 서버에 복사하지 않는다.",
)
if preview_url:
    st.caption("미리보기")
    st.image(preview_url, width=180)

with st.form("movie_form"):
    title = st.text_input("제목 *", max_chars=200)

    left, right = st.columns(2)
    with left:
        release_date = st.date_input(
            "개봉일 *", value=date(2020, 1, 1),
            min_value=date(1900, 1, 1), max_value=date.today(),
        )
        genre = st.text_input("장르", max_chars=100, placeholder="드라마")
    with right:
        director = st.text_input("감독", max_chars=100)
        external_rating = st.number_input(
            "TMDB 평점 (0~10)", min_value=0.0, max_value=10.0, value=0.0, step=0.1,
            help="리뷰 기반 감성 평점과는 별개 필드다. 모르면 비워 둔다(0 입력 시 미저장).",
        )

    submitted = st.form_submit_button("등록", type="primary")

if submitted:
    if not title.strip():
        st.error("제목을 입력해 주세요.")
    else:
        payload = {
            "title": title.strip(),
            "release_date": release_date.isoformat(),
            "director": director.strip() or None,
            "genre": genre.strip() or None,
            "poster_url": preview_url.strip() or None,
            "external_rating": external_rating if external_rating > 0 else None,
        }
        try:
            movie = api_client.create_movie(payload)
        except api_client.ApiError as error:
            components.show_error(error)
        else:
            # 방금 등록한 영화가 목록에 없으면 저장 실패로 오해한다
            api_client.clear_cache()
            st.success(f"'{movie['title']}'을(를) 등록했습니다.")
            st.page_link("app.py", label="영화 목록으로 이동")
