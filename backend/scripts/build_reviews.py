"""NSMC 리뷰를 선별해 영화에 배정한다 (로컬 1회 실행).

⚠ NSMC는 영화별 리뷰가 아니라 네이버 영화 리뷰 20만 건의 모음이다.
   **리뷰와 영화의 대응은 임의 배정**이며 실제 관람평이 아니다. 보고서에 명시한다.

NSMC 필드는 `id / document / label`뿐이라 제목 · 작성자 · 등록일은 여기서 파생 생성한다.

실행:
    python scripts/build_reviews.py
"""
from __future__ import annotations

import json
import random
import re
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from app.config import settings  # noqa: E402
from app.ml.loader import load_model  # noqa: E402
from app.ml.predictor import predict  # noqa: E402

NSMC_PATH = Path("/mnt/wsl_data/datasets/nsmc/ratings_train.txt")
MOVIES_PATH = BASE_DIR / "data" / "movies_tmdb.json"
OUTPUT_PATH = BASE_DIR / "data" / "reviews_seed.json"

SEED = 42
REVIEWS_PER_MOVIE = 12        # 캡처 요건은 영화당 10건 이상
POOL_SIZE = 30000            # 큐레이션용 후보 표본 크기
MIN_LEN, MAX_LEN = 15, 140    # 너무 짧으면 판단 근거가 없고, NSMC 상한은 140자
CONFIDENT = 0.90              # 확신 있는 예측 기준 (model-eval.md C-b 실측 근거)
UNCERTAIN_MIN = 0.55          # 저확신 표본의 하한 — 이보다 낮으면 예측이 사실상 무작위다

# 영화별 감성 구성.
#
# 모든 영화에 같은 비율을 주면 평균이 전부 같은 값이 되어 화면에서 평점 차이가
# 드러나지 않는다. TMDB 평점이 높은 작품일수록 긍정을 많이 배정해 순서를 맞춘다.
# (리뷰-영화 대응이 임의 배정이므로 이 배분 자체도 연출이며, 보고서에 명시한다.)
#
# `저확신`은 정답과 일치하되 confidence가 낮은 표본이다. 이것이 없으면
# `판정 애매` 표기 기능을 화면으로 증명할 수 없다. 오분류를 섞는 것과는 다르다.
PROFILES: dict[str, dict[str, int]] = {
    "기생충":     {"긍정": 8, "중립": 1, "부정": 1, "저확신": 2},
    "올드보이":   {"긍정": 7, "중립": 2, "부정": 1, "저확신": 2},
    "부산행":     {"긍정": 6, "중립": 2, "부정": 2, "저확신": 2},
    "신세계":     {"긍정": 5, "중립": 2, "부정": 3, "저확신": 2},
    "헤어질 결심": {"긍정": 4, "중립": 3, "부정": 3, "저확신": 2},
    "괴물":       {"긍정": 3, "중립": 2, "부정": 5, "저확신": 2},
}
# 프로필에 없는 영화가 들어오면 균등 배분으로 처리한다
DEFAULT_PROFILE = {"긍정": 5, "중립": 2, "부정": 3, "저확신": 2}
BUCKETS = ("긍정", "중립", "부정", "저확신")


# 리뷰-영화 대응이 임의 배정이므로, **어느 영화에 붙어도 어색하지 않은 리뷰**만 고른다.
# 배우 이름이나 다른 작품이 언급된 리뷰가 섞이면 화면을 보는 사람이 먼저
# "데이터가 깨졌나"로 읽는다. 명시해 두는 것만으로는 그 인상을 막지 못한다.

# 일반적인 평가 어휘. 최소 하나는 있어야 리뷰로서 의미가 있다
EVALUATIVE_WORDS = (
    "재미", "재밌", "재미없", "연기", "연출", "스토리", "지루", "감동", "추천",
    "최고", "별로", "실망", "명작", "졸작", "볼만", "아깝", "몰입", "전개",
    "구성", "각본", "장면", "영상", "음악", "결말", "배우", "웃기", "감명",
    "훌륭", "괜찮", "그저", "평범", "지겹", "훈훈", "탄탄", "어색", "지루함",
)

