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


@dataclass(frozen=True)
class Settings:
    database_url: str = ""
    ml_assets_dir: Path = field(default_factory=lambda: BASE_DIR / "ml_assets")
    model_version: str = "mission13-modelA-full-ft"
    allowed_origins: tuple[str, ...] = ("*",)


def load_settings() -> Settings:
    db_path = _env_path("DATABASE_PATH", "data/movies.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)

    origins = os.getenv("ALLOWED_ORIGINS", "*")
    return Settings(
        database_url=os.getenv("DATABASE_URL", f"sqlite:///{db_path}"),
        ml_assets_dir=_env_path("ML_ASSETS_DIR", "ml_assets"),
        model_version=os.getenv("MODEL_VERSION", "mission13-modelA-full-ft"),
        allowed_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
    )


settings = load_settings()
