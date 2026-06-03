import json
import time
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from bosgenesis_mop_creation_agent.api.app import create_app
from bosgenesis_mop_creation_agent.config.settings import AgentSettings, Settings


REQUIRED_HUMAN_MOP_SECTIONS = (
    "Document Header",
    "Change Summary",
    "Pre-change Checklist",
    "Access & Environment Verification",
    "Pre-change Backup",
    "Stakeholder Notification",
    "Deployment Execution",
    "Validation",
    "Go / No-Go Decision Points",
    "Rollback Procedure",
    "Post-Change Activities",
    "Execution Log",
)


def _settings(tmp_path: Path) -> Settings:
    return Settings(agent=AgentSettings(local_storage_path=str(tmp_path)))


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


def test_generate_get_and_latest_artifact_response(tmp_path: Path) -> None:
    client = TestClient(create_app(_settings(tmp_path)))

    response = client.post(
        "/mop-creation/generate",
        json={
            "target_namespace": "bosgenesis-copy-dev",
            "caller": "pytest",
            "correlation_id": "test-correlation-id",
            "return_content": True,
        },
    )

    assert response.status_code == 202
    accepted_payload = response.json()
    assert accepted_payload["status"] == "accepted"
    assert accepted_payload["correlation_id"] == "test-correlation-id"
    assert accepted_payload["run_id"]
    assert accepted_payload["mop_id"]

    payload = _wait_for_generated(client, accepted_payload["mop_id"])
    assert payload["status"] == "generated"
    assert payload["correlation_id"] == "test-correlation-id"
    assert payload["run_id"]
    assert payload["mop_id"]
    assert payload["trace_ids"]["langfuse"].startswith("stub-langfuse-")
    assert payload["trace_ids"]["signoz"].startswith("stub-signoz-")
    assert Path(payload["artifacts"]["run_directory_path"]).is_dir()
    assert Path(payload["artifacts"]["artifact_manifest_path"]).is_file()
    assert Path(payload["artifacts"]["human_mop_markdown_path"]).is_file()
    assert Path(payload["artifacts"]["human_mop_pdf_path"]).is_file()
    assert payload["artifacts"]["human_mop_pdf_path"].endswith(".pdf")
    assert Path(payload["artifacts"]["installation_notes_path"]).is_file()
    assert payload["artifacts"]["installation_notes_path"].endswith(".installation.md")
    assert payload["content"].startswith("# MoP:")
    assert payload["installation_notes_content"].startswith("---")
    assert payload["qdrant_lookup_status"] == "not_executed"
    assert payload["mcp_sources_attempted"] == [
        "k8s_inspector_mcp",
        "helm_manager_mcp",
        "data_ingestion_mcp",
    ]
    assert "k8s_mcp_tools_list_failed" in " ".join(payload["warnings"])
    assert "helm_mcp_tools_list_failed" in " ".join(payload["warnings"])
    assert "postgres_snapshot_read_failed" in " ".join(payload["warnings"])
    assert "clickhouse_snapshot_read_failed" in " ".join(payload["warnings"])
    assert "snapshot_inventory_missing" in " ".join(payload["warnings"])
    assert payload["resource_count"] == 0
    assert payload["helm_release_count"] == 0
    assert payload["helm_managed_resource_count"] == 0
    assert payload["raw_k8s_resource_count"] == 0
    assert payload["excluded_resource_count"] == 0
    assert payload["warning_only_resource_count"] == 0
    assert payload["classification_summary"]["enabled"] is False

    human_mop = Path(payload["artifacts"]["human_mop_markdown_path"]).read_text(encoding="utf-8")
    installation_notes = Path(payload["artifacts"]["installation_notes_path"]).read_text(
        encoding="utf-8"
    )
    pdf_bytes = Path(payload["artifacts"]["human_mop_pdf_path"]).read_bytes()
    manifest = json.loads(
        Path(payload["artifacts"]["artifact_manifest_path"]).read_text(encoding="utf-8")
    )

    assert pdf_bytes.startswith(b"%PDF-1.4")
    assert manifest["mop_id"] == payload["mop_id"]
    assert manifest["external_calls"] == {
        "kubernetes": True,
        "helm": True,
        "qdrant": False,
        "datastores": True,
    }
    assert manifest["mcp"]["sources_attempted"] == payload["mcp_sources_attempted"]
    for section in REQUIRED_HUMAN_MOP_SECTIONS:
        assert section in human_mop
    assert "artifact_type: installation_notes" in installation_notes
    assert "phase_id: install_helm_releases" in installation_notes
    assert "step_id:" in installation_notes

    mop_id = payload["mop_id"]
    get_response = client.get(f"/mop-creation/{mop_id}")
    latest_response = client.get("/mop-creation/latest")

    assert get_response.status_code == 200
    assert latest_response.status_code == 200
    assert get_response.json()["mop_id"] == mop_id
    assert latest_response.json()["mop_id"] == mop_id

    classification_response = client.get(f"/mop-creation/{mop_id}/classification")
    assert classification_response.status_code == 404

    artifacts_response = client.get(f"/mop-creation/{mop_id}/artifacts")
    assert artifacts_response.status_code == 200
    artifact_index = artifacts_response.json()
    assert artifact_index["mop_id"] == mop_id
    assert any(item["path"] == "artifact.json" for item in artifact_index["files"])

    preview_response = client.get(
        f"/mop-creation/{mop_id}/artifacts/preview",
        params={"path": "artifact.json"},
    )
    assert preview_response.status_code == 200
    assert preview_response.json()["content"].startswith("{")

    installation_notes_name = Path(payload["artifacts"]["installation_notes_path"]).name
    download_response = client.get(
        f"/mop-creation/{mop_id}/artifacts/download",
        params={"path": installation_notes_name},
    )
    assert download_response.status_code == 200
    content_disposition = download_response.headers["content-disposition"]
    assert content_disposition.startswith("attachment;")
    assert f'filename="{installation_notes_name}"' in content_disposition
    assert download_response.headers["content-type"].startswith("text/markdown")
    assert download_response.content == Path(
        payload["artifacts"]["installation_notes_path"]
    ).read_bytes()

    traversal_response = client.get(
        f"/mop-creation/{mop_id}/artifacts/preview",
        params={"path": "../settings.yaml"},
    )
    assert traversal_response.status_code == 403

    traversal_download_response = client.get(
        f"/mop-creation/{mop_id}/artifacts/download",
        params={"path": "../settings.yaml"},
    )
    assert traversal_download_response.status_code == 403

    pdf_download_response = client.get(
        f"/mop-creation/{mop_id}/artifacts/download",
        params={"path": Path(payload["artifacts"]["human_mop_pdf_path"]).name},
    )
    assert pdf_download_response.status_code == 403

    generated_dir = Path(payload["artifacts"]["run_directory_path"]) / "generated"
    generated_file = generated_dir / "synthetic.yaml"
    generated_file.write_text("kind: ConfigMap\nmetadata:\n  name: synthetic\n", encoding="utf-8")
    ignored_file = generated_dir / "ignore.bin"
    ignored_file.write_bytes(b"not an artifact")

    archive_response = client.get(
        f"/mop-creation/{mop_id}/artifacts/archive",
        params={"prefix": "generated/"},
    )
    assert archive_response.status_code == 200
    assert archive_response.headers["content-type"] == "application/zip"
    archive_path = Path(payload["artifacts"]["run_directory_path"]) / "generated.zip"
    assert archive_path.is_file()
    assert archive_response.content == archive_path.read_bytes()
    with zipfile.ZipFile(archive_path) as archive:
        assert "synthetic.yaml" in archive.namelist()
        assert "ignore.bin" not in archive.namelist()

    traversal_archive_response = client.get(
        f"/mop-creation/{mop_id}/artifacts/archive",
        params={"prefix": "../"},
    )
    assert traversal_archive_response.status_code == 403

    delete_response = client.delete(f"/mop-creation/{mop_id}")
    assert delete_response.status_code == 200
    delete_payload = delete_response.json()
    assert delete_payload["status"] == "deleted"
    assert delete_payload["mop_id"] == mop_id
    assert delete_payload["removed_file_count"] >= 1
    assert not Path(payload["artifacts"]["run_directory_path"]).exists()
    assert client.get(f"/mop-creation/{mop_id}").status_code == 404


