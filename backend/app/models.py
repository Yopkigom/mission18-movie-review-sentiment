"""SQLAlchemy 모델. ERD(docs/plan/architecture.md B)와 1:1로 대응한다."""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Movie(Base):
    __tablename__ = "movie"
    __table_args__ = (
        # 같은 제목의 리메이크는 개봉일이 달라 통과한다
        UniqueConstraint("title", "release_date", name="uq_movie_title_release"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # 화면에서 수동 등록한 영화에는 TMDB ID가 없으므로 nullable이다.
    # SQLite는 UNIQUE 컬럼의 NULL 중복을 허용한다
    tmdb_id: Mapped[int | None] = mapped_column(Integer, unique=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    release_date: Mapped[date] = mapped_column(Date, nullable=False)
    director: Mapped[str | None] = mapped_column(String(100))
    genre: Mapped[str | None] = mapped_column(String(100))
    poster_url: Mapped[str | None] = mapped_column(Text)
    # TMDB vote_average(0~10). 감성 평점과 출처·범위가 다른 별개 필드다
    external_rating: Mapped[float | None] = mapped_column(Float)

    reviews: Mapped[list["Review"]] = relationship(
        back_populates="movie", cascade="all, delete-orphan", passive_deletes=True
    )


class Review(Base):
    __tablename__ = "review"
    __table_args__ = (
        Index("idx_review_movie", "movie_id", "created_at"),
        Index("idx_review_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movie.id", ondelete="CASCADE"), nullable=False
    )
    author: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str | None] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # 추론은 등록 시 1회만 수행하고 결과를 저장한다. 실패 시 전부 NULL이다
    sentiment_label: Mapped[str | None] = mapped_column(String(10))
    sentiment_score: Mapped[int | None] = mapped_column(Integer)
    confidence: Mapped[float | None] = mapped_column(Float)
    model_version: Mapped[str | None] = mapped_column(String(50))

    movie: Mapped[Movie] = relationship(back_populates="reviews")
