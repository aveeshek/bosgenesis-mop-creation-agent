import uvicorn

from bosgenesis_mop_creation_agent.config.settings import load_settings


def main() -> None:
    settings = load_settings()
    uvicorn.run(
        "bosgenesis_mop_creation_agent.api.app:create_app",
        host=settings.api.host,
        port=settings.api.port,
        factory=True,
    )

