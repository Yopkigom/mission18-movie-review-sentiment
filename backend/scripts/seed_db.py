"""시드 SQLite를 생성한다 (로컬 1회 실행).

적재 시점에 감성 분석을 수행해 결과까지 저장한다. 런타임에 시드 리뷰를
다시 추론하지 않는다.

실행:
    python scripts/seed_db.py [--force]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.config import settings  # noqa: E402
from app.database import Base, SessionLocal, engine  # noqa: E402
from app.ml.loader import load_model  # noqa: E402
from app.ml.predictor import predict  # noqa: E402
from app.models import Movie, Review  # noqa: E402

MOVIES_PATH = BASE_DIR / "data" / "movies_tmdb.json"
REVIEWS_PATH = BASE_DIR / "data" / "reviews_seed.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="시드 DB 생성")
    parser.add_argument(
        "--force", action="store_true", help="기존 테이블을 비우고 다시 적재한다"
    )
    args = parser.parse_args()

    for path in (MOVIES_PATH, REVIEWS_PATH):
        if not path.exists():
            print(f"입력 파일이 없습니다: {path}", file=sys.stderr)
            return 1

    movies_data = json.loads(MOVIES_PATH.read_text(encoding="utf-8"))
    reviews_data = json.loads(REVIEWS_PATH.read_text(encoding="utf-8"))

    Base.metadata.create_all(bind=engine)
    session = SessionLocal()

    try:
        existing = session.query(Movie).count()
        if existing and not args.force:
            print(f"이미 영화 {existing}편이 있습니다. 다시 적재하려면 --force를 주세요.",
                  file=sys.stderr)
            return 1
        if args.force:
            # 리뷰는 CASCADE로 함께 지워지지만, 순서를 명시해 의도를 남긴다
            session.query(Review).delete()
            session.query(Movie).delete()
            session.commit()

        bundle = load_model(settings.ml_assets_dir, settings.model_version)

        tmdb_to_id: dict[int, int] = {}
        for item in movies_data:
            movie = Movie(
                tmdb_id=item["tmdb_id"],
                title=item["title"],
                release_date=date.fromisoformat(item["release_date"]),
                director=item.get("director"),
                genre=item.get("genre"),
                poster_url=item.get("poster_url"),
                external_rating=item.get("external_rating"),
            )
            session.add(movie)
            session.flush()
            tmdb_to_id[item["tmdb_id"]] = movie.id
        session.commit()
        print(f"영화 {len(tmdb_to_id)}편 적재")

        analyzed = failed = 0
        for item in reviews_data:
            movie_id = tmdb_to_id.get(item["tmdb_id"])
            if movie_id is None:
                print(f"  [건너뜀] 대응 영화 없음: tmdb_id={item['tmdb_id']}", file=sys.stderr)
                continue

            review = Review(
                movie_id=movie_id,
                author=item["author"],
                title=item.get("title"),
                content=item["content"],
                created_at=datetime.fromisoformat(item["created_at"]),
            )
            try:
                result = predict(bundle, item["content"])
                review.sentiment_label = result.label
                review.sentiment_score = result.score
                review.confidence = result.confidence
                review.model_version = result.model_version
                analyzed += 1
            except Exception as exc:
                # 시드 단계의 추론 실패는 치명적이지 않다. 감성 null로 남긴다
                print(f"  [추론 실패] {exc}", file=sys.stderr)
                failed += 1
            session.add(review)

        session.commit()
        print(f"리뷰 {analyzed + failed}건 적재 (감성 분석 성공 {analyzed} / 실패 {failed})")
        print(f"DB → {settings.database_url}")
        return 0

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
