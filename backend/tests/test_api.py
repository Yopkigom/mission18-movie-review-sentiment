"""엔드포인트별 상태 코드 · 페이지네이션 경계 · 삭제 연쇄 검증 (G-c)."""
from __future__ import annotations


def _create_movie(client, payload: dict) -> int:
    response = client.post("/movies", json=payload)
    assert response.status_code == 201
    return response.json()["id"]


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    # 테스트는 lifespan 모델 로드를 타지 않는다
    assert "model_loaded" in body


def test_create_and_get_movie(client, movie_payload):
    movie_id = _create_movie(client, movie_payload)

    body = client.get(f"/movies/{movie_id}").json()
    assert body["title"] == movie_payload["title"]
    assert body["external_rating"] == 7.5
    # 리뷰가 없으면 평점은 null이다. 0(중립)으로 바꾸지 않는다
    assert body["sentiment_rating"] is None
    assert body["review_count"] == 0


def test_duplicate_movie_returns_409(client, movie_payload):
    _create_movie(client, movie_payload)
    assert client.post("/movies", json=movie_payload).status_code == 409

    # tmdb_id가 달라도 (제목, 개봉일)이 같으면 중복이다
    other = {**movie_payload, "tmdb_id": 999999}
    assert client.post("/movies", json=other).status_code == 409


def test_missing_movie_returns_404(client):
    assert client.get("/movies/9999").status_code == 404
    assert client.delete("/movies/9999").status_code == 404
    assert client.get("/movies/9999/rating").status_code == 404
    assert client.get("/movies/9999/reviews").status_code == 404


def test_invalid_payload_returns_422(client):
    assert client.post("/movies", json={"title": ""}).status_code == 422
    assert client.post(
        "/reviews", json={"movie_id": 1, "author": "", "content": ""}
    ).status_code == 422


def test_review_on_missing_movie_returns_404(client):
    response = client.post(
        "/reviews", json={"movie_id": 4242, "author": "익명", "content": "내용"}
    )
    assert response.status_code == 404


def test_review_created_even_without_model(client, movie_payload):
    """모델 미로드 상태에서도 리뷰 저장은 성공하고 감성 필드만 null이다."""
    movie_id = _create_movie(client, movie_payload)
    response = client.post(
        "/reviews",
        json={"movie_id": movie_id, "author": "익명1", "content": "재미있게 봤습니다."},
    )
    assert response.status_code == 201

    body = response.json()
    assert body["sentiment_label"] is None
    assert body["sentiment_score"] is None

    # 감성 null 리뷰는 평균에서 제외된다 — 리뷰는 1건이지만 평점은 여전히 null이다
    rating = client.get(f"/movies/{movie_id}/rating").json()
    assert rating["review_count"] == 1
    assert rating["analyzed_count"] == 0
    assert rating["sentiment_rating"] is None


def test_pagination_boundaries(client, movie_payload):
    movie_id = _create_movie(client, movie_payload)

    empty = client.get(f"/movies/{movie_id}/reviews?limit=10&offset=0").json()
    assert empty["total"] == 0 and empty["items"] == []

    for i in range(11):
        client.post(
            "/reviews",
            json={"movie_id": movie_id, "author": f"익명{i}", "content": f"리뷰 {i}"},
        )

    first = client.get(f"/movies/{movie_id}/reviews?limit=10&offset=0").json()
    assert first["total"] == 11 and len(first["items"]) == 10

    second = client.get(f"/movies/{movie_id}/reviews?limit=10&offset=10").json()
    assert len(second["items"]) == 1

    beyond = client.get(f"/movies/{movie_id}/reviews?limit=10&offset=20").json()
    assert beyond["items"] == [] and beyond["total"] == 11

    # 정렬은 created_at DESC, id DESC — 마지막에 넣은 리뷰가 첫 항목이다
    assert first["items"][0]["id"] > first["items"][1]["id"]

    assert client.get(f"/movies/{movie_id}/reviews?limit=0").status_code == 422


