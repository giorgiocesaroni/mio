FROM python:3.13-alpine

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# ffmpeg: audio conversion (media uploads) and 16kHz resampling (transcription)
RUN apk add --no-cache ffmpeg

ENV PYTHONPATH=/app

COPY . .

RUN uv sync --locked

EXPOSE 8000

CMD ["uv", "run", "src/api/api.py"]
