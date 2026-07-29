"""추론 모듈 검증 (B-c). 라벨 매핑이 뒤집히면 평점 부호가 통째로 반대가 되므로
골든 케이스를 회귀 테스트로 고정해 둔다.
"""
from __future__ import annotations

import pytest

from app.config import settings
from app.ml.loader import LABEL_NAMES, LABEL_SCORES, load_model
from app.ml.predictor import predict

pytestmark = pytest.mark.skipif(
    not (settings.ml_assets_dir / "modelA_full_ft.onnx").exists(),
    reason="ONNX 자산이 없는 환경",
)


@pytest.fixture(scope="module")
def bundle():
    return load_model(settings.ml_assets_dir, "test")


def test_label_table_is_fixed():
    """미션 13 학습 코드의 LABEL_MAP과 일치해야 한다."""
    assert LABEL_NAMES == ("부정", "중립", "긍정")
    assert LABEL_SCORES == (-1, 0, 1)


def test_input_shape_is_fixed(bundle):
    assert bundle.max_length == 256
    assert set(bundle.input_names) == {"input_ids", "attention_mask", "token_type_ids"}


@pytest.mark.parametrize(
    "text,expected",
    [
        ("정말 재미있게 봤어요. 배우들 연기도 훌륭하고 강력 추천합니다.", "긍정"),
        ("인생 영화입니다. 다시 봐도 감동이에요.", "긍정"),
        ("최악이었어요. 시간이 아깝습니다. 절대 보지 마세요.", "부정"),
        ("연기도 각본도 형편없었다. 실망스럽다.", "부정"),
        ("평범한 영화. 시간 때우기용으로는 괜찮음.", "중립"),
    ],
)
def test_golden_cases(bundle, text, expected):
    result = predict(bundle, text)
    assert result.label == expected
    assert result.score == LABEL_SCORES[LABEL_NAMES.index(expected)]
    assert 0.0 < result.confidence <= 1.0


def test_probabilities_sum_to_one(bundle):
    """모델 출력은 raw logit이므로 후처리 softmax가 반드시 적용돼야 한다."""
    result = predict(bundle, "볼만했습니다.")
    assert abs(sum(result.probabilities) - 1.0) < 1e-6


def test_long_input_is_truncated(bundle):
    long_text = "이 영화는 정말 재미있었다. " * 200
    result = predict(bundle, long_text)
    assert result.truncated is True


def test_empty_text_raises(bundle):
    with pytest.raises(ValueError):
        predict(bundle, "   ")