# 특정 작품·인물을 가리키는 신호. 하나라도 걸리면 제외한다
SPECIFIC_PATTERNS = re.compile(
    r"[A-Za-z]"                      # 영문 (CSI, TV, OST 등 외부 고유명사)
    r"|[0-9]"                        # 숫자 (편수·연도·회차 언급)
    r"|짱"                            # '한지민 짱' 류의 인물 호명
    r"|[가-힣]{2,4}(?:님|씨|배우|감독|작가)"   # 인물 지칭
    r"|원작|속편|시즌|드라마판|만화|소설|리메이크"  # 다른 매체·작품 언급
    r"|주연|출연|캐스팅"                 # 특정 캐스팅 언급
    r"|본방|방송|시청률|재방|종영|채널|회차|프로그램|다큐"  # TV 언급 (NSMC에는 드라마 평도 섞여 있다)
    r"|애니메이션|애니"                  # 장르 언급 — 실사 영화에 붙으면 어긋난다
    r"|중국|일본|홍콩|헐리|할리우드|외국영화"     # 제작국 언급 — 배정된 영화와 어긋난다
    # 자주 등장해 빈도 필터를 통과하는 유명인 이름. 일반화할 수 없어 목록으로 둔다
    r"|견자단|성룡|이연걸|주성치|장동건|송강호|하정우|마동석"
)


# 희귀 어절 판정 기준. 말뭉치 5만 건에서 이보다 드물게 나오는 어절은
# 인명·작품명 같은 고유명사일 가능성이 높다(사이먼래틀 · 엄석대 · 하이바라 …).
# 접미사 규칙만으로는 이런 이름을 걸러낼 수 없어 빈도 통계를 쓴다.
MIN_DOC_FREQ = 40
_TOKEN = re.compile(r"[가-힣]+")


def build_document_freq(rows: list[dict]) -> Counter:
    """어절 단위 문서 빈도. 형태소 분석기 없이 표준 라이브러리만 쓴다."""
    freq: Counter = Counter()
    for row in rows:
        freq.update(set(_TOKEN.findall(row["document"])))
    return freq


def is_generic(text: str, doc_freq: Counter) -> bool:
    """어느 영화에 붙여도 자연스러운 일반 평가문인지 판단한다."""
    if SPECIFIC_PATTERNS.search(text):
        return False
    if not any(word in text for word in EVALUATIVE_WORDS):
        return False
    # 희귀 어절이 하나라도 있으면 특정 작품·인물을 가리킬 가능성이 크다
    return all(doc_freq[token] >= MIN_DOC_FREQ for token in _TOKEN.findall(text))


def load_nsmc(path: Path) -> list[dict]:
    """NSMC 원본(TSV)을 읽는다. pandas 없이 표준 라이브러리로 처리한다."""
    rows: list[dict] = []
    with path.open(encoding="utf-8") as f:
        header = f.readline()
        if not header.startswith("id\tdocument\tlabel"):
            raise ValueError(f"NSMC 형식이 아닙니다: {path}")
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 3 or not parts[1].strip():
                continue
            rows.append({"id": parts[0], "document": parts[1], "label": int(parts[2])})
    return rows


def derive_title(content: str) -> str:
    """리뷰 본문에서 제목을 파생 생성한다.

    NSMC에는 제목이 없다. 첫 문장(또는 앞부분)을 잘라 제목으로 쓰고,
    길면 말줄임한다. 원문을 변형하지는 않는다.
    """
    first = re.split(r"[.!?~\n]", content.strip(), maxsplit=1)[0].strip()
    if not first:
        first = content.strip()
    return first if len(first) <= 25 else first[:24].rstrip() + "…"


