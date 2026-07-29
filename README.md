# 영화 리뷰 감성 분석 웹 서비스

코드잇 K-DT AI 엔지니어 10기 스프린트 미션 18 제출물 — **3팀 신호정**

Streamlit(프론트엔드) · FastAPI(백엔드) · ONNX 감성 분석 모델 서빙으로 구성한 3-tier 웹 서비스다.
영화를 등록·조회·삭제하고, 리뷰를 등록하면 **감성 분석이 자동 실행되어 평점에 반영**된다.

```
[Streamlit]  ──HTTPS/REST──>  [FastAPI]  ──>  [SQLite: 영화 / 리뷰]
   화면만                      데이터 소유          │
                                            [ONNX 감성 분석 모델]
```

모든 데이터는 백엔드가 소유한다. 프론트엔드에는 별도 저장 기능을 두지 않는다.

## 주요 기능

| 구분 | 기능 |
|---|---|
| 영화 | 등록 · 목록 조회(포스터 · 제목 · 평균 평점) · 상세 조회 · 삭제(리뷰 연쇄 삭제) |
| 리뷰 | 등록 시 감성 분석 자동 실행 · 영화별 목록(10건 페이지네이션) · 최근 10건 · 삭제 |
| 감성 분석 | `좋아요` / `보통` / `별로에요` 3단 표기, 확신도 낮으면 `판정 애매` 병기 |

**평점 필드는 두 종류이며 서로 다르다.**

- `external_rating` — TMDB `vote_average` 수집값 (0~10)
- `sentiment_rating` — 리뷰 감성 스칼라(`부정 -1` / `중립 0` / `긍정 +1`)의 산술평균 (-1~+1)

저장·API 응답은 원값이고, **0~5 별점 환산은 프론트엔드에서만** 수행한다.
리뷰가 없으면 평점은 `null`이며 `평점 없음`으로 표기한다 — 0(중립)과 구분하기 위해서다.

## 감성 분석 모델

미션 13에서 학습·경량화해 ONNX로 변환한 **ELECTRA 계열 3-class 분류기**를 그대로 재사용한다.

| 항목 | 값 |
|---|---|
| 구조 | hidden 256 · 12 layers · vocab 54,343 |
| 입력 | `input_ids` · `attention_mask` · `token_type_ids`, 각 `[1, 256]` int32 (Fixed Shape) |
| 출력 | `logits [1, 3]` (raw logit — 후처리에서 softmax 적용) |
| 라벨 | `0=부정` · `1=중립` · `2=긍정` |
| 크기 | 약 127MB (`.onnx` + `.onnx.data`) |

- `.onnx`와 `.onnx.data`는 **짝이다.** 하나만 배포하면 로드에 실패한다.
  ⚠ **제출 압축본에는 이 두 파일이 빠져 있다**(용량). 받는 방법은
  [`backend/ml_assets/MODEL_NOTE.md`](backend/ml_assets/MODEL_NOTE.md)를 본다.
- 모델은 `lifespan`에서 **1회 로드**해 재사용한다. 요청마다 세션을 만들지 않는다.
- 추론은 **리뷰 등록 시 1회**만 수행하고 결과를 저장한다. 조회할 때 다시 추론하지 않는다.
- 모델 로드에 실패해도 앱은 기동한다. 리뷰는 감성 필드 `null`로 저장되고 평균에서 제외되며,
  영화 CRUD(필수 기능)는 영향을 받지 않는다.

### 도메인 이동 성능

학습 도메인은 쇼핑몰·SNS 리뷰, 추론 대상은 영화 리뷰(NSMC)다. NSMC test 3,000건 실측:

| 지표 | 값 |
|---|---|
| 미션 13 자체 도메인 test accuracy | 0.885 |
| NSMC 이진 정확도 (중립 예측 제외) | **0.818** |
| 중립 예측 비율 | 0.200 |

`confidence`(= `max(softmax)`)는 정확도와 단조에 가깝게 증가한다. 이를 근거로
**0.90 미만**을 `판정 애매`로 표기한다. 예측값을 보정하지는 않는다.

## 실행

### 백엔드

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