def test_latest_returns_404_before_generation() -> None:
    client = TestClient(create_app(Settings()))

    response = client.get("/mop-creation/latest")

    assert response.status_code == 404


def test_delete_all_mop_artifacts_requires_confirmation_and_cleans_storage(tmp_path: Path) -> None:
    client = TestClient(create_app(_settings(tmp_path)))
    first = tmp_path / "mop-one"
    second = tmp_path / "mop-two"
    first.mkdir()
    second.mkdir()
    (first / "artifact.json").write_text("{}", encoding="utf-8")
    (second / "machine_execution_plan.yaml").write_text("machine_execution_plan: {}", encoding="utf-8")

    denied = client.delete("/mop-creation", params={"confirm": "false"})

    assert denied.status_code == 403
    assert first.exists()
    assert second.exists()

    response = client.delete("/mop-creation", params={"confirm": "true"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "deleted"
    assert payload["removed_mop_count"] == 2
    assert payload["removed_file_count"] == 2
    assert not first.exists()
    assert not second.exists()


def test_mcp_tool_contract_lists_and_invokes_tools(tmp_path: Path) -> None:
    client = TestClient(create_app(_settings(tmp_path)))

    tools_response = client.get("/mcp/tools")

    assert tools_response.status_code == 200
    tool_names = {tool["name"] for tool in tools_response.json()["tools"]}
    assert {
        "mop_creation_health",
        "mop_creation_generate",
        "mop_creation_get",
        "mop_creation_latest",
        "mop_creation_classification",
        "mop_creation_artifacts",
        "mop_creation_artifact_preview",
        "mop_creation_delete",
        "mop_creation_delete_all",
        "mop_creation_effective_config",
    }.issubset(tool_names)

    generate_response = client.post(
        "/mcp/tools/mop_creation_generate",
        json={"target_namespace": "bosgenesis-copy-dev", "caller": "codex"},
    )

    assert generate_response.status_code == 200
    result = generate_response.json()["result"]
    assert result["status"] == "accepted"
    assert result["run_id"]
    assert result["correlation_id"]
    assert result["target_namespace"] == "bosgenesis-copy-dev"
    generated = _wait_for_generated(client, result["mop_id"])
    assert generated["status"] == "generated"
    assert Path(generated["artifacts"]["human_mop_pdf_path"]).is_file()


def test_mcp_json_rpc_tools_call() -> None:
    client = TestClient(create_app(Settings()))

    initialize = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "init-1",
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "0.0.1"},
            },
        },
    )
    assert initialize.status_code == 200
    assert initialize.json()["result"]["capabilities"]["tools"]["listChanged"] is False

    tools = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": "list-1", "method": "tools/list"},
    )
    assert tools.status_code == 200
    assert tools.json()["result"]["tools"][0]["inputSchema"]

    response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": "request-1",
            "method": "tools/call",
            "params": {"name": "mop_creation_health", "arguments": {}},
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "request-1"
    assert payload["result"]["isError"] is False
    assert payload["result"]["content"][0]["type"] == "text"
    assert "bosgenesis-mop-creation-agent" in payload["result"]["content"][0]["text"]
