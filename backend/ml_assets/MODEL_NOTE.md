# 모델 가중치 안내

제출 압축본에는 용량 문제로 **ONNX 가중치 2개 파일이 빠져 있다.**

| 파일 | 크기 | 압축본 포함 |
|---|---|---|
| `modelA_full_ft.onnx` | 약 63MB | ✗ |
| `modelA_full_ft.onnx.data` | 약 63MB (external data) | ✗ |
| `tokenizer.json` · `vocab.txt` | 약 1.7MB | ✓ |

두 파일은 **짝이다.** 하나만 배치하면 onnxruntime 로드에 실패한다.

## 받는 곳

- 공개 저장소 `https://github.com/Yopkigom/mission18-movie-review-sentiment`
  → `backend/ml_assets/` (두 파일 모두 포함되어 있다)
- 또는 스프린트 미션 13 산출물 `mission13/CheckPoint/modelA_full_ft.onnx(.data)`
  (같은 파일이며 재-export 없이 그대로 재사용한 것이다)

받은 파일 2개를 이 폴더(`backend/ml_assets/`)에 그대로 두면 된다.

## 없이 실행하면

앱은 정상 기동한다. `lifespan`에서 모델 로드에 실패하면 감성 분석만 비활성화되고,
리뷰는 감성 필드 `null`로 저장되어 평균에서 제외된다. 영화 CRUD(필수 기능)는 영향이 없다.
`GET /health`의 `model_loaded`로 로드 여부를 확인할 수 있다.

동작 확인만 필요하면 배포본을 쓰는 편이 빠르다.

- 프론트엔드: https://movie-review-sentiment-mi18.streamlit.app/
- 백엔드 API 문서: https://mission18-backend-46129022703.asia-northeast3.run.app/docs
