from fastapi.testclient import TestClient

from bosgenesis_mop_creation_agent.api.app import create_app
from bosgenesis_mop_creation_agent.config.settings import Settings


def test_generate_get_and_latest_stub_response() -> None:
    client = TestClient(create_app(Settings()))

    response = client.post(
        "/mop-creation/generate",
        json={
            "target_namespace": "bosgenesis-copy-dev",
            "caller": "pytest",
            "correlation_id": "test-correlation-id",
            "return_content": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "accepted"
    assert payload["correlation_id"] == "test-correlation-id"
    assert payload["run_id"]
    assert payload["mop_id"]
    assert payload["trace_ids"]["langfuse"].startswith("stub-langfuse-")
    assert payload["trace_ids"]["signoz"].startswith("stub-signoz-")
    assert payload["artifacts"]["human_mop_pdf_path"].endswith(".pdf")
    assert payload["artifacts"]["installation_notes_path"].endswith(".installation.md")
    assert payload["installation_notes_content"].startswith("# Phase 1 Stub")
    assert payload["qdrant_lookup_status"] == "not_executed"
    assert "Kubernetes, Helm, Qdrant, and datastore integrations were not invoked" in " ".join(
        payload["warnings"]
    )

    mop_id = payload["mop_id"]
    get_response = client.get(f"/mop-creation/{mop_id}")
    latest_response = client.get("/mop-creation/latest")

    assert get_response.status_code == 200
    assert latest_response.status_code == 200
    assert get_response.json()["mop_id"] == mop_id
    assert latest_response.json()["mop_id"] == mop_id


def test_latest_returns_404_before_generation() -> None:
    client = TestClient(create_app(Settings()))

    response = client.get("/mop-creation/latest")

    assert response.status_code == 404


def test_mcp_tool_contract_lists_and_invokes_tools() -> None:
    client = TestClient(create_app(Settings()))

    tools_response = client.get("/mcp/tools")

    assert tools_response.status_code == 200
    tool_names = {tool["name"] for tool in tools_response.json()["tools"]}
    assert {
        "mop_creation_health",
        "mop_creation_generate",
        "mop_creation_get",
        "mop_creation_latest",
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
