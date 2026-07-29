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

# 주소창에 마지막으로 반영한 영화 ID. 아래 _sync_url 참고
URL_STATE_KEY = "_url_movie_id"
# rerun 뒤에 띄울 알림 문구
FLASH_KEY = "_flash_message"


def _write_url(movie_id: int | None) -> None:
    """현재 화면을 주소창에 반영한다. query param을 쓰는 유일한 지점이다."""
    if movie_id is None:
        st.query_params.clear()
    else:
        st.query_params["movie_id"] = str(movie_id)
    st.session_state[URL_STATE_KEY] = movie_id


def _navigate(movie_id: int | None) -> None:
    """상세(id) 또는 목록(None)으로 이동한다."""
    _write_url(movie_id)
    st.rerun()


def _sync_url(movie_id: int | None) -> None:
    """주소창이 실제 화면과 어긋나 있으면 되돌린다.

    사이드바 링크로 이 페이지에 돌아오면 Streamlit은 서버 쪽 query param만 비우고
    브라우저 주소창의 `movie_id`는 남겨 둔다. 그대로 두면 다음 클릭이 그 값을
    되살려, 목록에서 다른 영화를 눌러도 직전 영화의 상세가 다시 열린다.
    (클릭이 목록 화면까지 도달하지 못하고 상세 분기에서 가로채인다.)

    직접 쓴 값을 세션에 기억해 두고, 화면과 다를 때만 한 번 고쳐 쓴다.
    매번 쓰면 브라우저 history에 같은 주소가 계속 쌓인다.
    """
    if st.session_state.get(URL_STATE_KEY, movie_id) == movie_id:
        st.session_state[URL_STATE_KEY] = movie_id
        return
    _write_url(movie_id)


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
                if components.movie_card(movie):
                    _navigate(movie["id"])


def render_movie_detail(movie_id: int) -> None:
    if st.button("← 목록으로"):
        _navigate(None)

    try:
        movie = api_client.get_movie(movie_id)
    except api_client.ApiError as error:
        components.show_error(error)
        if error.status_code == 404:
            # 없는 영화를 가리키는 주소는 지운다. 오류 문구는 남겨 둔다
            _write_url(None)
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
    _render_danger_zone(movie_id, movie["review_count"], movie.get("deletable", True))


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


def _render_danger_zone(movie_id: int, review_count: int, deletable: bool) -> None:
    st.markdown("#### ⚠ 위험 구역")

    # 삭제 가능 여부는 백엔드가 판단해 내려준다. 화면이 스스로 정하지 않는다
    if not deletable:
        st.info(
            "이 영화는 **데모 시드 데이터**라 공개 배포본에서 삭제할 수 없습니다.\n\n"
            "삭제 기능은 직접 등록한 영화에서 확인할 수 있습니다. "
            "로컬 실행에서는 제한이 없습니다."
        )
        st.button("영화 삭제", disabled=True, type="secondary")
        return

    st.caption(f"이 영화를 삭제하면 리뷰 {review_count}건도 함께 삭제됩니다. 되돌릴 수 없습니다.")

    confirmed = st.checkbox("위 내용을 이해했습니다.", key=f"confirm_delete_{movie_id}")
    if st.button("영화 삭제", disabled=not confirmed, type="secondary"):
        try:
            api_client.delete_movie(movie_id)
        except api_client.ApiError as error:
            components.show_error(error)
            return
        api_client.clear_cache()
        # 알림은 다음 실행에서 띄운다. 지금 띄우면 곧바로 이어지는 rerun에 지워진다
        st.session_state[FLASH_KEY] = "영화를 삭제했습니다."
        _navigate(None)


def main() -> None:
    components.page_setup("영화 리뷰 감성 분석")

    flash = st.session_state.pop(FLASH_KEY, None)
    if flash:
        st.toast(flash)

    raw_id = st.query_params.get("movie_id")

    movie_id: int | None = None
    if raw_id is not None:
        try:
            movie_id = int(raw_id)
        except (TypeError, ValueError):
            st.warning("잘못된 영화 ID입니다.")
            _write_url(None)

    _sync_url(movie_id)

    if movie_id is None:
        render_movie_list()
        return

    render_movie_detail(movie_id)


main()
