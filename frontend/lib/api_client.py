"""백엔드 호출 · 오류 변환.

화면 코드에 HTTP 상태 코드 분기가 흩어지지 않도록, requests 예외와 4xx/5xx를
모두 ApiError로 바꾼다.
"""
from __future__ import annotations

import os
from typing import Any

import requests
import streamlit as st

# Cloud Run이 유휴 상태에서 깨어날 때 첫 요청이 느리다. 넉넉히 잡는다
TIMEOUT_SEC = (5, 60)   # (연결, 응답)


class ApiError(Exception):
    """화면이 사용자 메시지로 바꿔 쓰기 위한 예외."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def base_url() -> str:
    """st.secrets → 환경변수 순으로 읽는다. 하드코딩하지 않는다."""
    try:
        value = st.secrets["BACKEND_BASE_URL"]
    except Exception:
        value = os.getenv("BACKEND_BASE_URL", "http://localhost:8000")
    return str(value).rstrip("/")


def _request(method: str, path: str, **kwargs) -> Any:
    url = f"{base_url()}{path}"
    try:
        response = requests.request(method, url, timeout=TIMEOUT_SEC, **kwargs)
    except requests.Timeout as exc:
        raise ApiError("백엔드 응답이 지연되고 있습니다. 잠시 후 다시 시도해 주세요. (연결 시간 초과)") from exc
    except requests.ConnectionError as exc:
        raise ApiError("백엔드에 연결할 수 없습니다. 서버가 실행 중인지 확인해 주세요.") from exc
    except requests.RequestException as exc:
        raise ApiError(f"요청 처리 중 오류가 발생했습니다: {exc}") from exc

    if response.status_code >= 400:
        raise ApiError(_error_message(response), response.status_code)

    if response.status_code == 204 or not response.content:
        return None
    try:
        return response.json()
    except ValueError as exc:
        raise ApiError("백엔드 응답을 해석할 수 없습니다.") from exc


def _error_message(response: requests.Response) -> str:
    """FastAPI의 detail을 사용자 문구로 바꾼다. 422는 필드별 사유를 풀어 쓴다."""
    try:
        payload = response.json()
    except ValueError:
        return f"요청이 실패했습니다. (HTTP {response.status_code})"

    detail = payload.get("detail")
    if isinstance(detail, str):
        return detail
    if isinstance(detail, list):
        parts = []
        for item in detail:
            field = " → ".join(str(x) for x in item.get("loc", []) if x != "body")
            parts.append(f"{field}: {item.get('msg', '검증 실패')}")
        return "입력값을 확인해 주세요.\n" + "\n".join(parts)
    return f"요청이 실패했습니다. (HTTP {response.status_code})"


@st.cache_data(ttl=10, show_spinner=False)
def health() -> dict:
    return _request("GET", "/health")


@st.cache_data(ttl=10, show_spinner=False)
def list_movies(limit: int = 50, offset: int = 0) -> dict:
    return _request("GET", "/movies", params={"limit": limit, "offset": offset})


@st.cache_data(ttl=10, show_spinner=False)
def get_movie(movie_id: int) -> dict:
    return _request("GET", f"/movies/{movie_id}")


@st.cache_data(ttl=10, show_spinner=False)
def list_movie_reviews(movie_id: int, limit: int = 10, offset: int = 0) -> dict:
    return _request(
        "GET", f"/movies/{movie_id}/reviews", params={"limit": limit, "offset": offset}
    )


@st.cache_data(ttl=10, show_spinner=False)
def list_recent_reviews(limit: int = 10, offset: int = 0) -> dict:
    return _request("GET", "/reviews", params={"limit": limit, "offset": offset})


def create_movie(payload: dict) -> dict:
    return _request("POST", "/movies", json=payload)


def delete_movie(movie_id: int) -> None:
    _request("DELETE", f"/movies/{movie_id}")


def create_review(payload: dict) -> dict:
    return _request("POST", "/reviews", json=payload)


def clear_cache() -> None:
    """등록·삭제 직후 반드시 호출한다.

    방금 추가한 영화가 목록에 보이지 않으면 사용자는 저장이 실패했다고 판단한다.
    """
    for fn in (health, list_movies, get_movie, list_movie_reviews, list_recent_reviews):
        fn.clear()