- API 문서: http://localhost:8000/docs
- 헬스 체크: http://localhost:8000/health (모델 로드 여부 확인)

### 프론트엔드

```bash
cd frontend
pip install -r requirements.txt
BACKEND_BASE_URL=http://localhost:8000 streamlit run app.py
```

백엔드 주소는 `st.secrets["BACKEND_BASE_URL"]` → 환경변수 순으로 읽는다. 하드코딩하지 않는다.

### 시드 데이터 생성 (로컬 1회)

```bash
cd backend
cp .env.example .env        # TMDB_API_KEY 입력
python scripts/collect_tmdb.py    # TMDB 영화 메타데이터 수집
python scripts/build_reviews.py   # NSMC 리뷰 선별 · 영화에 배정
python scripts/seed_db.py         # 시드 DB 생성 (적재 시점에 감성 분석 수행)
```

TMDB API 키는 **수집 단계에서만** 필요하다. 서비스 실행에는 필요하지 않다.

### 테스트

```bash
cd backend && python -m pytest tests -q
```

## API

| 메서드 | 경로 | 설명 |
|---|---|---|
| GET | `/health` | 헬스 체크 · 모델 로드 여부 |
| GET | `/movies` | 영화 목록 (평균 평점 · 리뷰 수 포함) |
| POST | `/movies` | 영화 등록 |
| GET | `/movies/{id}` | 영화 단건 조회 |
| DELETE | `/movies/{id}` | 영화 삭제 (리뷰 연쇄 삭제) |
| GET | `/movies/{id}/reviews` | 영화별 리뷰 (페이지네이션) |
| GET | `/movies/{id}/rating` | 평점 조회 (감성 점수 평균) |
| POST | `/reviews` | 리뷰 등록 (감성 분석 자동 실행) |
| GET | `/reviews` | 전체 리뷰 최신순 (페이지네이션) |
| DELETE | `/reviews/{id}` | 리뷰 삭제 |
| POST | `/sentiment/analyze` | 감성 분석만 수행 (저장 없음) |

상태 코드: `404` 없는 리소스 · `409` 중복 영화 · `422` 검증 실패 · `503` 모델 미로드.
리뷰 등록 중 추론이 실패해도 **201**을 반환한다 — 리뷰 저장 자체는 성공했기 때문이다.

## 폴더 구조

```
backend/
├── app/
│   ├── main.py          # FastAPI 인스턴스 · lifespan · CORS
│   ├── routers/         # HTTP 계층
│   ├── services/        # 규칙 (평점 집계 · 감성 연동)
│   ├── repositories/    # DB 접근
│   └── ml/              # ONNX 로드 · 전처리 → 추론 → 후처리
├── ml_assets/           # .onnx + .onnx.data + tokenizer.json
├── scripts/             # 데이터 수집 (로컬 1회 실행)
└── tests/
frontend/
├── app.py               # 영화 목록 / 상세 (query param 분기)
├── pages/               # 영화 추가 · 리뷰 등록 · 최근 리뷰
└── lib/                 # API 클라이언트 · 표현 계층 · 공통 컴포넌트
```

## 데이터 출처

- **영화 메타데이터: [TMDB](https://www.themoviedb.org/)**
  이 서비스는 TMDB API를 사용하지만 TMDB가 보증하지 않습니다.
  (This product uses the TMDB API but is not endorsed or certified by TMDB.)
- **리뷰: [NSMC](https://github.com/e9t/nsmc)** (네이버 영화 리뷰 20만 건)
  ⚠ **리뷰와 영화의 대응은 임의 배정**이며 실제 해당 영화의 관람평이 아니다.
  NSMC에는 제목·작성자·등록일이 없어 이 세 필드는 파생 생성했다.

## 배포 시 유의점

- 배포본의 SQLite는 **영속되지 않는다.** 컨테이너 파일시스템이 교체되면 런타임에 추가된
  데이터가 사라진다. 시드 데이터를 이미지에 굽고 인스턴스를 1개로 고정해 운영한다.
  영속 저장이 필요한 사용은 로컬 실행을 기준으로 한다.
- TMDB API 키는 이미지·저장소 어디에도 포함하지 않는다. 수집 결과(DB)만 배포한다.
