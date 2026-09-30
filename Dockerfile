FROM python:3.12-slim

# optional build-time mirrors for slow international access, e.g.
#   docker build --build-arg PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
#                --build-arg APT_MIRROR=mirrors.ustc.edu.cn .
ARG APT_MIRROR=""
ARG PIP_INDEX_URL=""

WORKDIR /app

RUN if [ -n "$APT_MIRROR" ]; then \
        sed -i "s|deb.debian.org|$APT_MIRROR|g" /etc/apt/sources.list.d/debian.sources; \
    fi \
    && apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY video2subtitle ./video2subtitle
RUN pip install --no-cache-dir ${PIP_INDEX_URL:+--index-url "$PIP_INDEX_URL"} .

ENV V2S_HOST=0.0.0.0 \
    V2S_PORT=8765 \
    V2S_DATA_DIR=/data \
    V2S_SENSEVOICE_MODEL_DIR=/models/sensevoice \
    V2S_QWEN3_MODEL_DIR=/models/qwen3

VOLUME ["/data", "/models"]
EXPOSE 8765

CMD ["python", "-m", "video2subtitle.main"]
