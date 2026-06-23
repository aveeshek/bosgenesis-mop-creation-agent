FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    BOSGENESIS_MOP_CONFIG_PATH=/app/config/settings.yaml

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY config ./config
COPY artifacts ./artifacts

RUN test -f /app/src/bosgenesis_mop_creation_agent/__init__.py
RUN pip install --no-cache-dir .
RUN python -c "from bosgenesis_mop_creation_agent.entrypoints.main import main; print('bosgenesis_mop_creation_agent import ok')"

EXPOSE 8080

CMD ["bosgenesis-mop-creation-agent"]