def test_recent_reviews_default_limit_is_10(client, movie_payload):
    movie_id = _create_movie(client, movie_payload)
    for i in range(12):
        client.post(
            "/reviews",
            json={"movie_id": movie_id, "author": f"익명{i}", "content": f"리뷰 {i}"},
        )

    body = client.get("/reviews").json()
    assert len(body["items"]) == 10 and body["total"] == 12


def test_delete_movie_cascades_reviews(client, movie_payload):
    """PRAGMA foreign_keys=ON이 걸려 있지 않으면 이 테스트가 실패한다."""
    movie_id = _create_movie(client, movie_payload)
    for i in range(3):
        client.post(
            "/reviews",
            json={"movie_id": movie_id, "author": f"익명{i}", "content": f"리뷰 {i}"},
        )
    assert client.get("/reviews").json()["total"] == 3

    assert client.delete(f"/movies/{movie_id}").status_code == 204
    assert client.get(f"/movies/{movie_id}").status_code == 404
    assert client.get("/reviews").json()["total"] == 0


def test_delete_review(client, movie_payload):
    movie_id = _create_movie(client, movie_payload)
    review_id = client.post(
        "/reviews", json={"movie_id": movie_id, "author": "익명", "content": "리뷰"}
    ).json()["id"]

    assert client.delete(f"/reviews/{review_id}").status_code == 204
    assert client.delete(f"/reviews/{review_id}").status_code == 404


def test_sentiment_endpoint_returns_503_without_model(client):
    """모델 미로드 시 감성 전용 엔드포인트는 503이다."""
    response = client.post("/sentiment/analyze", json={"text": "재미있다"})
    assert response.status_code == 503


def test_openapi_documents_every_route(client):
    """/docs 렌더링 근거. 모든 경로에 summary가 채워져 있어야 한다."""
    spec = client.get("/openapi.json").json()
    for path, methods in spec["paths"].items():
        for method, operation in methods.items():
            assert operation.get("summary"), f"summary 누락: {method.upper()} {path}"
            assert operation.get("description"), f"description 누락: {method.upper()} {path}"


def test_seed_protection_blocks_delete(client, movie_payload, monkeypatch):
    """PROTECT_SEED가 켜지면 시드 데이터 삭제가 403으로 막힌다."""
    import dataclasses

    from app import config
    from tests.conftest import _mark_as_seed

    seed_id = _create_movie(client, movie_payload)
    normal_id = _create_movie(
        client, {**movie_payload, "title": "사용자 등록 영화", "tmdb_id": None}
    )
    # 시드 표시는 실제로는 seed_db.py가 한다
    _mark_as_seed(client, seed_id)

    monkeypatch.setattr(
        config, "settings", dataclasses.replace(config.settings, protect_seed=True)
    )

    # 시드 영화는 막히고
    assert client.delete(f"/movies/{seed_id}").status_code == 403
    # 시드 영화의 리뷰도 막힌다 (하나씩 지워 같은 결과를 만들 수 없게)
    review_id = client.post(
        "/reviews", json={"movie_id": seed_id, "author": "익명", "content": "리뷰"}
    ).json()["id"]
    assert client.delete(f"/reviews/{review_id}").status_code == 403

    # 직접 등록한 영화는 그대로 삭제된다 — 필수 기능은 배포본에서도 시연 가능하다
    assert client.delete(f"/movies/{normal_id}").status_code == 204

    # 조회 응답이 삭제 가능 여부를 함께 알려준다
    assert client.get(f"/movies/{seed_id}").json()["deletable"] is False


def test_seed_deletable_when_protection_off(client, movie_payload):
    """로컬 실행(기본값)에서는 시드도 삭제된다."""
    from tests.conftest import _mark_as_seed

    movie_id = _create_movie(client, movie_payload)
    _mark_as_seed(client, movie_id)

    assert client.get(f"/movies/{movie_id}").json()["deletable"] is True
    assert client.delete(f"/movies/{movie_id}").status_code == 204
