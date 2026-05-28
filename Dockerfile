FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BOSGENESIS_MOP_CONFIG_PATH=/app/config/settings.yaml

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY config ./config
COPY artifacts ./artifacts

RUN pip install --no-cache-dir .

EXPOSE 8080

CMD ["bosgenesis-mop-creation-agent"]
