from datetime import UTC, datetime
from uuid import uuid4

from bosgenesis_mop_creation_agent.classification.models import ClassificationSummary
from bosgenesis_mop_creation_agent.classification.resource_classifier import classify_inventory
from bosgenesis_mop_creation_agent.config.settings import Settings
from bosgenesis_mop_creation_agent.models.requests import MoPGenerationRequest
from bosgenesis_mop_creation_agent.models.responses import (
    ArtifactMetadata,
    MoPGenerationResponse,
    TraceIds,
)
from bosgenesis_mop_creation_agent.mcp_clients.data_ingestion_client import DataIngestionClient
from bosgenesis_mop_creation_agent.mcp_clients.enrichment import McpEnrichmentService
from bosgenesis_mop_creation_agent.mcp_clients.helm_manager_client import HelmManagerClient
from bosgenesis_mop_creation_agent.mcp_clients.k8s_inspector_client import K8sInspectorClient
from bosgenesis_mop_creation_agent.rendering.artifact_writer import LocalArtifactWriter
from bosgenesis_mop_creation_agent.sources.clickhouse_snapshot_reader import ClickHouseSnapshotReader
from bosgenesis_mop_creation_agent.sources.postgres_snapshot_reader import PostgresSnapshotReader
from bosgenesis_mop_creation_agent.sources.snapshot_selector import SnapshotSelector


class MoPCreationOrchestrator:
    """Orchestrate stored snapshots plus governed MCP live enrichment."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._artifact_writer = LocalArtifactWriter(settings.agent.local_storage_path)
        self._snapshot_selector = SnapshotSelector(
            postgres_reader=PostgresSnapshotReader(settings.inventory.postgres),
            clickhouse_reader=ClickHouseSnapshotReader(settings.inventory.clickhouse),
        )
        self._mcp_enrichment = McpEnrichmentService(
            k8s_client=K8sInspectorClient.from_settings(settings.mcp.k8s_inspector),
            helm_client=HelmManagerClient.from_settings(settings.mcp.helm_manager),
            data_ingestion_client=DataIngestionClient.from_settings(settings.mcp.data_ingestion_agent),
        )
        self._responses: dict[str, MoPGenerationResponse] = {}
        self._classifications: dict[str, ClassificationSummary] = {}
        self._latest_mop_id: str | None = None

    def generate(self, request: MoPGenerationRequest) -> MoPGenerationResponse:
        source_namespace = request.source_namespace or self._settings.agent.source_namespace
        mop_id = str(uuid4())
        run_id = str(uuid4())
        correlation_id = request.correlation_id or str(uuid4())
        created_at = datetime.now(UTC)
        warnings: list[str] = []
        snapshot_result = self._snapshot_selector.read(source_namespace, request.source_snapshot_id)
        warnings.extend(snapshot_result.warnings)
        enrichment_result = self._mcp_enrichment.enrich(
            namespace=source_namespace,
            correlation_id=correlation_id,
            snapshot_inventory=snapshot_result.inventory,
        )
        warnings.extend(enrichment_result.warnings)
        inventory = enrichment_result.inventory
        classification = classify_inventory(inventory)
        if classification:
            warnings.extend(classification.warnings)
        artifact_result = self._artifact_writer.write(
            mop_id=mop_id,
            run_id=run_id,
            correlation_id=correlation_id,
            source_namespace=source_namespace,
            request=request,
            created_at=created_at,
            warnings=warnings,
            inventory=inventory,
            classification=classification,
            snapshot_sources_attempted=snapshot_result.sources_attempted,
            mcp_sources_attempted=enrichment_result.sources_attempted,
        )

        response = MoPGenerationResponse(
            status="generated",
            mop_id=mop_id,
            run_id=run_id,
            correlation_id=correlation_id,
            source_namespace=source_namespace,
            target_namespace=request.target_namespace,
            local_file_path=artifact_result.human_mop_pdf_path,
            mongo_saved=False,
            qdrant_reference_count=0,
            qdrant_lookup_status="not_executed",
            inventory_source=inventory.source if inventory else None,
            source_snapshot_id=inventory.snapshot_id if inventory else request.source_snapshot_id,
            snapshot_sources_attempted=snapshot_result.sources_attempted,
            mcp_sources_attempted=enrichment_result.sources_attempted,
            resource_count=inventory.resource_count if inventory else 0,
            helm_release_count=inventory.helm_release_count if inventory else 0,
            helm_managed_resource_count=(
                classification.helm_managed_count if classification else 0
            ),
            raw_k8s_resource_count=classification.raw_k8s_count if classification else 0,
            excluded_resource_count=classification.excluded_count if classification else 0,
            warning_only_resource_count=(
                classification.warning_only_count if classification else 0
            ),
            classification_summary=_classification_summary(classification),
            warning_count=len(warnings),
            trace_ids=TraceIds(
                langfuse=f"stub-langfuse-{run_id}",
                signoz=f"stub-signoz-{run_id}",
            ),
            artifacts=ArtifactMetadata(
                run_directory_path=artifact_result.run_directory_path,
                artifact_manifest_path=artifact_result.artifact_manifest_path,
                human_mop_markdown_path=artifact_result.human_mop_markdown_path,
                human_mop_pdf_path=artifact_result.human_mop_pdf_path,
                installation_notes_path=artifact_result.installation_notes_path,
            ),
            warnings=warnings,
            created_at=created_at,
            content=artifact_result.human_mop_content if request.return_content else None,
            installation_notes_content=artifact_result.installation_notes_content
            if request.return_content
            else None,
        )

        self._responses[mop_id] = response
        if classification:
            self._classifications[mop_id] = classification
        self._latest_mop_id = mop_id
        return response

    def get(self, mop_id: str) -> MoPGenerationResponse | None:
        return self._responses.get(mop_id)

    def latest(self) -> MoPGenerationResponse | None:
        if self._latest_mop_id is None:
            return None
        return self._responses[self._latest_mop_id]

    def classification(self, mop_id: str) -> dict | None:
        classification = self._classifications.get(mop_id)
        if classification is None:
            return None
        return _classification_summary(classification, include_resources=True)


PhaseOneMoPCreationOrchestrator = MoPCreationOrchestrator


def _classification_summary(
    classification: ClassificationSummary | None,
    *,
    include_resources: bool = False,
) -> dict:
    if classification is None:
        return {
            "enabled": False,
            "helm_managed_resource_count": 0,
            "raw_k8s_resource_count": 0,
            "excluded_resource_count": 0,
            "warning_only_resource_count": 0,
            "warnings": [],
        }
    summary = {
        "enabled": True,
        "namespace": classification.namespace,
        "helm_managed_resource_count": classification.helm_managed_count,
        "raw_k8s_resource_count": classification.raw_k8s_count,
        "excluded_resource_count": classification.excluded_count,
        "warning_only_resource_count": classification.warning_only_count,
        "warnings": classification.warnings,
    }
    if include_resources:
        summary["resources"] = [
            {
                "kind": item.resource.kind,
                "name": item.resource.name,
                "namespace": item.resource.namespace,
                "category": item.category.value,
                "reason": item.reason,
                "evidence": item.evidence,
                "helm_release_name": item.helm_release_name,
            }
            for item in classification.resources
        ]
    return summary
