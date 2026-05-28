from fastapi import FastAPI

from bosgenesis_mop_creation_agent import __version__
from bosgenesis_mop_creation_agent.api.routes import router
from bosgenesis_mop_creation_agent.common.logging import configure_logging, get_logger
from bosgenesis_mop_creation_agent.config.settings import Settings, load_settings
from bosgenesis_mop_creation_agent.core.orchestrator import MoPCreationOrchestrator


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the FastAPI app."""
    app_settings = settings or load_settings()
    configure_logging(app_settings.logging)

    app = FastAPI(
        title=app_settings.agent.name,
        version=__version__,
        description="BOS Genesis MoP Creation Agent",
    )
    app.state.settings = app_settings
    app.state.orchestrator = MoPCreationOrchestrator(app_settings)
    app.include_router(router)

    logger = get_logger(__name__)
    logger.info(
        "application_created",
        extra={
            "agent_name": app_settings.agent.name,
            "source_namespace": app_settings.agent.source_namespace,
            "runtime_mode": app_settings.agent.mode,
        },
    )
    return app
