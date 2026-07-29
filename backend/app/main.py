"""FastAPI 진입점 — lifespan · CORS · 라우터 등록."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import Base, engine
from .ml.loader import load_model
from .routers import movies, reviews, sentiment
from .schemas import HealthResponse

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """모델은 여기서 1회 로드해 재사용한다. 요청마다 세션을 만들지 않는다."""
    Base.metadata.create_all(bind=engine)

    try:
        app.state.model_bundle = load_model(settings.ml_assets_dir, settings.model_version)
    except Exception:
        # 모델 로드 실패로 앱을 죽이지 않는다. 영화 CRUD(필수 기능)는 모델과 무관하다
        logger.exception("감성 분석 모델 로드 실패 — 감성 기능 없이 기동한다")
        app.state.model_bundle = None

    yield

    app.state.model_bundle = None


app = FastAPI(
    title="영화 리뷰 감성 분석 API",
    version="1.0.0",
    lifespan=lifespan,
    description=(
        "영화 정보와 리뷰를 관리하고, 리뷰 등록 시 감성 분석을 자동 수행하는 백엔드다.\n\n"
        "**평점 필드는 두 종류이며 서로 다르다.**\n"
        "- `external_rating` — TMDB `vote_average` 수집값 (0~10)\n"
        "- `sentiment_rating` — 소속 리뷰 감성 스칼라(-1 · 0 · +1)의 산술평균 (-1~+1, 파생값)\n\n"
        "저장과 응답은 모두 원값이며, 0~5 별점 환산은 프론트엔드에서만 수행한다.\n\n"
        "감성 분석 모델은 미션 13에서 학습·경량화한 ELECTRA 계열 ONNX 모델을 그대로 재사용한다.\n\n"
        "데이터 출처: 영화 메타데이터는 TMDB API, 리뷰는 NSMC 공개 데이터셋이다. "
        "이 서비스는 TMDB API를 사용하지만 TMDB가 보증하지 않는다."
    ),
    contact={"name": "3팀 신호정"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.allowed_origins),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(movies.router)
app.include_router(reviews.router)
app.include_router(sentiment.router)


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["system"],
    summary="헬스 체크",
    description=(
        "서비스 상태와 감성 분석 모델 로드 여부를 반환한다. "
        "`model_loaded`가 `false`면 리뷰 등록은 계속 동작하되 감성 필드가 `null`로 저장된다."
    ),
)
def health() -> HealthResponse:
    bundle = getattr(app.state, "model_bundle", None)
    return HealthResponse(
        status="ok",
        model_loaded=bundle is not None,
        model_version=bundle.model_version if bundle else None,
        max_length=bundle.max_length if bundle else None,
    )
