"""ONNX 세션 · 토크나이저 로드.

미션 13에서 export한 자산(modelA_full_ft.onnx + .onnx.data + tokenizer.json)을
그대로 사용한다. 세션은 lifespan에서 1회 생성해 재사용한다.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import onnxruntime as ort
from tokenizers import Tokenizer

logger = logging.getLogger(__name__)

ONNX_FILENAME = "modelA_full_ft.onnx"
TOKENIZER_FILENAME = "tokenizer.json"

# 미션 13 학습 코드의 LABEL_MAP({'-1': 0, '0': 1, '1': 2})과
# B-c-1 골든 케이스 실측으로 확정한 매핑이다. 추정값이 아니다.
LABEL_NAMES: tuple[str, str, str] = ("부정", "중립", "긍정")
LABEL_SCORES: tuple[int, int, int] = (-1, 0, 1)


@dataclass(frozen=True)
class ModelBundle:
    """추론에 필요한 자산 묶음."""

    session: ort.InferenceSession
    tokenizer: Tokenizer
    max_length: int
    input_names: tuple[str, ...]
    model_version: str


def load_model(assets_dir: str | Path, model_version: str) -> ModelBundle:
    """ONNX 세션과 토크나이저를 로드한다.

    실패 시 예외를 그대로 올린다. 호출부(lifespan)가 이를 잡아
    모델 없이 기동할지 결정한다 — 영화 CRUD는 모델 없이도 동작해야 한다.
    """
    base = Path(assets_dir)
    onnx_path = base / ONNX_FILENAME
    tokenizer_path = base / TOKENIZER_FILENAME

    # external data(.onnx.data)는 같은 폴더에 있어야 로드된다. 짝이 맞는지 먼저 확인
    external_data = onnx_path.with_suffix(".onnx.data")
    for path in (onnx_path, external_data, tokenizer_path):
        if not path.exists():
            raise FileNotFoundError(f"모델 자산 누락: {path}")

    options = ort.SessionOptions()
    # Cloud Run 1 vCPU 기준. 스레드를 늘려도 이득이 없고 메모리만 늘어난다
    options.intra_op_num_threads = 1
    options.inter_op_num_threads = 1

    session = ort.InferenceSession(
        str(onnx_path), sess_options=options, providers=["CPUExecutionProvider"]
    )

    # Fixed Shape이므로 max_length를 코드에 쓰지 않고 세션 입력 shape에서 읽는다
    shape = session.get_inputs()[0].shape
    max_length = int(shape[1])

    tokenizer = Tokenizer.from_file(str(tokenizer_path))
    tokenizer.enable_truncation(max_length=max_length)
    tokenizer.enable_padding(length=max_length, pad_id=0, pad_token="[PAD]")

    input_names = tuple(i.name for i in session.get_inputs())
    logger.info(
        "감성 분석 모델 로드 완료 (max_length=%d, inputs=%s)", max_length, input_names
    )

    return ModelBundle(
        session=session,
        tokenizer=tokenizer,
        max_length=max_length,
        input_names=input_names,
        model_version=model_version,
    )
