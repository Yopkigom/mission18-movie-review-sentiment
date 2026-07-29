"""전처리 → 추론 → 후처리.

모델 출력은 raw logits([1, 3])이므로 softmax를 직접 적용한다(B-b-3 실측 확인).
입력 dtype은 int32다 — 미션 13이 Unity Sentis 호환을 위해 int32로 export했다.
"""
from __future__ import annotations

import logging
import unicodedata
import re
from dataclasses import dataclass

import numpy as np

from .loader import LABEL_NAMES, LABEL_SCORES, ModelBundle

logger = logging.getLogger(__name__)

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


@dataclass(frozen=True)
class SentimentResult:
    """감성 분석 1건의 결과."""

    label: str          # 부정 · 중립 · 긍정
    score: int          # -1 · 0 · +1
    confidence: float   # max(softmax)
    probabilities: list[float]
    model_version: str
    truncated: bool     # 입력이 모델 최대 길이를 넘어 잘렸는지


def preprocess(text: str) -> str:
    """미션 13 학습 시 전처리와 동일하게 맞춘다.

    학습과 추론의 정규화가 다르면 같은 문장이 다른 토큰열이 된다.
    """
    text = unicodedata.normalize("NFKC", str(text))
    text = _CONTROL_CHARS.sub("", text)
    return text.strip()


def _softmax(logits: np.ndarray) -> np.ndarray:
    shifted = logits - logits.max()
    exp = np.exp(shifted)
    return exp / exp.sum()


def predict(bundle: ModelBundle, text: str) -> SentimentResult:
    """단건 감성 분석. 실패 시 예외를 올린다(호출부가 null 처리를 결정)."""
    cleaned = preprocess(text)
    if not cleaned:
        raise ValueError("분석할 텍스트가 비어 있습니다.")

    encoding = bundle.tokenizer.encode(cleaned)
    # 패딩 후 길이는 항상 max_length이므로 잘림 여부는 오버플로 유무로 판단한다
    truncated = bool(encoding.overflowing)

    feeds = {
        "input_ids": np.asarray([encoding.ids], dtype=np.int32),
        "attention_mask": np.asarray([encoding.attention_mask], dtype=np.int32),
        "token_type_ids": np.asarray([encoding.type_ids], dtype=np.int32),
    }
    # export 시점 입력 이름과 다를 가능성에 대비해 세션이 요구하는 키만 전달
    feeds = {name: feeds[name] for name in bundle.input_names}

    logits = bundle.session.run(None, feeds)[0][0]
    probabilities = _softmax(np.asarray(logits, dtype=np.float64))
    index = int(probabilities.argmax())

    return SentimentResult(
        label=LABEL_NAMES[index],
        score=LABEL_SCORES[index],
        confidence=float(probabilities[index]),
        probabilities=[float(p) for p in probabilities],
        model_version=bundle.model_version,
        truncated=truncated,
    )
