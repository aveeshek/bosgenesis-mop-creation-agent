from datetime import UTC, datetime
from pathlib import Path
from threading import Lock, Thread
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
        self._artifact_writer = LocalArtifactWriter(
            settings.agent.local_storage_path,
            settings.llm,
        )
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
        self._lock = Lock()

    def generate(self, request: MoPGenerationRequest) -> MoPGenerationResponse:
        source_namespace = request.source_namespace or self._settings.agent.source_namespace
        return self._generate_with_ids(
            request=request,
            mop_id=str(uuid4()),
            run_id=str(uuid4()),
            correlation_id=request.correlation_id or str(uuid4()),
            source_namespace=source_namespace,
            created_at=datetime.now(UTC),
        )

    def submit_generation(self, request: MoPGenerationRequest) -> MoPGenerationResponse:
        source_namespace = request.source_namespace or self._settings.agent.source_namespace
        mop_id = str(uuid4())
        run_id = str(uuid4())
        correlation_id = request.correlation_id or str(uuid4())
        created_at = datetime.now(UTC)
        response = self._accepted_response(
            request=request,
            mop_id=mop_id,
            run_id=run_id,
            correlation_id=correlation_id,
            source_namespace=source_namespace,
            created_at=created_at,
        )
        with self._lock:
            self._responses[mop_id] = response
            self._latest_mop_id = mop_id
        worker = Thread(
            target=self._generate_background,
            kwargs={
                "request": request,
                "mop_id": mop_id,
                "run_id": run_id,
                "correlation_id": correlation_id,
                "source_namespace": source_namespace,
                "created_at": created_at,
            },
            daemon=True,
        )
        worker.start()
        return response

    def _generate_background(
        self,
        *,
        request: MoPGenerationRequest,
        mop_id: str,
        run_id: str,
        correlation_id: str,
        source_namespace: str,
        created_at: datetime,
    ) -> None:
        try:
            response = self._generate_with_ids(
                request=request,
                mop_id=mop_id,
                run_id=run_id,
                correlation_id=correlation_id,
                source_namespace=source_namespace,
                created_at=created_at,
            )
        except Exception as exc:  # pragma: no cover - defensive production guard
            response = self._accepted_response(
                request=request,
                mop_id=mop_id,
                run_id=run_id,
                correlation_id=correlation_id,
                source_namespace=source_namespace,
                created_at=created_at,
            )
            response.status = "failed"
            response.warning_count = 1
            response.warnings = [f"mop_generation_failed:{exc}"]
        with self._lock:
            self._responses[mop_id] = response
            self._latest_mop_id = mop_id

    def _generate_with_ids(
        self,
        *,
        request: MoPGenerationRequest,
        mop_id: str,
        run_id: str,
        correlation_id: str,
        source_namespace: str,
        created_at: datetime,
    ) -> MoPGenerationResponse:
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
            warning_count=len(artifact_result.warnings),
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
            warnings=artifact_result.warnings,
            created_at=created_at,
            content=artifact_result.human_mop_content if request.return_content else None,
            installation_notes_content=artifact_result.installation_notes_content
            if request.return_content
            else None,
        )

        with self._lock:
            self._responses[mop_id] = response
            if classification:
                self._classifications[mop_id] = classification
            self._latest_mop_id = mop_id
        return response

    def _accepted_response(
        self,
        *,
        request: MoPGenerationRequest,
        mop_id: str,
        run_id: str,
        correlation_id: str,
        source_namespace: str,
        created_at: datetime,
    ) -> MoPGenerationResponse:
        run_dir = Path(self._settings.agent.local_storage_path) / mop_id
        return MoPGenerationResponse(
            status="accepted",
            mop_id=mop_id,
            run_id=run_id,
            correlation_id=correlation_id,
            source_namespace=source_namespace,
            target_namespace=request.target_namespace,
            local_file_path="",
            mongo_saved=False,
            qdrant_reference_count=0,
            qdrant_lookup_status="not_executed",
            classification_summary=_classification_summary(None),
            warning_count=0,
            trace_ids=TraceIds(
                langfuse=f"stub-langfuse-{run_id}",
                signoz=f"stub-signoz-{run_id}",
            ),
            artifacts=ArtifactMetadata(
                run_directory_path=str(run_dir),
                artifact_manifest_path=str(run_dir / "artifact.json"),
                human_mop_markdown_path="",
                human_mop_pdf_path="",
                installation_notes_path="",
            ),
            warnings=[],
            created_at=created_at,
        )

    def get(self, mop_id: str) -> MoPGenerationResponse | None:
        with self._lock:
            return self._responses.get(mop_id)

    def latest(self) -> MoPGenerationResponse | None:
        with self._lock:
            if self._latest_mop_id is None:
                return None
            return self._responses[self._latest_mop_id]

    def classification(self, mop_id: str) -> dict | None:
        with self._lock:
            classification = self._classifications.get(mop_id)
        if classification is None:
            return None
        return _classification_summary(classification, include_resources=True)

    def artifact_index(self, mop_id: str) -> dict | None:
        response = self.get(mop_id)
        if response is None:
            return None
        run_dir = Path(response.artifacts.run_directory_path).resolve()
        if not run_dir.is_dir():
            return None
        files = []
        for path in sorted(item for item in run_dir.rglob("*") if item.is_file()):
            relative_path = path.relative_to(run_dir).as_posix()
            files.append(
                {
                    "path": relative_path,
                    "size_bytes": path.stat().st_size,
                    "previewable": path.suffix.lower()
                    in self._settings.features.artifact_preview.allowed_extensions,
                }
            )
        return {
            "mop_id": mop_id,
            "run_directory_path": str(run_dir),
            "preview_enabled": self._settings.features.artifact_preview.enabled,
            "max_preview_bytes": self._settings.features.artifact_preview.max_bytes,
            "files": files,
        }

    def artifact_preview(self, mop_id: str, relative_path: str) -> dict | None:
        response = self.get(mop_id)
        if response is None:
            return None
        preview_settings = self._settings.features.artifact_preview
        if not preview_settings.enabled:
            return {
                "status": "disabled",
                "mop_id": mop_id,
                "path": relative_path,
                "content": None,
            }
        run_dir = Path(response.artifacts.run_directory_path).resolve()
        target = (run_dir / relative_path).resolve()
        if not _is_safe_artifact_path(run_dir, target):
            return {
                "status": "denied",
                "mop_id": mop_id,
                "path": relative_path,
                "error": "path_outside_artifact_directory",
            }
        if target.suffix.lower() not in preview_settings.allowed_extensions:
            return {
                "status": "denied",
                "mop_id": mop_id,
                "path": relative_path,
                "error": "extension_not_previewable",
            }
        if not target.is_file():
            return {
                "status": "not_found",
                "mop_id": mop_id,
                "path": relative_path,
                "error": "artifact_file_not_found",
            }
        content_bytes = target.read_bytes()
        truncated = len(content_bytes) > preview_settings.max_bytes
        content = content_bytes[: preview_settings.max_bytes].decode("utf-8", errors="replace")
        return {
            "status": "ok",
            "mop_id": mop_id,
            "path": target.relative_to(run_dir).as_posix(),
            "size_bytes": len(content_bytes),
            "truncated": truncated,
            "content": content,
        }


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


def _is_safe_artifact_path(run_dir: Path, target: Path) -> bool:
    try:
        target.relative_to(run_dir)
    except ValueError:
        return False
    return True
