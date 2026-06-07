import json
import zipfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import FileResponse

from bosgenesis_mop_creation_agent.api.mcp import call_mcp_tool, mcp_creation_tools
from bosgenesis_mop_creation_agent import __version__
from bosgenesis_mop_creation_agent.common.logging import get_logger
from bosgenesis_mop_creation_agent.config.settings import Settings
from bosgenesis_mop_creation_agent.core.orchestrator import MoPCreationOrchestrator
from bosgenesis_mop_creation_agent.models.requests import (
    MoPGenerationRequest,
    NamespaceSwitchRequest,
    QdrantIngestMoPRequest,
)
from bosgenesis_mop_creation_agent.models.responses import (
    McpToolResponse,
    MoPGenerationResponse,
    NamespaceStateResponse,
)

router = APIRouter()
logger = get_logger(__name__)


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _orchestrator(request: Request) -> MoPCreationOrchestrator:
    return request.app.state.orchestrator


@router.get("/health")
def health(request: Request) -> dict[str, Any]:
    settings = _settings(request)
    namespace_state = _orchestrator(request).namespace_state()
    logger.info(
        "health_checked",
        extra={
            "agent_name": settings.agent.name,
            "source_namespace": namespace_state["active_namespace"],
        },
    )
    return {
        "status": "ok",
        "agent": settings.agent.name,
        "version": __version__,
        "release_candidate": settings.release.release_candidate,
        "values_schema_version": settings.release.values_schema_version,
        "source_namespace": namespace_state["active_namespace"],
        "configured_source_namespace": namespace_state["configured_namespace"],
        "session_context_key": namespace_state["session_context_key"],
        "runtime_mode": settings.agent.mode,
    }


@router.get("/config/effective")
def effective_config(request: Request) -> dict[str, Any]:
    settings = _settings(request)
    logger.info("effective_config_requested", extra={"agent_name": settings.agent.name})
    return settings.redacted_dict()


@router.get("/namespace", response_model=NamespaceStateResponse)
def get_namespace(request: Request) -> dict[str, Any]:
    state = _orchestrator(request).namespace_state()
    logger.info(
        "runtime_namespace_requested",
        extra={
            "active_namespace": state["active_namespace"],
            "session_context_key": state["session_context_key"],
        },
    )
    return state


@router.put("/namespace", response_model=NamespaceStateResponse)
def set_namespace(
    request_body: NamespaceSwitchRequest,
    request: Request,
) -> dict[str, Any]:
    state = _orchestrator(request).set_source_namespace(
        request_body.namespace,
        caller=request_body.caller,
    )
    logger.info(
        "runtime_namespace_updated",
        extra={
            "caller": request_body.caller,
            "active_namespace": state["active_namespace"],
            "session_context_key": state["session_context_key"],
        },
    )
    return state


@router.post(
    "/mop-creation/generate",
    response_model=MoPGenerationResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_mop(request_body: MoPGenerationRequest, request: Request) -> MoPGenerationResponse:
    logger.info(
        "mop_generation_requested",
        extra={
            "caller": request_body.caller,
            "target_namespace": request_body.target_namespace,
            "phase": "phase5_classification_safety",
            "external_calls": "governed_mcp_read_only",
        },
    )
    return _orchestrator(request).submit_generation(request_body)


@router.get("/mop-creation/latest", response_model=MoPGenerationResponse)
def latest_mop(request: Request) -> MoPGenerationResponse:
    response = _orchestrator(request).latest()
    if response is None:
        raise HTTPException(
            status_code=404,
            detail={
                "status": "not_found",
                "error": "no_mop_generation_runs",
                "message": "No MoP generation run has been started yet.",
                "next_step": "Call POST /mop-creation/generate, then poll GET /mop-creation/{mop_id}.",
            },
        )
    return response


@router.get("/mop-creation/{mop_id}", response_model=MoPGenerationResponse)
def get_mop(mop_id: str, request: Request) -> MoPGenerationResponse:
    response = _orchestrator(request).get(mop_id)
    if response is None:
        raise HTTPException(
            status_code=404,
            detail=_missing_mop_detail(mop_id, "response"),
        )
    return response


@router.delete("/mop-creation/{mop_id}")
def delete_mop(mop_id: str, request: Request) -> dict[str, Any]:
    result = _orchestrator(request).delete_mop(mop_id)
    if result.get("status") == "denied":
        raise HTTPException(status_code=403, detail=result)
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=result)
    return result


@router.delete("/mop-creation")
def delete_all_mops(confirm: bool, request: Request) -> dict[str, Any]:
    result = _orchestrator(request).delete_all_mops(confirm=confirm)
    if result.get("status") == "denied":
        raise HTTPException(status_code=403, detail=result)
    return result


