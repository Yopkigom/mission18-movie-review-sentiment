"""환경변수 로딩.

TMDB 키는 여기에 두지 않는다. 수집 스크립트(`scripts/`)에서만 `.env`로 읽으며
런타임에는 필요하지 않다.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_path(name: str, default: str) -> Path:
    """상대 경로는 backend/ 기준으로 해석한다. 작업 디렉터리에 의존하지 않는다."""
    value = Path(os.getenv(name, default))
    return value if value.is_absolute() else (BASE_DIR / value).resolve()


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    database_url: str = ""
    ml_assets_dir: Path = field(default_factory=lambda: BASE_DIR / "ml_assets")
    model_version: str = "mission13-modelA-full-ft"
    allowed_origins: tuple[str, ...] = ("*",)
    # 공개 배포본에서만 켠다. 누구나 접근할 수 있는 데모의 시드 데이터가
    # 삭제되면 심사 중에 화면이 비어 버린다. 로컬 실행은 제한하지 않는다
    protect_seed: bool = False


def load_settings() -> Settings:
    db_path = _env_path("DATABASE_PATH", "data/movies.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)

    origins = os.getenv("ALLOWED_ORIGINS", "*")
    return Settings(
        database_url=os.getenv("DATABASE_URL", f"sqlite:///{db_path}"),
        ml_assets_dir=_env_path("ML_ASSETS_DIR", "ml_assets"),
        model_version=os.getenv("MODEL_VERSION", "mission13-modelA-full-ft"),
        allowed_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
        protect_seed=_env_flag("PROTECT_SEED", default=False),
    )


settings = load_settings()
