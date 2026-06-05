from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TraceIds(BaseModel):
    langfuse: str | None = None
    signoz: str | None = None


class ArtifactMetadata(BaseModel):
    run_directory_path: str
    artifact_manifest_path: str
    human_mop_markdown_path: str
    human_mop_pdf_path: str
    installation_notes_path: str


class MoPGenerationResponse(BaseModel):
    status: str
    mop_id: str
    run_id: str
    correlation_id: str
    source_namespace: str
    target_namespace: str
    session_context_key: str | None = None
    local_file_path: str
    mongo_saved: bool = False
    qdrant_reference_count: int = 0
    qdrant_lookup_status: str = "not_executed"
    memory_status: str = "not_executed"
    memory_read_count: int = 0
    memory_written_count: int = 0
    inventory_source: str | None = None
    source_snapshot_id: str | None = None
    snapshot_sources_attempted: list[str] = Field(default_factory=list)
    mcp_sources_attempted: list[str] = Field(default_factory=list)
    resource_count: int = 0
    helm_release_count: int = 0
    helm_managed_resource_count: int = 0
    raw_k8s_resource_count: int = 0
    excluded_resource_count: int = 0
    warning_only_resource_count: int = 0
    classification_summary: dict[str, Any] = Field(default_factory=dict)
    warning_count: int = 0
    trace_ids: TraceIds = Field(default_factory=TraceIds)
    artifacts: ArtifactMetadata
    warnings: list[str] = Field(default_factory=list)
    created_at: datetime
    content: str | None = None
    installation_notes_content: str | None = None


class McpToolDefinition(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]


class McpToolResponse(BaseModel):
    tool: str
    result: dict[str, Any]


class NamespaceStateResponse(BaseModel):
    configured_namespace: str
    active_namespace: str
    session_context_key: str
    memory_primary_key: str
    updated_at: datetime | None = None
    updated_by: str | None = None
