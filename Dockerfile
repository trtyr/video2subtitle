FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md ./
COPY video2subtitle ./video2subtitle
RUN pip install --no-cache-dir .

ENV V2S_HOST=0.0.0.0 \
    V2S_PORT=8765 \
    V2S_DATA_DIR=/data \
    V2S_SENSEVOICE_MODEL_DIR=/models/sensevoice \
    V2S_QWEN3_MODEL_DIR=/models/qwen3

VOLUME ["/data", "/models"]
EXPOSE 8765

CMD ["python", "-m", "video2subtitle.main"]
