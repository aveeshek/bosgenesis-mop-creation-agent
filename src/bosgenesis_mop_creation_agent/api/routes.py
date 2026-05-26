from typing import Any

from fastapi import APIRouter, Request

from bosgenesis_mop_creation_agent import __version__
from bosgenesis_mop_creation_agent.common.logging import get_logger
from bosgenesis_mop_creation_agent.config.settings import Settings

router = APIRouter()
logger = get_logger(__name__)


def _settings(request: Request) -> Settings:
    return request.app.state.settings


@router.get("/health")
def health(request: Request) -> dict[str, Any]:
    settings = _settings(request)
    logger.info(
        "health_checked",
        extra={
            "agent_name": settings.agent.name,
            "source_namespace": settings.agent.source_namespace,
        },
    )
    return {
        "status": "ok",
        "agent": settings.agent.name,
        "version": __version__,
        "source_namespace": settings.agent.source_namespace,
        "runtime_mode": settings.agent.mode,
    }


@router.get("/config/effective")
def effective_config(request: Request) -> dict[str, Any]:
    settings = _settings(request)
    logger.info("effective_config_requested", extra={"agent_name": settings.agent.name})
    return settings.redacted_dict()