@router.post("/references/qdrant/ingest-mop")
def ingest_mop_references(
    request_body: QdrantIngestMoPRequest,
    request: Request,
) -> dict[str, Any]:
    settings = _settings(request)
    if not settings.retrieval.qdrant.ingestion_api_enabled:
        raise HTTPException(
            status_code=403,
            detail={
                "status": "disabled",
                "error": "qdrant_ingestion_api_disabled",
            },
        )
    if not request_body.confirm:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "denied",
                "error": "confirm_required",
                "required_confirm": True,
            },
        )
    result = _orchestrator(request).ingest_mop_to_qdrant(request_body.mop_id)
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=result)
    if result.get("status") in {"disabled", "unavailable"}:
        raise HTTPException(status_code=503, detail=result)
    return result


@router.get("/mop-creation/{mop_id}/classification")
def get_mop_classification(mop_id: str, request: Request) -> dict[str, Any]:
    summary = _orchestrator(request).classification(mop_id)
    if summary is None:
        raise HTTPException(
            status_code=404,
            detail=_missing_mop_detail(mop_id, "classification summary"),
        )
    return summary


@router.get("/mop-creation/{mop_id}/artifacts")
def get_mop_artifact_index(mop_id: str, request: Request) -> dict[str, Any]:
    index = _orchestrator(request).artifact_index(mop_id)
    if index is None:
        raise HTTPException(status_code=404, detail=_missing_mop_detail(mop_id, "artifacts"))
    return index


@router.get("/mop-creation/{mop_id}/artifacts/preview")
def preview_mop_artifact(mop_id: str, path: str, request: Request) -> dict[str, Any]:
    preview = _orchestrator(request).artifact_preview(mop_id, path)
    if preview is None:
        raise HTTPException(status_code=404, detail=_missing_mop_detail(mop_id, "artifacts"))
    if preview.get("status") == "denied":
        raise HTTPException(status_code=403, detail=preview)
    if preview.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=preview)
    if preview.get("status") == "disabled":
        raise HTTPException(status_code=403, detail=preview)
    return preview


@router.get("/mop-creation/{mop_id}/artifacts/download")
def download_mop_artifact(mop_id: str, path: str, request: Request) -> FileResponse:
    download = _orchestrator(request).artifact_download(mop_id, path)
    if download is None:
        raise HTTPException(status_code=404, detail=_missing_mop_detail(mop_id, "artifacts"))
    if download.get("status") == "denied":
        raise HTTPException(status_code=403, detail=download)
    if download.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=download)
    return FileResponse(
        path=download["file_path"],
        filename=download["filename"],
        media_type=_artifact_media_type(download["filename"]),
    )


@router.get("/mop-creation/{mop_id}/artifacts/archive")
def archive_mop_artifacts(mop_id: str, prefix: str, request: Request) -> FileResponse:
    archive = _orchestrator(request).artifact_archive(mop_id, prefix)
    if archive is None:
        raise HTTPException(status_code=404, detail=_missing_mop_detail(mop_id, "artifacts"))
    if archive.get("status") == "denied":
        raise HTTPException(status_code=403, detail=archive)
    if archive.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=archive)
    directory_path = Path(archive["directory_path"])
    archive_path = Path(archive["archive_path"])
    _write_artifact_archive(
        directory_path=directory_path,
        archive_path=archive_path,
        allowed_extensions=archive["allowed_extensions"],
    )
    return FileResponse(
        path=str(archive_path),
        filename=archive["filename"],
        media_type="application/zip",
    )


def _artifact_media_type(filename: str) -> str:
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix == "md":
        return "text/markdown; charset=utf-8"
    if suffix in {"yaml", "yml"}:
        return "application/yaml; charset=utf-8"
    if suffix == "json":
        return "application/json"
    if suffix == "pdf":
        return "application/pdf"
    return "application/octet-stream"


def _write_artifact_archive(
    *,
    directory_path: Path,
    archive_path: Path,
    allowed_extensions: set[str],
) -> None:
    with zipfile.ZipFile(archive_path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in sorted(path for path in directory_path.rglob("*") if path.is_file()):
            if file_path.suffix.lower() not in allowed_extensions:
                continue
            archive.write(file_path, arcname=file_path.relative_to(directory_path).as_posix())


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
        raise HTTPException(
            status_code=400,
            detail={
                "status": "unsupported",
                "error": "unsupported_mcp_method",
                "method": method,
                "supported_methods": [
                    "initialize",
                    "notifications/initialized",
                    "tools/list",
                    "tools/call",
                ],
            },
        )

    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _missing_mop_detail(mop_id: str, artifact_type: str) -> dict[str, Any]:
    return {
        "status": "not_found",
        "error": "mop_run_not_found",
        "mop_id": mop_id,
        "artifact_type": artifact_type,
        "message": f"MoP {artifact_type} was not found for the provided mop_id.",
        "next_step": "Check GET /mop-creation/latest or start a new run with POST /mop-creation/generate.",
    }
