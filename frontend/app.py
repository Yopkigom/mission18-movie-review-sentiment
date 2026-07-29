"""홈 — 영화 목록과 상세를 query param으로 분기한다.

상세를 pages/에 두면 사이드바에 '영화를 고르지 않은 상세'라는 빈 화면이 남는다.
화면 식별을 URL에 두면 새로고침에도 상태가 유지되고 캡처·공유가 쉽다.
"""
from __future__ import annotations

import streamlit as st

from lib import api_client, components
from lib.formatting import rating_text, to_score_5

REVIEW_PAGE_SIZE = 10
GRID_COLUMNS = 4


def render_movie_list() -> None:
    st.subheader("영화 목록")

    try:
        data = api_client.list_movies(limit=100, offset=0)
    except api_client.ApiError as error:
        components.show_error(error)
        return

    movies = data["items"]
    if not movies:
        st.info("등록된 영화가 없습니다. 사이드바의 **영화 추가**에서 첫 영화를 등록해 보세요.")
        return

    for row_start in range(0, len(movies), GRID_COLUMNS):
        columns = st.columns(GRID_COLUMNS)
        for column, movie in zip(columns, movies[row_start:row_start + GRID_COLUMNS]):
            with column:
                components.movie_card(movie)


def render_movie_detail(movie_id: int) -> None:
    if st.button("← 목록으로"):
        st.query_params.clear()
        st.rerun()

    try:
        movie = api_client.get_movie(movie_id)
    except api_client.ApiError as error:
        components.show_error(error)
        if error.status_code == 404:
            st.query_params.clear()
        return

    poster_col, info_col = st.columns([1, 3])
    with poster_col:
        components.poster(movie.get("poster_url"))
    with info_col:
        st.header(movie["title"])
        meta = " · ".join(
            str(v) for v in (movie.get("release_date"), movie.get("director"),
                             movie.get("genre")) if v
        )
        st.caption(meta)

        # 평점 2종은 출처도 범위도 다르다. 이름을 붙여 나란히 표시한다
        st.markdown(
            f"**감성 평점** {rating_text(movie.get('sentiment_rating'), movie['review_count'])}"
        )
        external = movie.get("external_rating")
        st.markdown(
            f"**TMDB 평점** {external:.1f} / 10" if external is not None
            else "**TMDB 평점** 정보 없음"
        )

        if st.button("리뷰 쓰기", type="primary"):
            st.session_state["preselected_movie_id"] = movie_id
            st.switch_page("pages/2_리뷰_등록.py")

    st.divider()
    _render_reviews(movie_id, movie["review_count"])
    st.divider()
    _render_danger_zone(movie_id, movie["review_count"])


def _render_reviews(movie_id: int, review_count: int) -> None:
    st.subheader(f"리뷰 {review_count}건")
    if review_count == 0:
        st.info("아직 등록된 리뷰가 없습니다.")
        return

    state_key = f"review_page_{movie_id}"
    page = st.session_state.get(state_key, 1)

    try:
        data = api_client.list_movie_reviews(
            movie_id, limit=REVIEW_PAGE_SIZE, offset=(page - 1) * REVIEW_PAGE_SIZE
        )
    except api_client.ApiError as error:
        components.show_error(error)
        return

    total = data["total"]
    total_pages = max(1, -(-total // REVIEW_PAGE_SIZE))
    if page > total_pages:
        # 리뷰가 삭제되어 페이지가 사라진 경우 마지막 페이지로 되돌린다
        st.session_state[state_key] = total_pages
        st.rerun()

    for review in data["items"]:
        components.review_card(review)

    components.paginate(total, REVIEW_PAGE_SIZE, state_key)


def _render_danger_zone(movie_id: int, review_count: int) -> None:
    st.markdown("#### ⚠ 위험 구역")
    st.caption(f"이 영화를 삭제하면 리뷰 {review_count}건도 함께 삭제됩니다. 되돌릴 수 없습니다.")

    confirmed = st.checkbox("위 내용을 이해했습니다.", key=f"confirm_delete_{movie_id}")
    if st.button("영화 삭제", disabled=not confirmed, type="secondary"):
        try:
            api_client.delete_movie(movie_id)
        except api_client.ApiError as error:
            components.show_error(error)
            return
        api_client.clear_cache()
        st.query_params.clear()
        st.success("영화를 삭제했습니다.")
        st.rerun()


def main() -> None:
    components.page_setup("🎬 영화 리뷰 감성 분석")

    raw_id = st.query_params.get("movie_id")
    if raw_id is None:
        render_movie_list()
        return

    try:
        movie_id = int(raw_id)
    except (TypeError, ValueError):
        st.warning("잘못된 영화 ID입니다.")
        st.query_params.clear()
        render_movie_list()
        return

    render_movie_detail(movie_id)


main()
