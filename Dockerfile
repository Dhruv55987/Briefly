FROM python:3.11-slim-bookworm

COPY --from=denoland/deno:bin-2.9.6 /deno /usr/local/bin/deno

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000
# Jobs live in memory: use one process and one service instance for this demo.
CMD ["sh", "-c", "exec uvicorn backend:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
