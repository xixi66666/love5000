FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HOME=/tmp TZ=Asia/Shanghai
ARG DOWNLOAD_PROXY=
RUN if [ -n "$DOWNLOAD_PROXY" ]; then export http_proxy="$DOWNLOAD_PROXY" https_proxy="$DOWNLOAD_PROXY"; fi; \
    sed -i 's|http://deb.debian.org/debian|https://mirrors.cloud.tencent.com/debian|g' /etc/apt/sources.list.d/debian.sources && \
    apt-get -o Acquire::Retries=5 update && apt-get -o Acquire::Retries=5 install -y --no-install-recommends ffmpeg fonts-noto-cjk ca-certificates \
    libnss3 libatk-bridge2.0-0 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app/backend
COPY backend/pyproject.toml ./
COPY deploy/requirements.lock /tmp/requirements.lock
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r /tmp/requirements.lock \
    && pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple 'setuptools>=75' wheel
COPY backend/app ./app
RUN pip install --no-cache-dir --no-build-isolation --no-deps .
COPY frontend/dist /app/frontend/dist
RUN apt-get -o Acquire::Retries=3 update \
    && apt-get -o Acquire::Retries=3 install -y --no-install-recommends libxcomposite1 libxdamage1 \
    && rm -rf /var/lib/apt/lists/*
USER 65532:65532
CMD ["uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "15177", "--workers", "1"]
