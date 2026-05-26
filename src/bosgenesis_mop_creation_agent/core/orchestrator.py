from datetime import UTC, datetime
from uuid import uuid4

from bosgenesis_mop_creation_agent.config.settings import Settings
from bosgenesis_mop_creation_agent.models.requests import MoPGenerationRequest
from bosgenesis_mop_creation_agent.models.responses import (
    ArtifactMetadata,
    MoPGenerationResponse,
    TraceIds,
)


class PhaseOneMoPCreationOrchestrator:
    """Phase 1 contract orchestrator with no external system calls."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._responses: dict[str, MoPGenerationResponse] = {}
        self._latest_mop_id: str | None = None

    def generate(self, request: MoPGenerationRequest) -> MoPGenerationResponse:
        source_namespace = request.source_namespace or self._settings.agent.source_namespace
        mop_id = str(uuid4())
        run_id = str(uuid4())
        correlation_id = request.correlation_id or str(uuid4())
        created_at = datetime.now(UTC)
        file_stem = f"mop-{source_namespace}-to-{request.target_namespace}-{created_at:%Y%m%dT%H%M%SZ}"
        base_path = self._settings.agent.local_storage_path.rstrip("/")

        human_mop_pdf_path = f"{base_path}/{file_stem}.pdf"
        installation_notes_path = f"{base_path}/{file_stem}.installation.md"
        warnings = [
            "phase1_stub_response: no MoP artifacts are generated yet",
            "phase1_no_external_calls: Kubernetes, Helm, Qdrant, and datastore integrations were not invoked",
        ]

        response = MoPGenerationResponse(
            status="accepted",
            mop_id=mop_id,
            run_id=run_id,
            correlation_id=correlation_id,
            source_namespace=source_namespace,
            target_namespace=request.target_namespace,
            local_file_path=human_mop_pdf_path,
            mongo_saved=False,
            qdrant_reference_count=0,
            qdrant_lookup_status="not_executed",
            resource_count=0,
            helm_release_count=0,
            excluded_resource_count=0,
            warning_count=len(warnings),
            trace_ids=TraceIds(
                langfuse=f"stub-langfuse-{run_id}",
                signoz=f"stub-signoz-{run_id}",
            ),
            artifacts=ArtifactMetadata(
                human_mop_pdf_path=human_mop_pdf_path,
                installation_notes_path=installation_notes_path,
            ),
            warnings=warnings,
            created_at=created_at,
            installation_notes_content=(
                "# Phase 1 Stub Installation Notes\n\n"
                "No installation notes are generated in Phase 1."
            )
            if request.return_content
            else None,
        )

        self._responses[mop_id] = response
        self._latest_mop_id = mop_id
        return response

    def get(self, mop_id: str) -> MoPGenerationResponse | None:
        return self._responses.get(mop_id)

    def latest(self) -> MoPGenerationResponse | None:
        if self._latest_mop_id is None:
            return None
        return self._responses[self._latest_mop_id]

