from datetime import UTC, datetime
import json
from pathlib import Path
import shutil
from threading import Lock, Thread
from typing import Any
from uuid import uuid4

from bosgenesis_mop_creation_agent.classification.models import ClassificationSummary
from bosgenesis_mop_creation_agent.classification.resource_classifier import classify_inventory
from bosgenesis_mop_creation_agent.config.settings import Settings
from bosgenesis_mop_creation_agent.memory.service import AgentMemoryService
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
from bosgenesis_mop_creation_agent.observability import ObservabilityService
from bosgenesis_mop_creation_agent.rendering.artifact_writer import LocalArtifactWriter
from bosgenesis_mop_creation_agent.retrieval.reference_lookup import ReferenceLookupService
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
        self._reference_lookup = ReferenceLookupService(settings.retrieval.qdrant)
        self._memory = AgentMemoryService(settings.memory)
        self._observability = ObservabilityService(settings.observability)
        self._responses: dict[str, MoPGenerationResponse] = {}
        self._classifications: dict[str, ClassificationSummary] = {}
        self._latest_mop_id: str | None = None
        self._active_source_namespace = settings.agent.source_namespace
        self._namespace_updated_at: datetime | None = None
        self._namespace_updated_by: str | None = None
        self._lock = Lock()

    def generate(self, request: MoPGenerationRequest) -> MoPGenerationResponse:
        source_namespace = request.source_namespace or self.current_source_namespace()
        return self._generate_with_ids(
            request=request,
            mop_id=str(uuid4()),
            run_id=str(uuid4()),
            correlation_id=request.correlation_id or str(uuid4()),
            source_namespace=source_namespace,
            created_at=datetime.now(UTC),
        )

    def submit_generation(self, request: MoPGenerationRequest) -> MoPGenerationResponse:
        source_namespace = request.source_namespace or self.current_source_namespace()
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

    def namespace_state(self) -> dict[str, Any]:
        with self._lock:
            active_namespace = self._active_source_namespace
            updated_at = self._namespace_updated_at
            updated_by = self._namespace_updated_by
        return {
            "configured_namespace": self._settings.agent.source_namespace,
            "active_namespace": active_namespace,
            "session_context_key": _session_context_key(active_namespace),
            "memory_primary_key": _session_context_key(active_namespace),
            "updated_at": updated_at.isoformat() if updated_at else None,
            "updated_by": updated_by,
        }

    def current_source_namespace(self) -> str:
        with self._lock:
            return self._active_source_namespace

    def set_source_namespace(self, namespace: str, *, caller: str) -> dict[str, Any]:
        updated_at = datetime.now(UTC)
        with self._lock:
            self._active_source_namespace = namespace
            self._namespace_updated_at = updated_at
            self._namespace_updated_by = caller
        return self.namespace_state()

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
        namespace_key = _session_context_key(source_namespace)
        observability = self._observability.start_run(
            mop_id=mop_id,
            run_id=run_id,
            correlation_id=correlation_id,
            source_namespace=source_namespace,
            target_namespace=request.target_namespace,
            mode=request.mode.value,
            caller=request.caller,
        )
        observability.record_event(
            event_type="request_received",
            phase="request_received",
            action="generate_mop",
            status="accepted",
            details={
                "source_snapshot_id": request.source_snapshot_id,
                "include_helm": request.include_helm,
                "include_raw_k8s": request.include_raw_k8s,
                "include_validation_steps": request.include_validation_steps,
                "include_rollback_steps": request.include_rollback_steps,
                "include_application_schema": request.include_application_schema,
            },
        )

        with observability.phase("memory_read", action="read_namespace_memory"):
            memory_context = self._memory.read_context(
                namespace_key=namespace_key,
                correlation_id=correlation_id,
                run_id=run_id,
            )
        warnings.extend(memory_context.warnings)
        observability.record_event(
            event_type="memory_read",
            phase="memory_read",
            action="read_namespace_memory",
            status=memory_context.status,
            details={
                "enabled": memory_context.enabled,
                "namespace_key": memory_context.namespace_key,
                "read_count": memory_context.read_count,
                "backend_status": getattr(memory_context, "backend_status", {}),
            },
        )

        with observability.phase("read_latest_snapshot"):
            snapshot_result = self._snapshot_selector.read(source_namespace, request.source_snapshot_id)
        warnings.extend(snapshot_result.warnings)
        observability.record_event(
            event_type="snapshot_read",
            phase="read_latest_snapshot",
            action="read_latest_snapshot",
            status="found" if snapshot_result.inventory else "missing",
            details={
                "sources_attempted": snapshot_result.sources_attempted,
                "inventory_source": snapshot_result.inventory.source if snapshot_result.inventory else None,
                "resource_count": snapshot_result.inventory.resource_count if snapshot_result.inventory else 0,
                "helm_release_count": snapshot_result.inventory.helm_release_count
                if snapshot_result.inventory
                else 0,
            },
        )

        with observability.phase("enrich_from_mcp"):
            enrichment_result = self._mcp_enrichment.enrich(
                namespace=source_namespace,
                correlation_id=correlation_id,
                snapshot_inventory=snapshot_result.inventory,
            )
        warnings.extend(enrichment_result.warnings)
        inventory = enrichment_result.inventory
        observability.record_event(
            event_type="mcp_enrichment",
            phase="enrich_from_mcp",
            action="governed_mcp_read_enrichment",
            status="ok" if inventory else "no_inventory",
            details={
                "sources_attempted": enrichment_result.sources_attempted,
                "resource_count": inventory.resource_count if inventory else 0,
                "helm_release_count": inventory.helm_release_count if inventory else 0,
                "raw_kubectl_or_helm_used": False,
            },
        )

        with observability.phase("classify_resources"):
            classification = classify_inventory(inventory)
        if classification:
            warnings.extend(classification.warnings)
        observability.record_event(
            event_type="classification",
            phase="classify_resources",
            action="classify_helm_raw_excluded_warning_only",
            status="ok" if classification else "skipped_no_inventory",
            details=_classification_summary(classification),
        )

        with observability.phase("qdrant_reference_lookup"):
            reference_result = self._reference_lookup.lookup(
                inventory=inventory,
                classification=classification,
            )
        observability.record_event(
            event_type="qdrant_lookup",
            phase="qdrant_reference_lookup",
            action="read_only_prior_reference_lookup",
            status=reference_result.status,
            details={
                "enabled": reference_result.enabled,
                "reference_count": reference_result.reference_count,
                "query_count": len(reference_result.queries),
                "write_or_ingest_performed": False,
            },
        )

        with observability.phase("render_artifacts"):
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
                qdrant_references=reference_result,
                memory_context=memory_context,
                snapshot_sources_attempted=snapshot_result.sources_attempted,
                mcp_sources_attempted=enrichment_result.sources_attempted,
            )
        artifact_manifest = _read_artifact_manifest(artifact_result.artifact_manifest_path)
        observability.record_event(
            event_type="rendering",
            phase="render_artifacts",
            action="render_human_mop_pdf_installation_notes_and_machine_plan",
            status="generated",
            details={
                "artifact_manifest_path": artifact_result.artifact_manifest_path,
                "human_mop_pdf_renderer": artifact_manifest.get("human_mop_pdf_renderer", {}),
                "artifact_count": len(artifact_manifest.get("artifacts", {})),
            },
        )
        observability.record_event(
            event_type="validation",
            phase="validate_artifact",
            action="validate_generated_steps_have_evidence_or_inference",
            status="ok" if _machine_plan_missing_evidence_count(artifact_manifest) == 0 else "warning",
            details=_machine_plan_evidence_audit(artifact_manifest),
        )
        observability.record_llm_reasoning(
            artifact_manifest.get("bounded_llm_reasoning"),
            artifact_manifest.get("llm_repair_suggestions"),
        )

        with observability.phase("memory_write", action="write_generation_memory_summary"):
            memory_write_result = self._memory.write_generation_summary(
                namespace_key=namespace_key,
                mop_id=mop_id,
                run_id=run_id,
                correlation_id=correlation_id,
                target_namespace=request.target_namespace,
                inventory=inventory,
                classification=classification,
                qdrant_references=reference_result,
                warnings=artifact_result.warnings,
            )
        if memory_write_result.warnings:
            artifact_result.warnings.extend(memory_write_result.warnings)
        observability.record_event(
            event_type="memory_write",
            phase="memory_write",
            action="write_non_secret_generation_summary",
            status=memory_write_result.status,
            details={
                "enabled": memory_write_result.enabled,
                "written_count": memory_write_result.written_count,
                "backend_status": memory_write_result.backend_status,
            },
        )
        _update_artifact_memory_write_metadata(
            artifact_result.artifact_manifest_path,
            {
                "write_status": memory_write_result.status,
                "written_count": memory_write_result.written_count,
                "backend_status": memory_write_result.backend_status,
                "write_warnings": memory_write_result.warnings,
            },
        )
        observability.record_warnings(artifact_result.warnings)
        observability.record_event(
            event_type="response_ready",
            phase="return_response",
            action="build_generation_response",
            status="generated",
            details={
                "warning_count": len(artifact_result.warnings),
                "qdrant_lookup_status": reference_result.status,
                "memory_status": memory_write_result.status
                if memory_write_result.enabled
                else memory_context.status,
            },
        )
        _update_artifact_observability_metadata(
            artifact_result.artifact_manifest_path,
            observability.summary(),
        )

        trace_ids = observability.trace_ids
        effective_helm_release_count = max(
            inventory.helm_release_count if inventory else 0,
            artifact_result.reconstruction_helm_release_count,
        )
        response = MoPGenerationResponse(
            status="generated",
            mop_id=mop_id,
            run_id=run_id,
            correlation_id=correlation_id,
            source_namespace=source_namespace,
            target_namespace=request.target_namespace,
            session_context_key=_session_context_key(source_namespace),
            local_file_path=artifact_result.human_mop_pdf_path,
            mongo_saved=False,
            qdrant_reference_count=reference_result.reference_count,
            qdrant_lookup_status=reference_result.status,
            memory_status=memory_write_result.status
            if memory_write_result.enabled
            else memory_context.status,
            memory_read_count=memory_context.read_count,
            memory_written_count=memory_write_result.written_count,
            inventory_source=inventory.source if inventory else None,
            source_snapshot_id=inventory.snapshot_id if inventory else request.source_snapshot_id,
            snapshot_sources_attempted=snapshot_result.sources_attempted,
            mcp_sources_attempted=enrichment_result.sources_attempted,
            resource_count=inventory.resource_count if inventory else 0,
            helm_release_count=effective_helm_release_count,
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
                langfuse=trace_ids.get("langfuse"),
                signoz=trace_ids.get("signoz"),
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
            session_context_key=_session_context_key(source_namespace),
            local_file_path="",
            mongo_saved=False,
            qdrant_reference_count=0,
            qdrant_lookup_status="not_executed",
            memory_status="not_executed",
            memory_read_count=0,
            memory_written_count=0,
            classification_summary=_classification_summary(None),
            warning_count=0,
            trace_ids=TraceIds(
                langfuse=self._observability.trace_ids(run_id).get("langfuse"),
                signoz=self._observability.trace_ids(run_id).get("signoz"),
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

    def artifact_download(self, mop_id: str, relative_path: str) -> dict | None:
        response = self.get(mop_id)
        if response is None:
            return None
        run_dir = Path(response.artifacts.run_directory_path).resolve()
        target = (run_dir / relative_path).resolve()
        if not _is_safe_artifact_path(run_dir, target):
            return {
                "status": "denied",
                "mop_id": mop_id,
                "path": relative_path,
                "error": "path_outside_artifact_directory",
            }
        if target.suffix.lower() not in self._settings.features.artifact_preview.download_extensions:
            return {
                "status": "denied",
                "mop_id": mop_id,
                "path": relative_path,
                "error": "extension_not_downloadable",
            }
        if not target.is_file():
            return {
                "status": "not_found",
                "mop_id": mop_id,
                "path": relative_path,
                "error": "artifact_file_not_found",
            }
        return {
            "status": "ok",
            "mop_id": mop_id,
            "path": target.relative_to(run_dir).as_posix(),
            "file_path": str(target),
            "filename": target.name,
            "size_bytes": target.stat().st_size,
        }

    def artifact_archive(self, mop_id: str, prefix: str) -> dict | None:
        response = self.get(mop_id)
        if response is None:
            return None
        run_dir = Path(response.artifacts.run_directory_path).resolve()
        normalized_prefix = prefix.strip().replace("\\", "/").strip("/")
        if not normalized_prefix:
            return {
                "status": "denied",
                "mop_id": mop_id,
                "prefix": prefix,
                "error": "archive_prefix_required",
            }
        target_dir = (run_dir / normalized_prefix).resolve()
        if not _is_safe_artifact_path(run_dir, target_dir):
            return {
                "status": "denied",
                "mop_id": mop_id,
                "prefix": prefix,
                "error": "path_outside_artifact_directory",
            }
        if not target_dir.is_dir():
            return {
                "status": "not_found",
                "mop_id": mop_id,
                "prefix": prefix,
                "error": "artifact_directory_not_found",
            }
        archive_path = run_dir / f"{normalized_prefix.replace('/', '-')}.zip"
        allowed_extensions = set(self._settings.features.artifact_preview.allowed_extensions)
        return {
            "status": "ok",
            "mop_id": mop_id,
            "prefix": normalized_prefix + "/",
            "directory_path": str(target_dir),
            "archive_path": str(archive_path),
            "filename": archive_path.name,
            "allowed_extensions": allowed_extensions,
        }

    def ingest_mop_to_qdrant(self, mop_id: str) -> dict:
        response = self.get(mop_id)
        if response is None:
            return {"status": "not_found", "mop_id": mop_id}
        run_dir = Path(response.artifacts.run_directory_path).resolve()
        storage_root = Path(self._settings.agent.local_storage_path).resolve()
        if not _is_safe_artifact_path(storage_root, run_dir) or not run_dir.is_dir():
            return {
                "status": "not_found",
                "mop_id": mop_id,
                "error": "artifact_directory_not_found",
            }
        return self._reference_lookup.ingest_mop_artifacts(
            mop_id=mop_id,
            run_directory=run_dir,
        )

    def delete_mop(self, mop_id: str) -> dict:
        storage_root = Path(self._settings.agent.local_storage_path).resolve()
        target = (storage_root / mop_id).resolve()
        if not _is_safe_artifact_path(storage_root, target):
            return {
                "status": "denied",
                "mop_id": mop_id,
                "error": "path_outside_storage_directory",
            }
        removed = _remove_directory(target)
        with self._lock:
            existed_in_memory = mop_id in self._responses
            self._responses.pop(mop_id, None)
            self._classifications.pop(mop_id, None)
            if self._latest_mop_id == mop_id:
                self._latest_mop_id = next(reversed(self._responses), None)
        return {
            "status": "deleted" if removed["existed"] or existed_in_memory else "not_found",
            "mop_id": mop_id,
            "artifact_directory": str(target),
            "artifact_directory_existed": removed["existed"],
            "removed_file_count": removed["file_count"],
            "removed_directory_count": removed["directory_count"],
            "removed_size_bytes": removed["size_bytes"],
            "in_memory_record_existed": existed_in_memory,
        }

    def delete_all_mops(self, *, confirm: bool) -> dict:
        if not confirm:
            return {
                "status": "denied",
                "error": "confirm_required",
                "required_confirm": True,
            }
        storage_root = Path(self._settings.agent.local_storage_path).resolve()
        storage_root.mkdir(parents=True, exist_ok=True)
        removed_items = []
        for target in sorted(item for item in storage_root.iterdir() if item.is_dir()):
            if not _is_safe_artifact_path(storage_root, target.resolve()):
                continue
            removed = _remove_directory(target.resolve())
            removed_items.append(
                {
                    "mop_id": target.name,
                    "artifact_directory": str(target.resolve()),
                    "removed_file_count": removed["file_count"],
                    "removed_directory_count": removed["directory_count"],
                    "removed_size_bytes": removed["size_bytes"],
                }
            )
        with self._lock:
            in_memory_count = len(self._responses)
            self._responses.clear()
            self._classifications.clear()
            self._latest_mop_id = None
        return {
            "status": "deleted",
            "artifact_storage_path": str(storage_root),
            "removed_mop_count": len(removed_items),
            "removed_file_count": sum(item["removed_file_count"] for item in removed_items),
            "removed_directory_count": sum(
                item["removed_directory_count"] for item in removed_items
            ),
            "removed_size_bytes": sum(item["removed_size_bytes"] for item in removed_items),
            "removed_mops": removed_items,
            "removed_in_memory_record_count": in_memory_count,
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


def _session_context_key(namespace: str) -> str:
    return f"namespace:{namespace}"


def _read_artifact_manifest(path: str) -> dict[str, Any]:
    artifact_path = Path(path)
    if not artifact_path.is_file():
        return {}
    return json.loads(artifact_path.read_text(encoding="utf-8"))


def _machine_plan_evidence_audit(manifest: dict[str, Any]) -> dict[str, Any]:
    plan = manifest.get("machine_execution_plan")
    phases = plan.get("phases") if isinstance(plan, dict) else []
    total_steps = 0
    missing_steps: list[str] = []
    if not isinstance(phases, list):
        phases = []
    for phase in phases:
        if not isinstance(phase, dict):
            continue
        for step in phase.get("steps") or []:
            if not isinstance(step, dict):
                continue
            total_steps += 1
            evidence_refs = step.get("evidence_refs") or []
            inference = step.get("inference") if isinstance(step.get("inference"), dict) else {}
            has_inference = bool(inference.get("rationale") or inference.get("label"))
            if not evidence_refs and not has_inference:
                missing_steps.append(str(step.get("step_id") or "unknown_step"))
    return {
        "total_step_count": total_steps,
        "missing_evidence_or_inference_count": len(missing_steps),
        "missing_step_ids": missing_steps[:25],
        "policy": "every_generated_step_requires_evidence_refs_or_inference_label",
    }


def _machine_plan_missing_evidence_count(manifest: dict[str, Any]) -> int:
    return int(_machine_plan_evidence_audit(manifest)["missing_evidence_or_inference_count"])


def _update_artifact_observability_metadata(path: str, metadata: dict[str, Any]) -> None:
    artifact_path = Path(path)
    if not artifact_path.is_file():
        return
    manifest = json.loads(artifact_path.read_text(encoding="utf-8"))
    manifest["observability"] = metadata
    artifact_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )
def _update_artifact_memory_write_metadata(path: str, metadata: dict[str, Any]) -> None:
    artifact_path = Path(path)
    if not artifact_path.is_file():
        return
    manifest = json.loads(artifact_path.read_text(encoding="utf-8"))
    memory = manifest.setdefault("memory", {})
    memory.update(metadata)
    artifact_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _is_safe_artifact_path(run_dir: Path, target: Path) -> bool:
    try:
        target.relative_to(run_dir)
    except ValueError:
        return False
    return True


def _remove_directory(target: Path) -> dict:
    if not target.is_dir():
        return {
            "existed": False,
            "file_count": 0,
            "directory_count": 0,
            "size_bytes": 0,
        }
    file_count = 0
    directory_count = 0
    size_bytes = 0
    for item in target.rglob("*"):
        if item.is_file():
            file_count += 1
            size_bytes += item.stat().st_size
        elif item.is_dir():
            directory_count += 1
    shutil.rmtree(target)
    return {
        "existed": True,
        "file_count": file_count,
        "directory_count": directory_count + 1,
        "size_bytes": size_bytes,
    }
