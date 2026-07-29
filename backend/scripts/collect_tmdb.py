"""TMDB에서 영화 메타데이터를 수집한다 (로컬 1회 실행).

런타임에는 실행되지 않는다. 결과 JSON을 seed_db.py가 읽어 DB를 만들고,
배포 이미지에는 그 DB만 들어간다 — 서비스에 API 키가 필요 없다.

실행:
    TMDB_API_KEY=... python scripts/collect_tmdb.py
    (또는 backend/.env 에 TMDB_API_KEY=... 를 넣고 실행)

데이터 출처: The Movie Database (TMDB). 이 서비스는 TMDB API를 사용하지만
TMDB가 보증하지 않는다.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_PATH = BASE_DIR / "data" / "movies_tmdb.json"
IMAGE_BASE = "https://image.tmdb.org/t/p/w500"
API_BASE = "https://api.themoviedb.org/3"
REQUEST_INTERVAL_SEC = 0.3   # TMDB 레이트 리밋 회피
TIMEOUT_SEC = 10

# 시드 대상. NSMC가 한국 영화 리뷰 데이터셋이므로 한국 영화로 맞춘다.
# (제목, 개봉연도) — 동명 영화를 구분하기 위해 연도를 함께 준다
TARGET_MOVIES: list[tuple[str, int]] = [
    ("기생충", 2019),
    ("괴물", 2006),
    ("헤어질 결심", 2022),
    ("부산행", 2016),
    ("신세계", 2013),
    ("올드보이", 2003),
]


def _get(session: requests.Session, path: str, api_key: str, **params) -> dict:
    """TMDB GET 공통. 실패는 호출부가 판단하도록 예외를 올린다."""
    response = session.get(
        f"{API_BASE}{path}",
        params={"api_key": api_key, "language": "ko-KR", **params},
        timeout=TIMEOUT_SEC,
    )
    response.raise_for_status()
    time.sleep(REQUEST_INTERVAL_SEC)
    return response.json()


def search_movie_id(session: requests.Session, api_key: str, title: str, year: int) -> int | None:
    data = _get(session, "/search/movie", api_key, query=title, year=year)
    results = data.get("results") or []
    if not results:
        return None
    return int(results[0]["id"])


def extract_director(credits: dict) -> str | None:
    """감독은 /movie/{id}에 없다. credits의 crew에서 job == 'Director'를 뽑는다."""
    directors = [
        member.get("name")
        for member in credits.get("crew", [])
        if member.get("job") == "Director" and member.get("name")
    ]
    # 공동 연출이면 쉼표로 잇는다. 없으면 None을 그대로 남긴다
    return ", ".join(directors) if directors else None


def collect_one(session: requests.Session, api_key: str, title: str, year: int) -> dict | None:
    movie_id = search_movie_id(session, api_key, title, year)
    if movie_id is None:
        print(f"  [건너뜀] 검색 결과 없음: {title} ({year})")
        return None

    detail = _get(session, f"/movie/{movie_id}", api_key)
    credits = _get(session, f"/movie/{movie_id}/credits", api_key)

    poster_path = detail.get("poster_path")
    genres = [g["name"] for g in detail.get("genres", [])]

    return {
        "tmdb_id": movie_id,
        "title": detail.get("title") or title,
        "release_date": detail.get("release_date") or f"{year}-01-01",
        "director": extract_director(credits),
        "genre": ", ".join(genres) if genres else None,
        # poster_path가 null일 수 있다. URL만 저장하고 이미지는 내려받지 않는다
        "poster_url": f"{IMAGE_BASE}{poster_path}" if poster_path else None,
        "external_rating": detail.get("vote_average"),
    }


def main() -> int:
    load_dotenv(BASE_DIR / ".env")
    api_key = os.getenv("TMDB_API_KEY")
    if not api_key:
        print("TMDB_API_KEY가 없습니다. backend/.env에 넣거나 환경변수로 전달하세요.", file=sys.stderr)
        return 1

    collected: list[dict] = []
    with requests.Session() as session:
        for title, year in TARGET_MOVIES:
            print(f"수집 중: {title} ({year})")
            try:
                movie = collect_one(session, api_key, title, year)
            except requests.RequestException as exc:
                print(f"  [실패] {title}: {exc}", file=sys.stderr)
                continue
            if movie:
                collected.append(movie)
                print(f"  → id={movie['tmdb_id']} 감독={movie['director']} "
                      f"포스터={'있음' if movie['poster_url'] else '없음'}")

    if not collected:
        print("수집 결과가 비어 있습니다.", file=sys.stderr)
        return 1

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(collected, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n{len(collected)}편 저장 → {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
