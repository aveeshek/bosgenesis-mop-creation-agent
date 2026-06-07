from fastapi.testclient import TestClient

from bosgenesis_mop_creation_agent.api.app import create_app
from bosgenesis_mop_creation_agent.config.settings import Settings


def test_health_endpoint_returns_runtime_metadata() -> None:
    client = TestClient(create_app(Settings()))

    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["agent"] == "bosgenesis-mop-creation-agent"
    assert payload["release_candidate"] == "phase15-rc1"
    assert payload["values_schema_version"] == "phase15.rc.v1"
    assert payload["source_namespace"] == "bosgenesis"
    assert payload["runtime_mode"] == "on_demand"

    config_response = client.get("/config/effective")
    config = config_response.json()
    assert config["inventory"]["postgres"]["enabled"] is True
    assert config["inventory"]["clickhouse"]["enabled"] is True


def test_effective_config_is_redacted() -> None:
    settings = Settings.model_validate(
        {
            "inventory": {
                "postgres": {
                    "enabled": True,
                    "dsn": "postgresql://user:super-secret-password@example.invalid/db",
                }
            },
            "mcp": {
                "k8s_inspector": {
                    "enabled": True,
                    "endpoint": "https://example.invalid?token=do-not-emit",
                }
            }
        }
    )
    client = TestClient(create_app(settings))

    response = client.get("/config/effective")

    assert response.status_code == 200
    text = response.text
    assert "do-not-emit" not in text
    assert "super-secret-password" not in text
    assert "***REDACTED***" in text
