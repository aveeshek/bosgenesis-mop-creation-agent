from typing import Any

from bosgenesis_mop_creation_agent import __version__
from bosgenesis_mop_creation_agent.config.settings import Settings
from bosgenesis_mop_creation_agent.core.orchestrator import MoPCreationOrchestrator
from bosgenesis_mop_creation_agent.models.requests import MoPGenerationRequest
from bosgenesis_mop_creation_agent.models.responses import McpToolDefinition


def mcp_creation_tools() -> list[McpToolDefinition]:
    return [
        McpToolDefinition(
            name="mop_creation_health",
            description="Return MoP Creation Agent health metadata.",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        ),
        McpToolDefinition(
            name="mop_creation_generate",
            description="Create snapshot-backed and MCP-enriched local MoP artifacts.",
            input_schema=MoPGenerationRequest.model_json_schema(),
        ),
        McpToolDefinition(
            name="mop_creation_get",
            description="Get a MoP generation response by mop_id.",
            input_schema={
                "type": "object",
                "properties": {"mop_id": {"type": "string"}},
                "required": ["mop_id"],
                "additionalProperties": False,
            },
        ),
        McpToolDefinition(
            name="mop_creation_latest",
            description="Get the latest MoP generation response.",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        ),
        McpToolDefinition(
            name="mop_creation_classification",
            description="Get the classification and safety summary for a generated MoP.",
            input_schema={
                "type": "object",
                "properties": {"mop_id": {"type": "string"}},
                "required": ["mop_id"],
                "additionalProperties": False,
            },
        ),
        McpToolDefinition(
            name="mop_creation_effective_config",
            description="Return redacted effective configuration.",
            input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        ),
    ]


def call_mcp_tool(
    tool_name: str,
    arguments: dict[str, Any],
    settings: Settings,
    orchestrator: MoPCreationOrchestrator,
) -> dict[str, Any]:
    if tool_name == "mop_creation_health":
        return {
            "status": "ok",
            "agent": settings.agent.name,
            "version": __version__,
            "source_namespace": settings.agent.source_namespace,
            "runtime_mode": settings.agent.mode,
        }
    if tool_name == "mop_creation_generate":
        request = MoPGenerationRequest.model_validate(arguments)
        return orchestrator.generate(request).model_dump(mode="json")
    if tool_name == "mop_creation_get":
        response = orchestrator.get(str(arguments["mop_id"]))
        if response is None:
            return {"status": "not_found", "mop_id": arguments["mop_id"]}
        return response.model_dump(mode="json")
    if tool_name == "mop_creation_latest":
        response = orchestrator.latest()
        if response is None:
            return {"status": "not_found"}
        return response.model_dump(mode="json")
    if tool_name == "mop_creation_classification":
        summary = orchestrator.classification(str(arguments["mop_id"]))
        if summary is None:
            return {"status": "not_found", "mop_id": arguments["mop_id"]}
        return summary
    if tool_name == "mop_creation_effective_config":
        return settings.redacted_dict()
    raise KeyError(tool_name)
