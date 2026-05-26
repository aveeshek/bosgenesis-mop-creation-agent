import json
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from bosgenesis_mop_creation_agent.api.mcp import call_mcp_tool, mcp_creation_tools
from bosgenesis_mop_creation_agent import __version__
from bosgenesis_mop_creation_agent.common.logging import get_logger
from bosgenesis_mop_creation_agent.config.settings import Settings
from bosgenesis_mop_creation_agent.core.orchestrator import PhaseOneMoPCreationOrchestrator
from bosgenesis_mop_creation_agent.models.requests import MoPGenerationRequest
from bosgenesis_mop_creation_agent.models.responses import (
    McpToolResponse,
    MoPGenerationResponse,
)

router = APIRouter()
logger = get_logger(__name__)


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _orchestrator(request: Request) -> PhaseOneMoPCreationOrchestrator:
    return request.app.state.orchestrator


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


@router.post("/mop-creation/generate", response_model=MoPGenerationResponse)
def generate_mop(request_body: MoPGenerationRequest, request: Request) -> MoPGenerationResponse:
    logger.info(
        "mop_generation_stub_requested",
        extra={
            "caller": request_body.caller,
            "target_namespace": request_body.target_namespace,
            "phase": "phase1_contract",
            "external_calls": "disabled",
        },
    )
    return _orchestrator(request).generate(request_body)


@router.get("/mop-creation/latest", response_model=MoPGenerationResponse)
def latest_mop(request: Request) -> MoPGenerationResponse:
    response = _orchestrator(request).latest()
    if response is None:
        raise HTTPException(status_code=404, detail="No MoP generation responses found.")
    return response


@router.get("/mop-creation/{mop_id}", response_model=MoPGenerationResponse)
def get_mop(mop_id: str, request: Request) -> MoPGenerationResponse:
    response = _orchestrator(request).get(mop_id)
    if response is None:
        raise HTTPException(status_code=404, detail=f"MoP response not found: {mop_id}")
    return response


@router.get("/mcp/tools")
def list_mcp_tools() -> dict[str, Any]:
    return {"tools": [tool.model_dump(mode="json") for tool in mcp_creation_tools()]}


@router.post("/mcp/tools/{tool_name}", response_model=McpToolResponse)
def invoke_mcp_tool(tool_name: str, payload: dict[str, Any], request: Request) -> McpToolResponse:
    try:
        result = call_mcp_tool(
            tool_name=tool_name,
            arguments=payload,
            settings=_settings(request),
            orchestrator=_orchestrator(request),
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"MCP tool not found: {tool_name}") from exc
    return McpToolResponse(tool=tool_name, result=result)


@router.post("/mcp")
def invoke_mcp_json_rpc(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    method = payload.get("method")
    request_id = payload.get("id")

    if method == "initialize":
        result = {
            "protocolVersion": payload.get("params", {}).get("protocolVersion", "2024-11-05"),
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {
                "name": "bosgenesis-mop-creation-agent",
                "version": __version__,
            },
        }
    elif method == "notifications/initialized":
        result = {}
    elif method == "tools/list":
        result = {
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.input_schema,
                }
                for tool in mcp_creation_tools()
            ]
        }
    elif method == "tools/call":
        params = payload.get("params") or {}
        tool_name = params.get("name")
        arguments = params.get("arguments") or {}
        if not tool_name:
            raise HTTPException(status_code=400, detail="MCP tools/call requires params.name.")
        try:
            result = call_mcp_tool(
                tool_name=tool_name,
                arguments=arguments,
                settings=_settings(request),
                orchestrator=_orchestrator(request),
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=f"MCP tool not found: {tool_name}") from exc
        result = {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, default=str),
                }
            ],
            "isError": False,
        }
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported MCP method: {method}")

    return {"jsonrpc": "2.0", "id": request_id, "result": result}
