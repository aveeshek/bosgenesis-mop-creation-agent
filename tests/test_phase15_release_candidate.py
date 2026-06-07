import json
import time
from pathlib import Path

from fastapi.testclient import TestClient

from bosgenesis_mop_creation_agent.api.app import create_app
from bosgenesis_mop_creation_agent.config.settings import AgentSettings, Settings


def _wait_for_generated(client: TestClient, mop_id: str) -> dict:
    deadline = time.monotonic() + 10
    payload = {}
    while time.monotonic() < deadline:
        response = client.get(f"/mop-creation/{mop_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] != "accepted":
            return payload
        time.sleep(0.05)
    raise AssertionError(f"MoP generation did not complete in time: {payload}")


def test_application_mode_rc_generates_safe_human_review_placeholder(tmp_path: Path) -> None:
    client = TestClient(
        create_app(Settings(agent=AgentSettings(local_storage_path=str(tmp_path))))
    )

    accepted = client.post(
        "/mop-creation/generate",
        json={
            "target_namespace": "bosgenesis-application-rc",
            "mode": "application",
            "include_application_schema": True,
            "caller": "pytest-phase15",
            "correlation_id": "phase15-application-smoke",
        },
    ).json()

    payload = _wait_for_generated(client, accepted["mop_id"])

    assert payload["status"] == "generated"
    assert payload["target_namespace"] == "bosgenesis-application-rc"

    manifest = json.loads(
        Path(payload["artifacts"]["artifact_manifest_path"]).read_text(encoding="utf-8")
    )
    plan = manifest["machine_execution_plan"]["machine_execution_plan"]
    application_phase = next(
        phase for phase in plan["phases"] if phase["phase_id"] == "apply_application_metadata"
    )

    assert application_phase["enabled_when"] == 'generation_mode == "application"'
    assert application_phase["steps"][0]["requires_human_approval"] is False
    assert application_phase["steps"][0]["mutates_target"] is False
    assert application_phase["steps"][0]["required_human_inputs"] == [
        "application_metadata_evidence"
    ]
    assert application_phase["steps"][0]["commands"] == []
    assert "metadata recreation is deferred" in application_phase["objective"]
