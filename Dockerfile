# Full YouTube support needs a JS runtime. Deno is included in the image,
# so the person using the website does NOT install anything.
FROM denoland/deno:bin-2.9.6 AS deno
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=10000

COPY --from=deno /deno /usr/local/bin/deno
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY static/ ./static/

RUN useradd -m -u 10001 webapp
USER webapp
EXPOSE 10000
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1"]
