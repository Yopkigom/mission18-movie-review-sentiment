"""공통 UI 요소 — 사이드바 · 포스터 카드 · 리뷰 카드 · 페이지네이션."""
from __future__ import annotations

import streamlit as st

from . import api_client
from .formatting import badge_html, format_datetime, rating_text

# 포스터 로드 실패 시 대체 표시. 레이아웃이 무너지지 않도록 2:3 비율을 유지한다
_PLACEHOLDER = (
    "<div style='width:100%;aspect-ratio:2/3;background:#e8eaed;border-radius:6px;"
    "display:flex;align-items:center;justify-content:center;text-align:center;"
    "color:#5f6368;font-size:0.85rem;padding:8px;'>이미지<br/>없음</div>"
)

# 직전 실행이 어느 화면이었는지 기억한다. 화면 진입 감지에만 쓴다
_CURRENT_PAGE_KEY = "_current_page"

TMDB_NOTICE = (
    "이 서비스는 TMDB API를 사용하지만 TMDB가 보증하지 않습니다.\n\n"
    "리뷰는 NSMC 공개 데이터셋에서 가져와 영화에 **임의 배정**한 것으로, "
    "실제 해당 영화의 관람평이 아닙니다."
)


def page_setup(title: str) -> bool:
    """공통 셋업. 다른 화면에서 막 들어온 실행이면 True를 돌려준다.

    세션 상태는 화면을 옮겨도 남는다. 직전 화면에서 만든 일회성 결과(등록 결과 등)를
    새로 들어온 화면에 그대로 띄우지 않으려면 진입 시점을 구분해야 한다.
    """
    st.set_page_config(page_title="영화 리뷰 감성 분석", page_icon="🎬", layout="wide")
    entered = st.session_state.get(_CURRENT_PAGE_KEY) != title
    st.session_state[_CURRENT_PAGE_KEY] = title
    render_sidebar()
    st.title(title)
    return entered


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### 영화 리뷰 감성 분석")
        st.page_link("app.py", label="영화 목록")
        st.page_link("pages/1_영화_추가.py", label="영화 추가")
        st.page_link("pages/2_리뷰_등록.py", label="리뷰 등록")
        st.page_link("pages/3_최근_리뷰.py", label="최근 리뷰")

        st.divider()
        st.caption("**데이터 출처 — TMDB API**")
        st.caption(TMDB_NOTICE)

        _render_model_status()


def _render_model_status() -> None:
    """모델이 내려가 있으면 화면에 미리 알린다. 리뷰 등록 후 당황하지 않도록."""
    try:
        status = api_client.health()
    except api_client.ApiError:
        return
    if not status.get("model_loaded"):
        st.warning("감성 분석 모델이 로드되지 않았습니다. 리뷰는 저장되지만 감성 분석은 생략됩니다.")


def show_error(error: Exception) -> None:
    st.error(f"⚠ {error}")


def poster(url: str | None) -> None:
    if url:
        st.image(url, width='stretch')
    else:
        st.markdown(_PLACEHOLDER, unsafe_allow_html=True)


def movie_card(movie: dict) -> bool:
    """목록 카드. 눌렸는지만 돌려주고 화면 전환은 호출 측이 맡는다.

    URL(query param)을 쓰는 지점을 app.py 한 곳으로 모으기 위한 분리다.
    """
    poster(movie.get("poster_url"))
    st.markdown(f"**{movie['title']}**")
    st.caption(rating_text(movie.get("sentiment_rating"), movie.get("review_count", 0)))
    return st.button("상세 보기", key=f"movie_{movie['id']}", width='stretch')


def review_card(review: dict) -> None:
    """리뷰 카드 — 제목 · 감성 배지 · 작성자 · 등록일 · 내용 순."""
    with st.container(border=True):
        head, badge = st.columns([3, 1])
        with head:
            st.markdown(f"**{review.get('title') or '(제목 없음)'}**")
        with badge:
            st.markdown(
                badge_html(review.get("sentiment_label"), review.get("confidence")),
                unsafe_allow_html=True,
            )
        st.caption(f"{review['author']} · {format_datetime(review['created_at'])}")
        st.write(review["content"])


def paginate(total: int, page_size: int, state_key: str) -> int:
    """페이지 이동 UI. 현재 offset을 돌려준다.

    페이지 번호는 세션 상태(휘발성 UI 상태)로 관리한다.
    """
    total_pages = max(1, -(-total // page_size))
    page = st.session_state.get(state_key, 1)
    page = min(max(1, page), total_pages)

    prev_col, label_col, next_col = st.columns([1, 2, 1])
    with prev_col:
        if st.button("‹ 이전", disabled=page <= 1, key=f"{state_key}_prev",
                     width='stretch'):
            st.session_state[state_key] = page - 1
            st.rerun()
    with label_col:
        st.markdown(
            f"<div style='text-align:center;padding-top:6px;'>{page} / {total_pages} 페이지</div>",
            unsafe_allow_html=True,
        )
    with next_col:
        if st.button("다음 ›", disabled=page >= total_pages, key=f"{state_key}_next",
                     width='stretch'):
            st.session_state[state_key] = page + 1
            st.rerun()

    st.session_state[state_key] = page
    return (page - 1) * page_size