def build_pool(rows: list[dict], bundle, need: dict[str, int],
               rng: random.Random) -> dict[str, list[dict]]:
    """후보 표본을 감성별로 나눈다.

    긍정·부정은 NSMC 정답 라벨과 모델 예측이 **둘 다 일치**하는 것만 쓴다.
    시드 데이터에서까지 오분류를 섞으면 화면 캡처의 신뢰도가 떨어진다.
    중립은 NSMC에 정답이 없으므로 모델 예측으로만 선별한다.
    저확신 버킷도 정답과 일치하는 것만 쓴다 — 표기 기능을 보이려는 것이지
    틀린 예측을 보이려는 것이 아니다.
    """
    doc_freq = build_document_freq(rows)

    # NSMC에는 같은 문장이 다른 id로 여러 번 들어 있다. 그대로 두면
    # 동일한 리뷰가 서로 다른 영화에 배정돼 화면에서 눈에 띈다
    seen: set[str] = set()
    candidates = []
    for r in rows:
        text = r["document"]
        if not (MIN_LEN <= len(text) <= MAX_LEN) or text in seen:
            continue
        if is_generic(text, doc_freq):
            seen.add(text)
            candidates.append(r)
    rng.shuffle(candidates)
    print(f"일반 평가문 후보: {len(candidates):,}건 (전체 {len(rows):,}건 중)")

    buckets: dict[str, list[dict]] = {k: [] for k in BUCKETS}

    for row in candidates[:POOL_SIZE]:
        if all(len(buckets[k]) >= need[k] for k in BUCKETS):
            break
        try:
            result = predict(bundle, row["document"])
        except ValueError:
            continue

        gold = {0: "부정", 1: "긍정"}[row["label"]]
        item = {**row, "result": result}

        if result.confidence < CONFIDENT:
            # 정답과 일치하는 저확신 예측만 담는다
            if (UNCERTAIN_MIN <= result.confidence and result.label == gold
                    and len(buckets["저확신"]) < need["저확신"]):
                buckets["저확신"].append(item)
        elif result.label == "중립":
            # 중립은 정답이 없으므로 확신 있는 예측만 채택한다
            if len(buckets["중립"]) < need["중립"]:
                buckets["중립"].append(item)
        elif result.label == gold and len(buckets[result.label]) < need[result.label]:
            buckets[result.label].append(item)

    return buckets


def main() -> int:
    if not NSMC_PATH.exists():
        print(f"NSMC 원본이 없습니다: {NSMC_PATH}", file=sys.stderr)
        return 1
    if not MOVIES_PATH.exists():
        print(f"영화 메타데이터가 없습니다: {MOVIES_PATH}\n"
              "먼저 scripts/collect_tmdb.py를 실행하세요.", file=sys.stderr)
        return 1

    rng = random.Random(SEED)
    movies = json.loads(MOVIES_PATH.read_text(encoding="utf-8"))
    rows = load_nsmc(NSMC_PATH)
    print(f"NSMC {len(rows):,}건 로드 / 영화 {len(movies)}편")

    profiles = [PROFILES.get(m["title"], DEFAULT_PROFILE) for m in movies]
    need = {k: sum(p.get(k, 0) for p in profiles) for k in BUCKETS}
    print("필요 수량:", need)

    bundle = load_model(settings.ml_assets_dir, settings.model_version)
    buckets = build_pool(rows, bundle, need, rng)
    print("후보 확보:", {k: len(v) for k, v in buckets.items()})

    for label, count in need.items():
        if len(buckets[label]) < count:
            print(f"경고: {label} 후보 부족 ({len(buckets[label])}/{count}건) — "
                  "POOL_SIZE를 늘리거나 프로필을 조정하세요.", file=sys.stderr)

    now = datetime.now().replace(microsecond=0)
    reviews: list[dict] = []
    cursor = {k: 0 for k in BUCKETS}
    author_no = 1

    for movie_index, (movie, profile) in enumerate(zip(movies, profiles)):
        picked: list[dict] = []
        for label, count in profile.items():
            take = buckets[label][cursor[label]:cursor[label] + count]
            cursor[label] += len(take)
            picked.extend(take)
        rng.shuffle(picked)

        for order, item in enumerate(picked):
            result = item["result"]
            # 등록일은 최신순 정렬이 눈에 보이도록 분 단위로 흩는다
            created = now - timedelta(
                minutes=movie_index * 137 + order * 41 + rng.randint(0, 20)
            )
            reviews.append({
                "tmdb_id": movie["tmdb_id"],
                "author": f"익명{author_no}",
                "title": derive_title(item["document"]),
                "content": item["document"],
                "created_at": created.isoformat(timespec="seconds"),
                "nsmc_id": item["id"],
                "nsmc_label": item["label"],
                "expected_label": result.label,
                "expected_confidence": round(result.confidence, 4),
            })
            author_no += 1

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps(reviews, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    dist = Counter(r["expected_label"] for r in reviews)
    uncertain = sum(1 for r in reviews if r["expected_confidence"] < CONFIDENT)
    print(f"\n리뷰 {len(reviews)}건 저장 → {OUTPUT_PATH}")
    print(f"영화당 {REVIEWS_PER_MOVIE}건 / 감성 분포: {dict(dist)} / 저확신 {uncertain}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
