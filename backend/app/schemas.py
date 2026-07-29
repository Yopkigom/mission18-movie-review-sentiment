"""Pydantic 스키마. API 계약(docs/plan/implementation.md C-b)의 구현이다."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_serializer

T = TypeVar("T")


class MovieCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200, description="영화 제목")
    release_date: date = Field(description="개봉일 (YYYY-MM-DD)")
    director: str | None = Field(default=None, max_length=100, description="감독")
    genre: str | None = Field(default=None, max_length=100, description="장르")
    # HttpUrl 대신 str로 둔다. TMDB 이미지 URL은 정상이지만 사용자가 입력한
    # 값까지 엄격 검증하면 등록이 막히고, 잘못된 URL은 화면이 대체 표시로 처리한다
    poster_url: str | None = Field(default=None, max_length=500, description="포스터 이미지 URL")
    external_rating: float | None = Field(
        default=None, ge=0, le=10, description="TMDB vote_average (0~10). 감성 평점과 별개다"
    )
    tmdb_id: int | None = Field(default=None, description="TMDB 원본 ID")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "기생충",
                "release_date": "2019-05-30",
                "director": "봉준호",
                "genre": "드라마",
                "poster_url": "https://image.tmdb.org/t/p/w500/example.jpg",
                "external_rating": 8.5,
                "tmdb_id": 496243,
            }
        }
    )


class MovieSummary(BaseModel):
    """목록 화면용. 포스터 · 제목 · 평균 평점만 필요하다."""

    id: int
    title: str
    poster_url: str | None = None
    sentiment_rating: float | None = Field(
        default=None, description="소속 리뷰 감성 스칼라의 산술평균 (-1~+1). 리뷰가 없으면 null"
    )
    review_count: int = Field(description="감성 분석 성공 여부와 무관한 전체 리뷰 수")

    model_config = ConfigDict(from_attributes=True)


class MovieDetail(MovieSummary):
    release_date: date
    director: str | None = None
    genre: str | None = None
    external_rating: float | None = Field(default=None, description="TMDB 평점 (0~10)")
    tmdb_id: int | None = None
    is_seed: bool = Field(default=False, description="시드 적재로 들어온 데모 데이터인지")
    deletable: bool = Field(
        default=True,
        description=(
            "삭제 가능 여부. 공개 배포본은 시드 데이터 삭제를 막는다(`PROTECT_SEED`). "
            "로컬 실행에서는 항상 true다."
        ),
    )


class MovieRating(BaseModel):
    """평점 단건 조회 응답."""

    movie_id: int
    sentiment_rating: float | None = Field(description="감성 스칼라 평균 (-1~+1)")
    review_count: int = Field(description="전체 리뷰 수")
    analyzed_count: int = Field(description="평균 계산에 사용된 리뷰 수 (감성 분석 성공분)")


class ReviewCreate(BaseModel):
    movie_id: int = Field(description="리뷰를 등록할 영화 ID")
    author: str = Field(min_length=1, max_length=50, description="작성자")
    title: str | None = Field(default=None, max_length=200, description="리뷰 제목")
    # 상한 2000자는 저장 단계의 방어선이다. 모델 입력 truncation은 추론 모듈이 따로 수행한다
    content: str = Field(min_length=1, max_length=2000, description="리뷰 내용")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "movie_id": 1,
                "author": "익명1",
                "title": "연출이 정말 좋았다",
                "content": "계단 구도만으로 계급을 설명하는 장면이 인상적이었다.",
            }
        }
    )


class ReviewOut(BaseModel):
    id: int
    movie_id: int
    author: str
    title: str | None = None
    content: str
    created_at: datetime = Field(description="등록 시각 (UTC). 지역 시각 변환은 표시 측에서 한다")
    sentiment_label: str | None = Field(default=None, description="부정 · 중립 · 긍정")
    sentiment_score: int | None = Field(default=None, description="-1 · 0 · +1")
    confidence: float | None = Field(default=None, description="max(softmax). 표기 전용")
    model_version: str | None = None

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at")
    def _created_at_as_utc(self, value: datetime) -> str:
        """DB에는 naive UTC로 들어 있다. 소비 측이 로컬 시각으로 오해하지 않도록
        오프셋을 붙여 내보낸다."""
        return value.replace(tzinfo=timezone.utc).isoformat()


class SentimentRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000, description="분석할 텍스트")

    model_config = ConfigDict(
        json_schema_extra={"example": {"text": "연출도 배우도 훌륭했다. 강력 추천합니다."}}
    )


class SentimentResponse(BaseModel):
    label: str = Field(description="부정 · 중립 · 긍정")
    score: int = Field(description="-1 · 0 · +1")
    confidence: float = Field(description="max(softmax)")
    probabilities: list[float] = Field(description="[부정, 중립, 긍정] 확률")
    model_version: str
    truncated: bool = Field(description="입력이 모델 최대 길이(256 토큰)를 넘어 잘렸는지")


class Page(BaseModel, Generic[T]):
    """페이지네이션 응답. 총 페이지 수 계산에 total이 필요하다."""

    items: list[T]
    total: int
    limit: int
    offset: int


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool = Field(description="감성 분석 모델 로드 여부")
    model_version: str | None = None
    max_length: int | None = Field(default=None, description="모델 입력 시퀀스 고정 길이")


class ErrorResponse(BaseModel):
    detail: str
