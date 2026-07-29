# Cloud Run 배포용. 메모리 1GiB · --max-instances=1 을 전제로 한다.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# .onnx 와 .onnx.data 는 짝이다. 하나만 복사하면 로드에 실패한다
COPY ml_assets/ ./ml_assets/
COPY app/ ./app/
# 시드 DB를 이미지에 굽는다. 런타임에 TMDB·NSMC에 접근하지 않는다
COPY data/movies.db ./data/movies.db

EXPOSE 8080

# 워커 1개. 모델을 프로세스마다 로드하면 메모리 예산을 넘긴다
CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --workers 1
