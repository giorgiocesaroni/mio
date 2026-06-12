FROM python:3.13-alpine

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV PYTHONPATH=/app

COPY . .

RUN uv sync --locked

EXPOSE 8000

CMD ["uv", "run", "src/api/api.py"]
