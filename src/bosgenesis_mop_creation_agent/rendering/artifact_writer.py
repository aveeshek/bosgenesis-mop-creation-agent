from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from bosgenesis_mop_creation_agent.classification.models import (
    ClassificationSummary,
    ClassifiedResource,
)
from bosgenesis_mop_creation_agent.classification.resource_classifier import classify_inventory
from bosgenesis_mop_creation_agent.config.settings import LlmSettings
from bosgenesis_mop_creation_agent.llm.bounded_reasoning import build_bounded_reasoning
from bosgenesis_mop_creation_agent.llm.models import BoundedReasoningResult, RepairSuggestionResult
from bosgenesis_mop_creation_agent.llm.repair_suggester import build_repair_suggestions
from bosgenesis_mop_creation_agent.memory.models import MemoryContext
from bosgenesis_mop_creation_agent.models.requests import MoPGenerationRequest
from bosgenesis_mop_creation_agent.reconstruction.helm_hints import apply_helm_chart_hints
from bosgenesis_mop_creation_agent.reconstruction.models import (
    HelmReleasePlan,
    RawManifestPlan,
    ReconstructionPlan,
)
from bosgenesis_mop_creation_agent.reconstruction.planner import build_reconstruction_plan
from bosgenesis_mop_creation_agent.reconstruction.quality_gate import (
    assert_executable_reconstruction_complete,
)
from bosgenesis_mop_creation_agent.rendering.pdf_renderer import render_human_mop_pdf
from bosgenesis_mop_creation_agent.retrieval.models import ReferenceLookupResult
from bosgenesis_mop_creation_agent.sources.snapshot_models import NormalizedInventory


HUMAN_MOP_TEMPLATE_PATH = Path("artifacts/human-mop/human_mop_pdf_template.md")
INSTALLATION_NOTES_TEMPLATE_PATH = Path(
    "artifacts/installation-notes/installation_notes_template.md"
)


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


@dataclass(frozen=True)
class ArtifactWriteResult:
    run_directory_path: str
    artifact_manifest_path: str
    human_mop_markdown_path: str
    human_mop_pdf_path: str
    installation_notes_path: str
    human_mop_content: str
    installation_notes_content: str
    reconstruction_helm_release_count: int
    reconstruction_raw_manifest_count: int
    warnings: list[str]


class LocalArtifactWriter:
    """Write snapshot and MCP-enriched artifacts to local storage."""

    def __init__(self, storage_path: str, llm_settings: LlmSettings | None = None) -> None:
        self._storage_path = Path(storage_path)
        self._llm_settings = llm_settings or LlmSettings()

    def write(
        self,
        *,
        mop_id: str,
        run_id: str,
        correlation_id: str,
        source_namespace: str,
        request: MoPGenerationRequest,
        created_at: datetime,
        warnings: list[str],
        inventory: NormalizedInventory | None = None,
        classification: ClassificationSummary | None = None,
        qdrant_references: ReferenceLookupResult | None = None,
        memory_context: MemoryContext | None = None,
        snapshot_sources_attempted: list[str] | None = None,
        mcp_sources_attempted: list[str] | None = None,
    ) -> ArtifactWriteResult:
        run_dir = self._storage_path / mop_id
        generated_dir = run_dir / "generated"
        values_dir = run_dir / "values"
        evidence_dir = run_dir / "evidence"
        for directory in (run_dir, generated_dir, values_dir, evidence_dir):
            directory.mkdir(parents=True, exist_ok=True)

        file_stem = (
            f"mop-{source_namespace}-to-{request.target_namespace}-"
            f"{created_at:%Y%m%dT%H%M%SZ}"
        )
        human_mop_markdown_path = run_dir / f"{file_stem}.human-mop.md"
        human_mop_pdf_path = run_dir / f"{file_stem}.pdf"
        installation_notes_path = run_dir / f"{file_stem}.installation.md"
        machine_execution_plan_path = run_dir / "machine_execution_plan.yaml"
        artifact_manifest_path = run_dir / "artifact.json"
        try:
            inventory = apply_helm_chart_hints(
                inventory=inventory,
                classification=classification,
                hints=request.helm_chart_hints,
            )
            if inventory is not None:
                classification = classify_inventory(inventory)
            reconstruction = build_reconstruction_plan(
                inventory=inventory,
                classification=classification,
                target_namespace=request.target_namespace,
                generated_dir=generated_dir,
                values_dir=values_dir,
            )
            assert_executable_reconstruction_complete(
                classification=classification,
                reconstruction=reconstruction,
            )
        except Exception:
            shutil.rmtree(run_dir, ignore_errors=True)
            raise
        reference_result = qdrant_references or ReferenceLookupResult()
        safe_memory_context = memory_context or MemoryContext(
            namespace_key=f"namespace:{source_namespace}"
        )
        bounded_reasoning = build_bounded_reasoning(
            settings=self._llm_settings,
            reconstruction=reconstruction,
            classification=classification,
            correlation_id=correlation_id,
            prior_references=reference_result,
            memory_context=safe_memory_context,
        )
        repair_suggestions = build_repair_suggestions(
            settings=self._llm_settings,
            reconstruction=reconstruction,
            classification=classification,
            correlation_id=correlation_id,
            prior_references=reference_result,
        )
        all_warnings = [
            *warnings,
            *reconstruction.warnings,
            *reference_result.warnings,
            *bounded_reasoning.warnings,
            *repair_suggestions.warnings,
        ]

        context = self._build_context(
            mop_id=mop_id,
            run_id=run_id,
            correlation_id=correlation_id,
            source_namespace=source_namespace,
            request=request,
            created_at=created_at,
            warnings=all_warnings,
            inventory=inventory,
            classification=classification,
            reconstruction=reconstruction,
            bounded_reasoning=bounded_reasoning,
            repair_suggestions=repair_suggestions,
            qdrant_references=reference_result,
            memory_context=safe_memory_context,
            snapshot_sources_attempted=snapshot_sources_attempted or [],
            mcp_sources_attempted=mcp_sources_attempted or [],
            run_dir=run_dir,
            human_mop_pdf_path=human_mop_pdf_path,
            installation_notes_path=installation_notes_path,
            generated_dir=generated_dir,
            values_dir=values_dir,
            evidence_dir=evidence_dir,
        )

        human_mop_content = render_template(_read_template(HUMAN_MOP_TEMPLATE_PATH), context)
        installation_notes_content = render_template(
            _read_template(INSTALLATION_NOTES_TEMPLATE_PATH),
            context,
        )
        machine_execution_plan_content = context["machine_execution_plan_yaml"]
        _assert_required_sections(human_mop_content)

        human_mop_markdown_path.write_text(human_mop_content, encoding="utf-8")
        installation_notes_path.write_text(installation_notes_content, encoding="utf-8")
        machine_execution_plan_path.write_text(machine_execution_plan_content, encoding="utf-8")
        pdf_result = render_human_mop_pdf(
            human_mop_content,
            human_mop_pdf_path,
            context=context,
        )

        manifest = {
            "artifact_type": "phase6_reconstruction_mop_artifact",
            "schema_version": "1.0",
            "mop_id": mop_id,
            "run_id": run_id,
            "correlation_id": correlation_id,
            "source_namespace": source_namespace,
            "target_namespace": request.target_namespace,
            "session_context_key": f"namespace:{source_namespace}",
            "memory_primary_key": f"namespace:{source_namespace}",
            "generation_mode": request.mode.value,
            "created_at": created_at.isoformat(),
            "status": "generated",
            "external_calls": {
                "kubernetes": "k8s_inspector_mcp" in (mcp_sources_attempted or []),
                "helm": "helm_manager_mcp" in (mcp_sources_attempted or []),
                "qdrant": reference_result.enabled,
                "datastores": True,
            },
            "inventory": {
                "source": inventory.source if inventory else None,
                "snapshot_id": inventory.snapshot_id if inventory else None,
                "resource_count": inventory.resource_count if inventory else 0,
                "helm_release_count": inventory.helm_release_count if inventory else 0,
                "sources_attempted": snapshot_sources_attempted or [],
            },
            "classification": _classification_manifest(classification),
            "reconstruction": _reconstruction_manifest(reconstruction),
            "qdrant_prior_references": reference_result.model_dump(mode="json"),
            "memory": {
                **safe_memory_context.model_dump(mode="json"),
                "read_count": safe_memory_context.read_count,
            },
            "bounded_llm_reasoning": bounded_reasoning.model_dump(mode="json"),
            "human_mop_pdf_renderer": pdf_result.metadata.model_dump(),
            "machine_execution_plan": _machine_execution_plan(
                reconstruction=reconstruction,
                classification=classification,
                target_namespace=request.target_namespace,
                generation_mode=request.mode.value,
                qdrant_references=reference_result,
            ),
            "llm_repair_suggestions": repair_suggestions.model_dump(mode="json"),
            "mcp": {
                "sources_attempted": mcp_sources_attempted or [],
                "live_enrichment_enabled": bool(mcp_sources_attempted),
                "policy": "governed_read_only_mcp_clients_no_raw_kubectl_or_helm",
            },
            "artifacts": {
                "human_mop_markdown_path": str(human_mop_markdown_path),
                "human_mop_pdf_path": str(human_mop_pdf_path),
                "installation_notes_path": str(installation_notes_path),
                "machine_execution_plan_path": str(machine_execution_plan_path),
                "generated_manifests_dir": str(generated_dir),
                "generated_values_dir": str(values_dir),
                "evidence_dir": str(evidence_dir),
            },
            "required_human_mop_sections": list(REQUIRED_HUMAN_MOP_SECTIONS),
            "warnings": all_warnings,
        }
        artifact_manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True),
            encoding="utf-8",
        )

        return ArtifactWriteResult(
            run_directory_path=str(run_dir),
            artifact_manifest_path=str(artifact_manifest_path),
            human_mop_markdown_path=str(human_mop_markdown_path),
            human_mop_pdf_path=str(human_mop_pdf_path),
            installation_notes_path=str(installation_notes_path),
            human_mop_content=human_mop_content,
            installation_notes_content=installation_notes_content,
            reconstruction_helm_release_count=reconstruction.helm_release_count,
            reconstruction_raw_manifest_count=len(reconstruction.raw_manifests),
            warnings=all_warnings,
        )

    def _build_context(
        self,
        *,
        mop_id: str,
        run_id: str,
        correlation_id: str,
        source_namespace: str,
        request: MoPGenerationRequest,
        created_at: datetime,
        warnings: list[str],
        inventory: NormalizedInventory | None,
        classification: ClassificationSummary | None,
        reconstruction: ReconstructionPlan,
        bounded_reasoning: BoundedReasoningResult,
        repair_suggestions: RepairSuggestionResult,
        qdrant_references: ReferenceLookupResult,
        memory_context: MemoryContext,
        snapshot_sources_attempted: list[str],
        mcp_sources_attempted: list[str],
        run_dir: Path,
        human_mop_pdf_path: Path,
        installation_notes_path: Path,
        generated_dir: Path,
        values_dir: Path,
        evidence_dir: Path,
    ) -> dict[str, Any]:
        warning_yaml = "\n".join(f"  - {warning}" for warning in warnings) or "  []"
        empty_yaml_list = "  []"
        empty_phase_commands = (
            "  - step_id: phase6-placeholder\n"
            "    title: Phase 6 placeholder\n"
            "    type: validation\n"
            "    depends_on: []\n"
            "    evidence_refs: []\n"
            "    qdrant_refs: []\n"
            "    inference:\n"
            "      label: human_input_required\n"
            "      confidence: low\n"
            "      rationale: Phase 6 generates platform reconstruction commands from classified inventory.\n"
            "    command: |\n"
            "      echo \"Phase 6 placeholder only\"\n"
            "    expected: No target system changes are made.\n"
            "    on_failure: STOP and inspect the local artifact bundle.\n"
            "    mutates_target: false\n"
            "    requires_human_approval: false"
        )

        return {
            "mop_title": f"Namespace Recreation MoP - {source_namespace} to {request.target_namespace}",
            "mop_id": mop_id,
            "mop_version": "0.6.0-phase6",
            "generated_at": created_at.isoformat(),
            "reviewed_by_placeholder": "TBD",
            "change_ticket_placeholder": "TBD",
            "change_window_placeholder": "TBD",
            "estimated_duration": "TBD",
            "risk_level": "TBD",
            "rollback_time": "TBD",
            "rollback_approver_placeholder": "TBD",
            "source_namespace": source_namespace,
            "target_namespace": request.target_namespace,
            "session_context_key": f"namespace:{source_namespace}",
            "memory_primary_key": f"namespace:{source_namespace}",
            "memory_context_status": memory_context.status,
            "memory_context_read_count": str(memory_context.read_count),
            "memory_context_yaml": _memory_context_yaml(memory_context),
            "generation_mode": request.mode.value,
            "source_snapshot_id_or_timestamp": (
                inventory.snapshot_id if inventory else request.source_snapshot_id
            ),
            "run_id": run_id,
            "correlation_id": correlation_id,
            "change_reason": "Phase 6 platform reconstruction artifact generation with normalized raw manifests and Helm value files.",
            "helm_release_count": str(
                max(
                    inventory.helm_release_count if inventory else 0,
                    reconstruction.helm_release_count,
                )
            ),
            "helm_release_summary": _helm_summary(inventory, reconstruction),
            "raw_k8s_resource_count": str(_raw_count(inventory, classification)),
            "raw_k8s_summary": _resource_summary(inventory, classification),
            "application_target_count": "0",
            "application_summary": "Application mode metadata discovery is not executed in Phase 6.",
            "excluded_resource_count": str(classification.excluded_count if classification else 0),
            "excluded_summary": _excluded_summary(classification),
            "warning_count": str(len(warnings)),
            "warning_summary": "; ".join(warnings),
            "assumptions_list": (
                "- Stored ETL snapshots are preferred when available.\n"
                "- Live Kubernetes and Helm reads are performed only through governed MCP servers."
            ),
            "unknowns_list": _unknowns(inventory),
            "expected_cluster_context": "TBD",
            "artifact_bundle_path": str(run_dir),
            "backup_dir": str(evidence_dir),
            "helm_backup_commands": _helm_backup_commands(reconstruction),
            "target_namespace_preparation_steps": _placeholder_step("4.1", "Target namespace preparation"),
            "secret_placeholder_rows": "| TBD | TBD | TBD | Pending |",
            "secret_creation_guidance": "No secret values are read or generated in Phase 6.",
            "configmap_execution_steps": _resource_steps_by_plan(reconstruction, "ConfigMap", "4.3"),
            "pvc_execution_steps": _resource_steps_by_plan(
                reconstruction,
                "PersistentVolumeClaim",
                "4.4",
            ),
            "helm_release_execution_steps": _helm_steps_by_plan(reconstruction),
            "raw_kubernetes_execution_steps": _raw_kubernetes_steps_by_plan(reconstruction),
            "ingress_execution_steps": _resource_steps_by_plan(reconstruction, "Ingress", "4.7"),
            "application_mode_execution_steps": _placeholder_step(
                "4.8",
                "Application metadata recreation",
            ),
            "helm_validation_commands": _join_commands(
                plan.validation_command for plan in reconstruction.helm_releases
            ),
            "ingress_validation_commands": _join_commands(
                plan.validation_command
                for plan in reconstruction.raw_manifests
                if plan.kind == "Ingress"
            ),
            "application_mode_validation_steps": _placeholder_step(
                "5.5",
                "Application metadata validation",
            ),
            "helm_rollback_commands": _join_commands(
                plan.rollback_command for plan in reversed(reconstruction.helm_releases)
            ),
            "raw_kubernetes_rollback_commands": _join_commands(
                plan.rollback_command for plan in reversed(reconstruction.raw_manifests)
            ),
            "application_mode_rollback_steps": "No application metadata was created in Phase 6.",
            "evidence_references": _evidence_references(
                inventory,
                snapshot_sources_attempted,
                mcp_sources_attempted,
            ),
            "qdrant_prior_references": _qdrant_references_markdown(qdrant_references),
            "inference_labels_and_rationale": (
                _reasoning_and_repair_markdown(bounded_reasoning, repair_suggestions)
            ),
            "excluded_resources": _excluded_resources_markdown(classification),
            "generation_status": "generated",
            "qdrant_lookup_status": qdrant_references.status,
            "qdrant_reference_count": str(qdrant_references.reference_count),
            "required_human_inputs_yaml": _required_human_inputs_yaml(
                reconstruction,
                classification,
            ),
            "k8s_mcp_status": _source_status("k8s_inspector_mcp", mcp_sources_attempted),
            "k8s_evidence_references_yaml": _source_refs("k8s_inspector_mcp", mcp_sources_attempted),
            "helm_mcp_status": _source_status("helm_manager_mcp", mcp_sources_attempted),
            "helm_evidence_references_yaml": _source_refs("helm_manager_mcp", mcp_sources_attempted),
            "data_ingestion_status": _source_status("data_ingestion_mcp", mcp_sources_attempted),
            "data_ingestion_references_yaml": _source_refs(
                "data_ingestion_mcp",
                mcp_sources_attempted,
            ),
            "qdrant_references_yaml": _qdrant_references_yaml(qdrant_references),
            "helm_releases_yaml": _helm_inventory_yaml(inventory),
            "raw_kubernetes_resources_yaml": _resource_inventory_yaml(inventory, classification),
            "professional_resource_snapshot": _professional_resource_snapshot(
                inventory,
                classification,
            ),
            "application_targets_yaml": empty_yaml_list,
            "excluded_resources_yaml": _excluded_resources_yaml(classification),
            "warnings_yaml": warning_yaml,
            "verify_access_commands_yaml": empty_phase_commands,
            "verify_access_expected_outcomes_yaml": "  - Snapshot and MCP inventory evidence is represented in generated artifacts.",
            "verify_access_stop_conditions_yaml": "  - Local artifact directory is not writable.",
            "verify_access_evidence_refs_yaml": "  - artifact.json",
            "target_namespace_commands_yaml": _target_namespace_commands_yaml(request.target_namespace),
            "target_namespace_expected_outcomes_yaml": f"  - Namespace {request.target_namespace} exists.",
            "target_namespace_rollback_yaml": "  - Delete the target namespace only if it was created for this change and cleanup is approved.",
            "target_namespace_evidence_refs_yaml": "  - artifact.json",
            "secret_manual_inputs_yaml": empty_yaml_list,
            "secret_placeholder_commands_yaml": empty_phase_commands,
            "secret_expected_outcomes_yaml": "  - No secrets are generated or copied.",
            "secret_evidence_refs_yaml": "  - artifact.json",
            "configmap_commands_yaml": _raw_commands_yaml(reconstruction, {"ConfigMap"}),
            "configmap_expected_outcomes_yaml": "  - ConfigMaps are accepted by dry-run and then applied when approved.",
            "configmap_rollback_yaml": _raw_rollback_yaml(reconstruction, {"ConfigMap"}),
            "configmap_evidence_refs_yaml": "  - artifact.json",
            "pvc_commands_yaml": _raw_commands_yaml(reconstruction, {"PersistentVolumeClaim"}),
            "pvc_expected_outcomes_yaml": "  - PVCs are accepted by dry-run and then applied when approved.",
            "pvc_rollback_yaml": _raw_rollback_yaml(reconstruction, {"PersistentVolumeClaim"}),
            "pvc_evidence_refs_yaml": "  - artifact.json",
            "helm_commands_yaml": _helm_commands_yaml(reconstruction),
            "helm_expected_outcomes_yaml": "  - Helm dry-runs render successfully before install commands are executed.",
            "helm_rollback_yaml": _helm_rollback_yaml(reconstruction),
            "helm_unknowns_yaml": (
                _helm_unknowns_yaml(reconstruction)
            ),
            "raw_kubernetes_commands_yaml": _raw_commands_yaml(
                reconstruction,
                exclude={"ConfigMap", "PersistentVolumeClaim", "Ingress"},
            ),
            "raw_kubernetes_expected_outcomes_yaml": (
                "  - Raw Kubernetes manifests are accepted by server-side dry-run before apply."
            ),
            "raw_kubernetes_rollback_yaml": _raw_rollback_yaml(
                reconstruction,
                exclude={"ConfigMap", "PersistentVolumeClaim", "Ingress"},
            ),
            "raw_kubernetes_evidence_refs_yaml": "  - artifact.json",
            "ingress_commands_yaml": _raw_commands_yaml(reconstruction, {"Ingress"}),
            "ingress_expected_outcomes_yaml": "  - Ingress resources are accepted by dry-run and then applied when approved.",
            "ingress_rollback_yaml": _raw_rollback_yaml(reconstruction, {"Ingress"}),
            "ingress_evidence_refs_yaml": "  - artifact.json",
            "application_metadata_commands_yaml": empty_phase_commands,
            "application_metadata_expected_outcomes_yaml": "  - No schemas, topics, or topology are created.",
            "application_metadata_rollback_yaml": "  - No rollback required.",
            "application_metadata_evidence_refs_yaml": "  - artifact.json",
            "validation_commands_yaml": _validation_commands_yaml(reconstruction),
            "validation_expected_outcomes_yaml": (
                "  - Generated files exist and target namespace dry-run commands succeed."
            ),
            "validation_stop_conditions_yaml": "  - Required MoP sections are missing.",
            "validation_evidence_refs_yaml": "  - artifact.json",
            "go_no_go_yaml": (
                "  - checkpoint: Required artifact files exist\n"
                "    expected: true\n"
                "    action_if_failed: STOP"
            ),
            "rollback_trigger_conditions_yaml": "  - Any approved install/apply command fails after mutation begins.",
            "namespace_cleanup_rollback_yaml": "  - Delete target namespace only with explicit approval.",
            "inferences_yaml": (
                _inferences_yaml(bounded_reasoning, repair_suggestions)
            ),
            "unknowns_yaml": _unknowns_yaml(inventory),
            "confidence_summary_yaml": (
                _confidence_summary_yaml(bounded_reasoning, repair_suggestions)
            ),
            "machine_execution_plan_yaml": _machine_execution_plan_yaml(
                reconstruction=reconstruction,
                classification=classification,
                target_namespace=request.target_namespace,
                generation_mode=request.mode.value,
                qdrant_references=qdrant_references,
            ),
            "human_mop_pdf_path": str(human_mop_pdf_path),
            "installation_notes_path": str(installation_notes_path),
            "generated_manifests_dir": str(generated_dir),
            "generated_values_dir": str(values_dir),
            "evidence_dir": str(evidence_dir),
        }


def _machine_execution_plan_yaml(
    *,
    reconstruction: ReconstructionPlan,
    classification: ClassificationSummary | None,
    target_namespace: str,
    generation_mode: str,
    qdrant_references: ReferenceLookupResult | None = None,
) -> str:
    return yaml.dump(
        _machine_execution_plan(
            reconstruction=reconstruction,
            classification=classification,
            target_namespace=target_namespace,
            generation_mode=generation_mode,
            qdrant_references=qdrant_references or ReferenceLookupResult(),
        ),
        Dumper=_NoAliasSafeDumper,
        sort_keys=False,
        width=120,
    ).rstrip()


def _machine_execution_plan(
    *,
    reconstruction: ReconstructionPlan,
    classification: ClassificationSummary | None,
    target_namespace: str,
    generation_mode: str,
    qdrant_references: ReferenceLookupResult,
) -> dict[str, Any]:
    phases = [
        _phase(
            phase_id="verify_access",
            depends_on=[],
            objective="Confirm artifact bundle, source evidence, and target namespace intent.",
            steps=[
                _step(
                    step_id="verify-artifact-bundle",
                    phase_id="verify_access",
                    step_type="context_check",
                    title="Verify generated artifact bundle",
                    commands=[
                        {
                            "kind": "check",
                            "command": "test -f artifact.json && test -d generated && test -d values",
                        }
                    ],
                    expected_outcomes=["artifact.json, generated/, and values/ are present."],
                    evidence_refs=["artifact.json"],
                    inference_label="observed",
                    confidence="high",
                    rationale="The artifact bundle is produced by this agent before execution.",
                    mutates_target=False,
                    requires_human_approval=False,
                )
            ],
        ),
        _phase(
            phase_id="prepare_target_namespace",
            depends_on=["verify_access"],
            objective="Ensure the target namespace exists before namespaced resources are applied.",
            steps=[
                _step(
                    step_id="prepare-target-namespace",
                    phase_id="prepare_target_namespace",
                    step_type="namespace",
                    title=f"Ensure namespace {target_namespace} exists",
                    commands=[
                        {
                            "kind": "check",
                            "command": f"kubectl get namespace {target_namespace}",
                        },
                        {
                            "kind": "apply",
                            "command": (
                                f"kubectl get namespace {target_namespace} || "
                                f"kubectl create namespace {target_namespace}"
                            ),
                        },
                    ],
                    expected_outcomes=[f"Namespace {target_namespace} exists."],
                    evidence_refs=["generation_request.target_namespace"],
                    inference_label="human_input_required",
                    confidence="high",
                    rationale="The target namespace is supplied by the generation request.",
                    rollback_commands=[
                        (
                            f"kubectl delete namespace {target_namespace} "
                            "# only if created for this change and cleanup is approved"
                        )
                    ],
                    mutates_target=True,
                    requires_human_approval=True,
                )
            ],
        ),
        _phase(
            phase_id="prepare_secret_placeholders",
            depends_on=["prepare_target_namespace"],
            objective="Collect approved secret values without copying source Secret data.",
            steps=_secret_placeholder_steps(classification),
        ),
        _phase(
            phase_id="apply_configmaps",
            depends_on=["prepare_secret_placeholders"],
            objective="Apply generated ConfigMap manifests after namespace rewrite.",
            steps=_raw_plan_steps(
                reconstruction,
                phase_id="apply_configmaps",
                include={"ConfigMap"},
                depends_on=["prepare_secret_placeholders"],
            ),
        ),
        _phase(
            phase_id="apply_pvcs",
            depends_on=["prepare_target_namespace"],
            objective="Apply approved PersistentVolumeClaim manifests.",
            steps=_raw_plan_steps(
                reconstruction,
                phase_id="apply_pvcs",
                include={"PersistentVolumeClaim"},
                depends_on=["prepare_target_namespace"],
            ),
        ),
        _phase(
            phase_id="install_helm_releases",
            depends_on=["apply_configmaps", "apply_pvcs", "prepare_secret_placeholders"],
            objective="Install or upgrade Helm-managed components with redacted values files.",
            steps=_helm_plan_steps(reconstruction),
        ),
        _phase(
            phase_id="apply_raw_kubernetes_resources",
            depends_on=["install_helm_releases", "apply_configmaps", "apply_pvcs"],
            objective="Apply supported non-Helm Kubernetes resources in deterministic order.",
            steps=_raw_plan_steps(
                reconstruction,
                phase_id="apply_raw_kubernetes_resources",
                exclude={"ConfigMap", "PersistentVolumeClaim", "Ingress"},
                depends_on=["install_helm_releases", "apply_configmaps", "apply_pvcs"],
            ),
        ),
        _phase(
            phase_id="apply_ingress",
            depends_on=["apply_raw_kubernetes_resources"],
            objective="Apply Ingress resources after backend services are present.",
            steps=_raw_plan_steps(
                reconstruction,
                phase_id="apply_ingress",
                include={"Ingress"},
                depends_on=["apply_raw_kubernetes_resources"],
            ),
        ),
        _phase(
            phase_id="apply_application_metadata",
            depends_on=["apply_raw_kubernetes_resources"],
            objective="Application-mode metadata recreation is deferred until application evidence exists.",
            enabled_when='generation_mode == "application"',
            steps=[
                _manual_guidance_step(
                    step_id="application-metadata-human-review",
                    phase_id="apply_application_metadata",
                    title="Review application metadata gaps",
                    rationale="Phase 8 platform notes do not create database schemas, topics, or cache metadata.",
                    required_human_inputs=["application_metadata_evidence"],
                )
            ]
            if generation_mode == "application"
            else [],
        ),
        _phase(
            phase_id="validate",
            depends_on=["apply_ingress", "apply_application_metadata"],
            objective="Confirm generated resources are visible and healthy in the target namespace.",
            steps=_validation_plan_steps(reconstruction),
        ),
    ]
    return {
        "machine_execution_plan": {
            "schema_version": "1.0",
            "authority_order": "observed_evidence > deterministic_normalization > llm_suggestion > human_fill_in",
            "executor_contract": {
                "parse_this_block_first": True,
                "dry_run_before_mutation": True,
                "human_approval_before_mutation": True,
                "never_copy_secret_values": True,
                "target_namespace_only": target_namespace,
                "llm_suggestions_are_not_authority": True,
                "qdrant_references_are_prior_guidance_only": True,
            },
            "prior_references": [
                {
                    "reference_id": reference.reference_id,
                    "citation_label": reference.citation_label,
                    "component": (
                        f"{reference.component_identity.kind}/"
                        f"{reference.component_identity.name}"
                    ),
                    "source_mop_id": reference.source_mop_id,
                    "score": reference.score,
                    "matched_fields": reference.matched_fields,
                }
                for reference in qdrant_references.references
            ],
            "dependency_graph": [
                {"phase_id": phase["phase_id"], "depends_on": phase["depends_on"]}
                for phase in phases
            ],
            "required_human_inputs": _required_human_inputs(reconstruction, classification),
            "phases": phases,
        }
    }


def _phase(
    *,
    phase_id: str,
    depends_on: list[str],
    objective: str,
    steps: list[dict[str, Any]],
    enabled_when: str | None = None,
) -> dict[str, Any]:
    phase: dict[str, Any] = {
        "phase_id": phase_id,
        "depends_on": depends_on,
        "objective": objective,
        "steps": steps,
    }
    if enabled_when:
        phase["enabled_when"] = enabled_when
    return phase


def _step(
    *,
    step_id: str,
    phase_id: str,
    step_type: str,
    title: str,
    commands: list[dict[str, str]],
    expected_outcomes: list[str],
    evidence_refs: list[str],
    inference_label: str,
    confidence: str,
    rationale: str,
    depends_on: list[str] | None = None,
    qdrant_refs: list[str] | None = None,
    manifest_refs: list[str] | None = None,
    values_refs: list[str] | None = None,
    required_human_inputs: list[str] | None = None,
    rollback_commands: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    mutates_target: bool,
    requires_human_approval: bool,
) -> dict[str, Any]:
    step = {
        "step_id": _safe_step_id(step_id),
        "phase_id": phase_id,
        "title": title,
        "type": step_type,
        "depends_on": depends_on or [],
        "evidence_refs": evidence_refs,
        "qdrant_refs": qdrant_refs or [],
        "manifest_refs": manifest_refs or [],
        "values_refs": values_refs or [],
        "inference": {
            "label": inference_label,
            "confidence": confidence,
            "rationale": rationale,
        },
        "commands": commands,
        "expected_outcomes": expected_outcomes,
        "required_human_inputs": required_human_inputs or [],
        "rollback_commands": rollback_commands or [],
        "mutates_target": mutates_target,
        "requires_human_approval": requires_human_approval,
        "on_failure": "STOP and resolve the evidence or generated artifact before continuing.",
    }
    if metadata:
        step.update(metadata)
    return step


def _secret_placeholder_steps(classification: ClassificationSummary | None) -> list[dict[str, Any]]:
    secret_inputs = [
        f"approved_secret_material_for_{item.resource.name}"
        for item in (classification.excluded if classification else [])
        if item.resource.kind == "Secret"
    ]
    if not secret_inputs:
        return [
            _manual_guidance_step(
                step_id="secret-values-not-generated",
                phase_id="prepare_secret_placeholders",
                title="Confirm no generated Secret values are present",
                rationale="Secret values are excluded by policy and must not appear in artifacts.",
                required_human_inputs=[],
            )
        ]
    return [
        _manual_guidance_step(
            step_id="collect-approved-secret-material",
            phase_id="prepare_secret_placeholders",
            title="Collect approved target Secret material",
            rationale="Source Secret values are excluded; humans must provide approved target values.",
            required_human_inputs=secret_inputs,
        )
    ]


def _manual_guidance_step(
    *,
    step_id: str,
    phase_id: str,
    title: str,
    rationale: str,
    required_human_inputs: list[str],
) -> dict[str, Any]:
    return _step(
        step_id=step_id,
        phase_id=phase_id,
        step_type="human_input",
        title=title,
        commands=[],
        expected_outcomes=["Required human inputs are confirmed before execution continues."],
        evidence_refs=["artifact.json"],
        inference_label="human_input_required",
        confidence="high",
        rationale=rationale,
        required_human_inputs=required_human_inputs,
        mutates_target=False,
        requires_human_approval=False,
    )


def _helm_plan_steps(reconstruction: ReconstructionPlan) -> list[dict[str, Any]]:
    steps = []
    for index, plan in enumerate(reconstruction.helm_releases, start=1):
        human_inputs = []
        if plan.chart_ref.startswith("<"):
            human_inputs.append(f"public_chart_ref_for_{plan.release_name}")
        if plan.chart_source == "private" and not plan.repo_url:
            human_inputs.append(f"private_repo_url_for_{plan.release_name}")
        steps.append(
            _step(
                step_id=f"helm-{index}-{plan.release_name}",
                phase_id="install_helm_releases",
                step_type="helm_upgrade",
                title=f"Install Helm release {plan.release_name}",
                depends_on=["apply_configmaps", "apply_pvcs", "prepare_secret_placeholders"],
                values_refs=[plan.values_relative_path],
                metadata=_helm_step_metadata(plan),
                commands=[
                    {"kind": "dry_run", "command": plan.dry_run_command},
                    {"kind": "apply", "command": plan.install_command},
                    {"kind": "validate", "command": plan.validation_command},
                ],
                expected_outcomes=[
                    f"Helm release {plan.release_name} is deployed in {reconstruction.target_namespace}.",
                ],
                evidence_refs=[plan.evidence_ref],
                inference_label="observed",
                confidence="medium",
                rationale=_helm_plan_rationale(plan),
                required_human_inputs=human_inputs,
                rollback_commands=[plan.rollback_command],
                mutates_target=True,
                requires_human_approval=True,
            )
        )
    return steps


def _raw_plan_steps(
    reconstruction: ReconstructionPlan,
    *,
    phase_id: str,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
    depends_on: list[str] | None = None,
) -> list[dict[str, Any]]:
    return [
        _step(
            step_id=f"{phase_id}-{index}-{plan.kind}-{plan.name}",
            phase_id=phase_id,
            step_type=_raw_step_type(plan.kind),
            title=f"Apply {plan.kind} {plan.name}",
            depends_on=depends_on or [],
            manifest_refs=[plan.relative_path],
            commands=[
                {"kind": "dry_run", "command": plan.dry_run_command},
                {"kind": "apply", "command": plan.apply_command},
                {"kind": "validate", "command": plan.validation_command},
            ],
            expected_outcomes=[
                f"{plan.kind} {plan.name} exists in namespace {plan.namespace}.",
            ],
            evidence_refs=[plan.evidence_ref],
            inference_label="observed_or_inferred",
            confidence="medium",
            rationale="Manifest was normalized from available namespace evidence.",
            rollback_commands=[plan.rollback_command],
            mutates_target=True,
            requires_human_approval=True,
        )
        for index, plan in enumerate(_filtered_raw_plans(reconstruction, include, exclude), start=1)
    ]


def _validation_plan_steps(reconstruction: ReconstructionPlan) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for index, command in enumerate(reconstruction.validation_commands, start=1):
        step_type = "context_check" if command.startswith("helm list") else "k8s_validate"
        steps.append(
            _step(
                step_id=f"validate-preflight-{index}",
                phase_id="validate",
                step_type=step_type,
                title=f"Run validation command {index}",
                commands=[{"kind": "validate", "command": command}],
                expected_outcomes=["Command succeeds and expected resources are visible."],
                evidence_refs=["artifact.json"],
                inference_label="observed_or_inferred",
                confidence="medium",
                rationale="Validation confirms generated platform resources.",
                mutates_target=False,
                requires_human_approval=False,
            )
        )
    for index, plan in enumerate(reconstruction.helm_releases, start=1):
        steps.append(
            _step(
                step_id=f"validate-helm-{index}-{plan.release_name}",
                phase_id="validate",
                step_type="helm_validate",
                title=f"Validate Helm release {plan.release_name}",
                values_refs=[plan.values_relative_path],
                metadata=_helm_step_metadata(plan),
                commands=[
                    {
                        "kind": "helm_validate",
                        "command": _helm_template_command(
                            plan,
                            target_namespace=reconstruction.target_namespace,
                        ),
                    },
                    {"kind": "helm_status", "command": plan.validation_command},
                ],
                expected_outcomes=[
                    f"Helm chart {plan.chart_ref} renders for release {plan.release_name}.",
                    f"Helm release {plan.release_name} is visible in {reconstruction.target_namespace}.",
                ],
                evidence_refs=[plan.evidence_ref],
                inference_label="observed",
                confidence="medium",
                rationale=_helm_plan_rationale(plan),
                mutates_target=False,
                requires_human_approval=False,
            )
        )
    for index, plan in enumerate(reconstruction.raw_manifests, start=1):
        steps.append(
            _step(
                step_id=f"validate-k8s-{index}-{plan.kind}-{plan.name}",
                phase_id="validate",
                step_type="k8s_validate",
                title=f"Validate {plan.kind} {plan.name}",
                manifest_refs=[plan.relative_path],
                commands=[{"kind": "k8s_validate", "command": plan.validation_command}],
                expected_outcomes=[f"{plan.kind} {plan.name} exists in namespace {plan.namespace}."],
                evidence_refs=[plan.evidence_ref],
                inference_label="observed_or_inferred",
                confidence="medium",
                rationale="Validation confirms generated platform resources.",
                mutates_target=False,
                requires_human_approval=False,
            )
        )
    return steps


def _helm_step_metadata(plan: HelmReleasePlan) -> dict[str, Any]:
    return {
        "release_name": plan.release_name,
        "source_release_name": plan.source_release_name,
        "chart_ref": plan.chart_ref,
        "chart_version": plan.chart_version,
        "chart_source": plan.chart_source,
        "repo_name": plan.repo_name,
        "repo_url": plan.repo_url,
        "credential_secret_ref": plan.credential_secret_ref,
        "generated_by": "bosgenesis-mop-creation-agent",
    }


def _helm_template_command(plan: HelmReleasePlan, *, target_namespace: str) -> str:
    command = (
        f"helm template {plan.release_name} {plan.chart_ref} "
        f"--namespace {target_namespace} -f {plan.values_relative_path}"
    )
    if plan.chart_version:
        command = f"{command} --version {plan.chart_version}"
    return command


def _raw_step_type(kind: str) -> str:
    if kind == "ConfigMap":
        return "configmap"
    if kind == "PersistentVolumeClaim":
        return "pvc"
    if kind == "Ingress":
        return "ingress"
    return "kubernetes"


def _required_human_inputs_yaml(
    reconstruction: ReconstructionPlan,
    classification: ClassificationSummary | None,
) -> str:
    inputs = _required_human_inputs(reconstruction, classification)
    if not inputs:
        return "  []"
    return _indent_yaml(inputs, spaces=2)


def _required_human_inputs(
    reconstruction: ReconstructionPlan,
    classification: ClassificationSummary | None,
) -> list[dict[str, str]]:
    inputs: list[dict[str, str]] = []
    for plan in reconstruction.helm_releases:
        if plan.chart_ref.startswith("<"):
            inputs.append(
                {
                    "input_id": f"public_chart_ref_for_{plan.release_name}",
                    "target": f"helm_release/{plan.release_name}",
                    "reason": "Chart reference was unavailable in observed evidence.",
                    "blocks_phase": "install_helm_releases",
                }
            )
        if plan.chart_source == "private" and not plan.repo_url:
            inputs.append(
                {
                    "input_id": f"private_repo_url_for_{plan.release_name}",
                    "target": f"helm_release/{plan.release_name}",
                    "reason": "Private Helm chart source was selected but repo_url was not supplied.",
                    "blocks_phase": "install_helm_releases",
                }
            )
    for item in (classification.excluded if classification else []):
        if item.resource.kind == "Secret":
            inputs.append(
                {
                    "input_id": f"approved_secret_material_for_{item.resource.name}",
                    "target": f"Secret/{item.resource.name}",
                    "reason": "Secret values are excluded and must be supplied from an approved secure source.",
                    "blocks_phase": "prepare_secret_placeholders",
                }
            )
    return inputs


def _indent_yaml(value: Any, *, spaces: int) -> str:
    text = yaml.safe_dump(value, sort_keys=False, width=120).rstrip()
    return "\n".join((" " * spaces) + line if line else line for line in text.splitlines())


def _safe_step_id(value: str) -> str:
    return re.sub(r"[^a-z0-9_.-]+", "-", value.lower()).strip("-") or "step"


class _NoAliasSafeDumper(yaml.SafeDumper):
    def ignore_aliases(self, data: Any) -> bool:
        return True


def render_template(template: str, context: dict[str, Any]) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        return str(context.get(key, "TBD"))

    return re.sub(r"\{\{\s*([^}]+?)\s*\}\}", replace, template)


def _read_template(path: Path) -> str:
    if path.exists():
        return path.read_text(encoding="utf-8")
    raise FileNotFoundError(f"Required artifact template not found: {path}")


def _placeholder_step(section: str, title: str) -> str:
    return (
        f"**Step {section} - {title} placeholder**\n\n"
        "```bash\n"
        f"echo \"Phase 6 placeholder: {title}\"\n"
        "```\n\n"
        "**Expected output:** No target system changes are made.\n\n"
        "> STOP if this placeholder appears in a production execution package."
    )


def _resource_steps_by_plan(reconstruction: ReconstructionPlan, kind: str, section: str) -> str:
    plans = [plan for plan in reconstruction.raw_manifests if plan.kind == kind]
    if not plans:
        return _placeholder_step(section, f"{kind} recreation")
    blocks = []
    for index, plan in enumerate(plans, start=1):
        blocks.append(
            f"**Step {section}.{index} - Apply {kind} `{plan.name}`**\n\n"
            "Dry-run first:\n\n"
            "```bash\n"
            f"{plan.dry_run_command}\n"
            "```\n\n"
            "Apply after approval:\n\n"
            "```bash\n"
            f"{plan.apply_command}\n"
            "```\n\n"
            f"**Expected output:** {kind} `{plan.name}` exists in namespace "
            f"`{plan.namespace}`.\n\n"
            f"**Manifest:** `{plan.relative_path}`\n\n"
            f"**Evidence:** {plan.evidence_ref}"
            f"{_warning_suffix(plan.warnings)}"
        )
    return "\n\n---\n\n".join(blocks)


def _helm_steps_by_plan(reconstruction: ReconstructionPlan) -> str:
    if not reconstruction.helm_releases:
        return _placeholder_step("4.5", "Helm release recreation")
    blocks = []
    for index, plan in enumerate(reconstruction.helm_releases, start=1):
        blocks.append(
            f"**Step 4.5.{index} - Install Helm release `{plan.release_name}`**\n\n"
            "Dry-run first:\n\n"
            "```bash\n"
            f"{plan.dry_run_command}\n"
            "```\n\n"
            "Install after approval:\n\n"
            "```bash\n"
            f"{plan.install_command}\n"
            "```\n\n"
            f"**Expected output:** Helm release `{plan.release_name}` is deployed in "
            f"namespace `{reconstruction.target_namespace}`.\n\n"
            f"**Values:** `{plan.values_relative_path}`\n\n"
            f"**Chart source:** `{plan.chart_source}`\n\n"
            f"**Evidence:** {plan.evidence_ref}"
            f"{_warning_suffix(plan.warnings)}"
        )
    return "\n\n---\n\n".join(blocks)


def _raw_kubernetes_steps_by_plan(reconstruction: ReconstructionPlan) -> str:
    plans = [
        plan
        for plan in reconstruction.raw_manifests
        if plan.kind not in {"ConfigMap", "PersistentVolumeClaim", "Ingress"}
    ]
    if not plans:
        return _placeholder_step("4.6", "Raw Kubernetes recreation")
    blocks = []
    for index, plan in enumerate(plans, start=1):
        blocks.append(
            f"**Step 4.6.{index} - Apply {plan.kind} `{plan.name}`**\n\n"
            "```bash\n"
            f"{plan.dry_run_command}\n"
            f"{plan.apply_command}\n"
            "```\n\n"
            f"**Expected output:** {plan.kind} `{plan.name}` exists in namespace "
            f"`{plan.namespace}`.\n\n"
            f"**Manifest:** `{plan.relative_path}`\n\n"
            f"**Evidence:** {plan.evidence_ref}"
            f"{_warning_suffix(plan.warnings)}"
        )
    return "\n\n---\n\n".join(blocks)


def _helm_backup_commands(reconstruction: ReconstructionPlan) -> str:
    if not reconstruction.helm_releases:
        return "echo \"No Helm releases were found for backup reference\""
    return "\n".join(
        f"echo \"Review redacted Helm values: {plan.values_relative_path}\""
        for plan in reconstruction.helm_releases
    )


def _target_namespace_commands_yaml(target_namespace: str) -> str:
    return (
        "  - step_id: prepare-target-namespace\n"
        "    title: Ensure target namespace exists\n"
        "    type: namespace\n"
        "    depends_on: [verify_access]\n"
        "    evidence_refs: []\n"
        "    qdrant_refs: []\n"
        "    inference:\n"
        "      label: human_input_required\n"
        "      confidence: high\n"
        "      rationale: Target namespace is supplied by the generation request.\n"
        "    command: |\n"
        f"      kubectl get namespace {target_namespace} || kubectl create namespace {target_namespace}\n"
        f"      kubectl get namespace {target_namespace}\n"
        f"    expected: Namespace {target_namespace} exists.\n"
        "    on_failure: STOP and confirm namespace creation is approved.\n"
        "    mutates_target: true\n"
        "    requires_human_approval: true"
    )


def _helm_commands_yaml(reconstruction: ReconstructionPlan) -> str:
    if not reconstruction.helm_releases:
        return "  []"
    return "\n".join(_helm_command_yaml(plan, index) for index, plan in enumerate(reconstruction.helm_releases, 1))


def _helm_command_yaml(plan: HelmReleasePlan, index: int) -> str:
    return (
        f"  - step_id: helm-{index}-{plan.release_name}\n"
        f"    title: Install Helm release {plan.release_name}\n"
        "    type: helm_upgrade\n"
        f"    release_name: {plan.release_name}\n"
        f"    source_release_name: {plan.source_release_name or ''}\n"
        f"    chart_source: {plan.chart_source}\n"
        f"    chart_ref: {plan.chart_ref}\n"
        f"    chart_version: {plan.chart_version or ''}\n"
        f"    repo_name: {plan.repo_name or ''}\n"
        f"    repo_url: {plan.repo_url or ''}\n"
        f"    credential_secret_ref: {plan.credential_secret_ref or ''}\n"
        f"    values_refs: [{plan.values_relative_path}]\n"
        "    generated_by: bosgenesis-mop-creation-agent\n"
        "    depends_on: [apply_configmaps, apply_pvcs, prepare_secret_placeholders]\n"
        f"    evidence_refs: [{plan.evidence_ref}]\n"
        "    qdrant_refs: []\n"
        "    inference:\n"
        "      label: observed\n"
        "      confidence: medium\n"
        f"      rationale: {_helm_plan_rationale(plan)}\n"
        "    command: |\n"
        f"      {plan.dry_run_command}\n"
        f"      {plan.install_command}\n"
        f"    expected: Helm release {plan.release_name} is deployed.\n"
        "    on_failure: STOP; inspect Helm output and generated values file.\n"
        "    mutates_target: true\n"
        "    requires_human_approval: true"
    )


def _helm_plan_rationale(plan: HelmReleasePlan) -> str:
    if plan.chart_source == "observed":
        return "Release was discovered from Helm evidence; values are redacted before use."
    if plan.chart_source == "public":
        return "Chart reference was supplied as public chart evidence; values are redacted before use."
    if plan.chart_source == "private":
        return "Chart reference was supplied as private chart evidence; credentials must come from approved secret references."
    if plan.chart_source == "oci":
        return "Chart reference was supplied as OCI chart evidence; values are redacted before use."
    if plan.chart_source == "local":
        return "Chart reference was supplied as local chart evidence; values are redacted before use."
    return "Chart reference was supplied as operator evidence; values are redacted before use."


def _raw_commands_yaml(
    reconstruction: ReconstructionPlan,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
) -> str:
    plans = _filtered_raw_plans(reconstruction, include, exclude)
    if not plans:
        return "  []"
    return "\n".join(_raw_command_yaml(plan, index) for index, plan in enumerate(plans, 1))


def _raw_command_yaml(plan: RawManifestPlan, index: int) -> str:
    return (
        f"  - step_id: raw-{index}-{plan.kind.lower()}-{plan.name}\n"
        f"    title: Apply {plan.kind} {plan.name}\n"
        "    type: kubernetes\n"
        "    depends_on: []\n"
        f"    manifest_refs: [{plan.relative_path}]\n"
        f"    evidence_refs: [{plan.evidence_ref}]\n"
        "    qdrant_refs: []\n"
        "    inference:\n"
        "      label: observed_or_inferred\n"
        "      confidence: medium\n"
        "      rationale: Manifest was normalized from available namespace evidence.\n"
        "    command: |\n"
        f"      {plan.dry_run_command}\n"
        f"      {plan.apply_command}\n"
        f"    expected: {plan.kind} {plan.name} exists in {plan.namespace}.\n"
        "    on_failure: STOP; fix generated manifest and repeat dry-run.\n"
        "    mutates_target: true\n"
        "    requires_human_approval: true"
    )


def _raw_rollback_yaml(
    reconstruction: ReconstructionPlan,
    include: set[str] | None = None,
    exclude: set[str] | None = None,
) -> str:
    plans = _filtered_raw_plans(reconstruction, include, exclude)
    if not plans:
        return "  - No rollback required."
    return "\n".join(f"  - {plan.rollback_command}" for plan in reversed(plans))


def _helm_rollback_yaml(reconstruction: ReconstructionPlan) -> str:
    if not reconstruction.helm_releases:
        return "  - No rollback required."
    return "\n".join(
        f"  - {plan.rollback_command}" for plan in reversed(reconstruction.helm_releases)
    )


def _validation_commands_yaml(reconstruction: ReconstructionPlan) -> str:
    entries: list[str] = []
    for index, command in enumerate(reconstruction.validation_commands, 1):
        step_type = "context_check" if command.startswith("helm list") else "k8s_validate"
        entries.append(
            "  - step_id: validate-preflight-{index}\n"
            "    title: Validation command {index}\n"
            "    type: {step_type}\n"
            "    depends_on: []\n"
            "    evidence_refs: []\n"
            "    qdrant_refs: []\n"
            "    inference:\n"
            "      label: observed_or_inferred\n"
            "      confidence: medium\n"
            "      rationale: Validation confirms generated platform resources.\n"
            "    command: |\n"
            "      {command}\n"
            "    expected: Command succeeds and expected resources are visible.\n"
            "    on_failure: STOP and inspect target namespace.\n"
            "    mutates_target: false\n"
            "    requires_human_approval: false".format(
                index=index,
                step_type=step_type,
                command=command,
            )
        )
    for index, plan in enumerate(reconstruction.helm_releases, 1):
        entries.append(
            "  - step_id: validate-helm-{index}-{release_name}\n"
            "    title: Validate Helm release {release_name}\n"
            "    type: helm_validate\n"
            "    release_name: {release_name}\n"
            "    chart_source: {chart_source}\n"
            "    chart_ref: {chart_ref}\n"
            "    chart_version: {chart_version}\n"
            "    repo_name: {repo_name}\n"
            "    repo_url: {repo_url}\n"
            "    credential_secret_ref: {credential_secret_ref}\n"
            "    values_refs: [{values_ref}]\n"
            "    generated_by: bosgenesis-mop-creation-agent\n"
            "    depends_on: []\n"
            "    evidence_refs: [{evidence_ref}]\n"
            "    qdrant_refs: []\n"
            "    inference:\n"
            "      label: observed\n"
            "      confidence: medium\n"
            "      rationale: {rationale}\n"
            "    command: |\n"
            "      {template_command}\n"
            "      {status_command}\n"
            "    expected: Helm chart renders and release status is visible.\n"
            "    on_failure: STOP and inspect target namespace.\n"
            "    mutates_target: false\n"
            "    requires_human_approval: false".format(
                index=index,
                release_name=plan.release_name,
                chart_source=plan.chart_source,
                chart_ref=plan.chart_ref,
                chart_version=plan.chart_version or "",
                repo_name=plan.repo_name or "",
                repo_url=plan.repo_url or "",
                credential_secret_ref=plan.credential_secret_ref or "",
                values_ref=plan.values_relative_path,
                evidence_ref=plan.evidence_ref,
                rationale=_helm_plan_rationale(plan),
                template_command=_helm_template_command(
                    plan,
                    target_namespace=reconstruction.target_namespace,
                ),
                status_command=plan.validation_command,
            )
        )
    for index, plan in enumerate(reconstruction.raw_manifests, 1):
        entries.append(
            "  - step_id: validate-k8s-{index}-{kind}-{name}\n"
            "    title: Validate {kind} {name}\n"
            "    type: k8s_validate\n"
            "    depends_on: []\n"
            "    manifest_refs: [{manifest_ref}]\n"
            "    evidence_refs: [{evidence_ref}]\n"
            "    qdrant_refs: []\n"
            "    inference:\n"
            "      label: observed_or_inferred\n"
            "      confidence: medium\n"
            "      rationale: Validation confirms generated platform resources.\n"
            "    command: |\n"
            "      {command}\n"
            "    expected: {kind} {name} exists in namespace {namespace}.\n"
            "    on_failure: STOP and inspect target namespace.\n"
            "    mutates_target: false\n"
            "    requires_human_approval: false".format(
                index=index,
                kind=plan.kind,
                name=plan.name,
                manifest_ref=plan.relative_path,
                evidence_ref=plan.evidence_ref,
                command=plan.validation_command,
                namespace=plan.namespace,
            )
        )
    if not entries:
        return "  []"
    return "\n".join(entries)


def _helm_unknowns_yaml(reconstruction: ReconstructionPlan) -> str:
    unknowns = [
        f"  - {plan.release_name}: chart reference must be confirmed before install."
        for plan in reconstruction.helm_releases
        if plan.chart_ref.startswith("<")
    ]
    return "\n".join(unknowns) if unknowns else "  []"


def _filtered_raw_plans(
    reconstruction: ReconstructionPlan,
    include: set[str] | None,
    exclude: set[str] | None,
) -> list[RawManifestPlan]:
    plans = reconstruction.raw_manifests
    if include is not None:
        plans = [plan for plan in plans if plan.kind in include]
    if exclude is not None:
        plans = [plan for plan in plans if plan.kind not in exclude]
    return plans


def _join_commands(commands: Any) -> str:
    command_list = [command for command in commands if command]
    return "\n".join(command_list) if command_list else "echo \"No commands generated\""


def _warning_suffix(warnings: list[str]) -> str:
    if not warnings:
        return ""
    return "\n\n**Warnings:** " + "; ".join(warnings)


def _repair_suggestions_markdown(result: RepairSuggestionResult) -> str:
    lines = [f"- authority_order: {result.authority_order}"]
    if not result.enabled:
        lines.append("- llm_repair_suggestions: disabled")
        return "\n".join(lines)
    lines.append(f"- llm_repair_suggestions_status: {result.status}")
    if not result.suggestions:
        lines.append("- llm_suggestions: none")
        return "\n".join(lines)
    for suggestion in result.suggestions:
        lines.append(
            f"- {suggestion.label} / confidence={suggestion.confidence:.2f}: "
            f"{suggestion.target_type}:{suggestion.target_name} - {suggestion.suggestion}"
        )
    return "\n".join(lines)


def _bounded_reasoning_markdown(result: BoundedReasoningResult) -> str:
    lines = [f"- bounded_reasoning_authority_order: {result.authority_order}"]
    if not result.enabled:
        lines.append("- bounded_llm_reasoning: disabled")
        return "\n".join(lines)
    lines.append(f"- bounded_llm_reasoning_status: {result.status}")
    lines.append(f"- langgraph_used: {str(result.diagnostics.langgraph_used).lower()}")
    lines.append("- llm_output_authoritative: false")
    if result.status == "deterministic_sufficient":
        lines.append("- deterministic_evidence: sufficient")
    if not result.findings:
        lines.append("- bounded_reasoning_findings: none")
        return "\n".join(lines)
    for finding in result.findings:
        human_inputs = "; ".join(finding.required_human_inputs) or "human review required"
        qdrant_refs = ", ".join(finding.qdrant_refs) or "none"
        lines.append(
            f"- {finding.label} / confidence={finding.confidence:.2f}: "
            f"{finding.focus_area}:{finding.target} - {finding.recommendation} "
            f"(qdrant_refs={qdrant_refs}; human_inputs={human_inputs})"
        )
    return "\n".join(lines)


def _reasoning_and_repair_markdown(
    reasoning: BoundedReasoningResult,
    repair: RepairSuggestionResult,
) -> str:
    return "\n".join(
        [
            _bounded_reasoning_markdown(reasoning),
            _repair_suggestions_markdown(repair),
        ]
    )


def _qdrant_references_markdown(result: ReferenceLookupResult) -> str:
    if not result.enabled:
        return "- qdrant_lookup: disabled"
    lines = [
        f"- qdrant_lookup_status: {result.status}",
        "- authority: prior_reference_only_not_current_observed_fact",
    ]
    if not result.references:
        lines.append("- qdrant_references: none")
        return "\n".join(lines)
    for reference in result.references:
        component = reference.component_identity
        lines.append(
            f"- {reference.reference_id}: {component.kind}/{component.name} "
            f"score={reference.score:.2f} source_mop={reference.source_mop_id or 'unknown'} "
            f"matched={','.join(reference.matched_fields)}"
        )
    return "\n".join(lines)


def _qdrant_references_yaml(result: ReferenceLookupResult) -> str:
    if not result.references:
        return "  []"
    blocks = []
    for reference in result.references:
        component = reference.component_identity
        blocks.append(
            "  - reference_id: {reference_id}\n"
            "    citation_label: prior_reference_only_not_current_fact\n"
            "    source_mop_id: {source_mop_id}\n"
            "    source_artifact_type: {source_artifact_type}\n"
            "    source_namespace: {source_namespace}\n"
            "    component: {kind}/{name}\n"
            "    score: {score:.4f}\n"
            "    confidence: {confidence}\n"
            "    matched_fields: {matched_fields}\n"
            "    redaction_status: {redaction_status}".format(
                reference_id=reference.reference_id,
                source_mop_id=reference.source_mop_id or "",
                source_artifact_type=reference.source_artifact_type or "",
                source_namespace=reference.source_namespace or "",
                kind=component.kind,
                name=component.name,
                score=reference.score,
                confidence=reference.confidence,
                matched_fields=", ".join(reference.matched_fields),
                redaction_status=reference.redaction_status,
            )
        )
    return "\n".join(blocks)


def _memory_context_yaml(context: MemoryContext) -> str:
    if not context.enabled:
        return "  - memory_context: disabled"
    if not context.records:
        return f"  - memory_context: {context.status}"
    blocks = []
    for record in context.records[:5]:
        blocks.append(
            "  - memory_id: {memory_id}\n"
            "    kind: {kind}\n"
            "    authority: prior_context_only_not_current_fact\n"
            "    confidence: {confidence}\n"
            "    redaction_status: {redaction_status}\n"
            "    summary: {summary}".format(
                memory_id=record.memory_id,
                kind=record.kind,
                confidence=record.confidence,
                redaction_status=record.redaction_status,
                summary=yaml.safe_dump(record.summary, default_flow_style=True).strip(),
            )
        )
    return "\n".join(blocks)


def _inferences_yaml(
    reasoning: BoundedReasoningResult,
    repair: RepairSuggestionResult,
) -> str:
    base = (
        "  - label: observed_or_inferred\n"
        "    confidence: medium\n"
        "    rationale: Deterministic reconstruction writes normalized manifests and Helm values from available evidence; missing chart refs or specs require human completion.\n"
        "    authority_order: Observed evidence > deterministic reconstruction > Qdrant prior references > LLM suggestion > human approval"
    )
    blocks = [base]
    if not reasoning.enabled:
        blocks.append(
            "  - label: bounded_llm_reasoning_disabled\n"
            "    confidence: high\n"
            "    rationale: Optional bounded LLM reasoning is disabled.\n"
            "    executable_yaml_allowed: false"
        )
    elif not reasoning.findings:
        blocks.append(
            f"  - label: bounded_llm_reasoning_{reasoning.status}\n"
            "    confidence: high\n"
            "    rationale: No executable YAML or Helm command was generated by the bounded reasoning layer.\n"
            "    executable_yaml_allowed: false"
        )
    else:
        for finding in reasoning.findings:
            qdrant_refs = ", ".join(finding.qdrant_refs)
            human_inputs = ", ".join(finding.required_human_inputs)
            blocks.append(
                "  - label: llm_suggestion_requires_human_review\n"
                f"    focus_area: {finding.focus_area}\n"
                f"    target: {finding.target}\n"
                f"    confidence: {finding.confidence:.2f}\n"
                f"    rationale: {finding.rationale}\n"
                f"    qdrant_refs: [{qdrant_refs}]\n"
                f"    required_human_inputs: [{human_inputs}]\n"
                "    authoritative: false\n"
                "    executable_yaml_allowed: false"
            )
    if not repair.enabled:
        blocks.append(
            "  - label: llm_repair_disabled\n"
            "    confidence: high\n"
            "    rationale: Optional LLM repair suggestions are disabled.\n"
            "    executable_yaml_allowed: false"
        )
    elif not repair.suggestions:
        blocks.append(
            f"  - label: llm_repair_{repair.status}\n"
            "    confidence: high\n"
            "    rationale: No executable YAML was generated by the LLM repair layer.\n"
            "    executable_yaml_allowed: false"
        )
    for suggestion in repair.suggestions:
        blocks.append(
            "  - label: llm_suggestion_requires_human_review\n"
            f"    target: {suggestion.target_type}:{suggestion.target_name}\n"
            f"    confidence: {suggestion.confidence:.2f}\n"
            f"    rationale: {suggestion.rationale}\n"
            "    executable_yaml_allowed: false"
        )
    return "\n".join(blocks)


def _confidence_summary_yaml(
    reasoning: BoundedReasoningResult,
    repair: RepairSuggestionResult,
) -> str:
    return (
        "  overall: medium_when_snapshot_found_low_when_missing\n"
        f"  bounded_llm_reasoning_status: {reasoning.status}\n"
        f"  bounded_llm_reasoning_accepted_findings: {len(reasoning.findings)}\n"
        f"  llm_repair_status: {repair.status}\n"
        f"  llm_repair_accepted_suggestions: {len(repair.suggestions)}\n"
        "  llm_output_authoritative: false"
    )


def _helm_summary(
    inventory: NormalizedInventory | None,
    reconstruction: ReconstructionPlan | None = None,
) -> str:
    if reconstruction and reconstruction.helm_releases:
        names = ", ".join(plan.release_name for plan in reconstruction.helm_releases[:10])
        suffix = " ..." if len(reconstruction.helm_releases) > 10 else ""
        return f"Executable Helm plans generated for releases: {names}{suffix}"
    if not inventory or not inventory.helm_releases:
        return "No Helm releases found in the selected stored snapshot."
    names = ", ".join(release.release_name for release in inventory.helm_releases[:10])
    suffix = " ..." if len(inventory.helm_releases) > 10 else ""
    return f"Stored snapshot includes Helm releases: {names}{suffix}"


def _raw_count(
    inventory: NormalizedInventory | None,
    classification: ClassificationSummary | None,
) -> int:
    if classification:
        return classification.raw_k8s_count
    return inventory.resource_count if inventory else 0


def _resource_summary(
    inventory: NormalizedInventory | None,
    classification: ClassificationSummary | None = None,
) -> str:
    if classification:
        resources = [item.resource for item in classification.raw_k8s]
        if not resources:
            return "No supported raw Kubernetes resources are eligible for executable recreation."
    else:
        resources = inventory.resources if inventory else []
        if not resources:
            return "No raw Kubernetes resources found in the selected stored snapshot."

    counts: dict[str, int] = {}
    for resource in resources:
        counts[resource.kind] = counts.get(resource.kind, 0) + 1
    return ", ".join(f"{kind}={count}" for kind, count in sorted(counts.items()))


def _excluded_summary(classification: ClassificationSummary | None) -> str:
    if not classification or not classification.excluded:
        return "No blocked or out-of-scope resources were classified for exclusion."
    counts: dict[str, int] = {}
    for item in classification.excluded:
        counts[item.resource.kind] = counts.get(item.resource.kind, 0) + 1
    return ", ".join(f"{kind}={count}" for kind, count in sorted(counts.items()))


def _raw_classified_resources(
    inventory: NormalizedInventory | None,
    classification: ClassificationSummary | None,
) -> list:
    if classification:
        return [item.resource for item in classification.raw_k8s]
    if not inventory or not inventory.resources:
        return []
    return inventory.resources


def _unknowns(inventory: NormalizedInventory | None) -> str:
    if not inventory:
        return "- Inventory is missing from snapshots and MCP enrichment."
    return (
        "- Exact install command synthesis requires a later generation phase.\n"
        "- Secret values are intentionally unavailable and must be supplied by humans."
    )


def _resource_steps(
    inventory: NormalizedInventory | None,
    kind: str,
    section: str,
    classification: ClassificationSummary | None = None,
) -> str:
    resources = [
        item for item in _raw_classified_resources(inventory, classification) if item.kind == kind
    ]
    if not resources:
        return _placeholder_step(section, f"{kind} recreation")
    blocks = []
    for index, resource in enumerate(resources, start=1):
        blocks.append(
            f"**Step {section}.{index} - Prepare {kind} `{resource.name}`**\n\n"
            "```bash\n"
            f"echo \"Generate and review {kind} manifest for {resource.name} in "
            "{{target_namespace}}\"\n"
            "```\n\n"
            f"**Expected output:** {kind} `{resource.name}` is represented in generated manifests "
            "after Phase 6 normalization.\n\n"
            f"**Evidence:** {inventory.source}:{inventory.snapshot_id}:{resource.entity_key or resource.name}"
        )
    return "\n\n---\n\n".join(blocks)


def _helm_steps(inventory: NormalizedInventory | None) -> str:
    if not inventory or not inventory.helm_releases:
        return _placeholder_step("4.5", "Helm release recreation")
    blocks = []
    for index, release in enumerate(inventory.helm_releases, start=1):
        chart = release.chart_name or "<chart-ref-requires-enrichment>"
        blocks.append(
            f"**Step 4.5.{index} - Prepare Helm release `{release.release_name}`**\n\n"
            "```bash\n"
            f"helm upgrade --install {release.release_name} {chart} \\\n"
            "  --namespace {{target_namespace}} \\\n"
            f"  -f values-{release.release_name}.yaml \\\n"
            "  --dry-run\n"
            "```\n\n"
            "**Expected output:** Helm dry-run succeeds after chart repository and values are "
            "enriched in a later phase.\n\n"
            f"**Evidence:** {inventory.source}:{inventory.snapshot_id}:{release.entity_key or release.release_name}"
        )
    return "\n\n---\n\n".join(blocks)


def _raw_kubernetes_steps(
    inventory: NormalizedInventory | None,
    classification: ClassificationSummary | None = None,
) -> str:
    resources = (
        [
            item
            for item in _raw_classified_resources(inventory, classification)
            if item.kind not in {"ConfigMap", "PersistentVolumeClaim", "Ingress"}
        ]
    )
    if not resources:
        return _placeholder_step("4.6", "Raw Kubernetes recreation")
    blocks = []
    for index, resource in enumerate(resources, start=1):
        filename = f"generated/{resource.kind.lower()}-{resource.name}.yaml"
        blocks.append(
            f"**Step 4.6.{index} - Prepare {resource.kind} `{resource.name}`**\n\n"
            "```bash\n"
            f"kubectl apply -f {filename} -n {{{{target_namespace}}}} --dry-run=server -o yaml\n"
            "```\n\n"
            f"**Expected output:** {resource.kind} `{resource.name}` is accepted by server-side "
            "dry-run after manifest normalization in a later phase.\n\n"
            f"**Evidence:** {inventory.source}:{inventory.snapshot_id}:{resource.entity_key or resource.name}"
        )
    return "\n\n---\n\n".join(blocks)


def _evidence_references(
    inventory: NormalizedInventory | None,
    snapshot_sources_attempted: list[str],
    mcp_sources_attempted: list[str],
) -> str:
    snapshot_attempted = ", ".join(snapshot_sources_attempted) if snapshot_sources_attempted else "none"
    mcp_attempted = ", ".join(mcp_sources_attempted) if mcp_sources_attempted else "none"
    if not inventory:
        return (
            "- artifact.json: Phase 6 local artifact manifest.\n"
            f"- Snapshot sources attempted: {snapshot_attempted}.\n"
            f"- MCP sources attempted: {mcp_attempted}."
        )
    return (
        f"- {inventory.source}: snapshot_id={inventory.snapshot_id}, "
        f"resources={inventory.resource_count}, helm_releases={inventory.helm_release_count}.\n"
        f"- Snapshot sources attempted: {snapshot_attempted}.\n"
        f"- MCP sources attempted: {mcp_attempted}."
    )


def _source_status(source_name: str, mcp_sources_attempted: list[str]) -> str:
    return "attempted" if source_name in mcp_sources_attempted else "not_attempted"


def _source_refs(source_name: str, mcp_sources_attempted: list[str]) -> str:
    if source_name not in mcp_sources_attempted:
        return "  []"
    return f"  - artifact.json#mcp.sources_attempted[{source_name}]"


def _resource_inventory_yaml(
    inventory: NormalizedInventory | None,
    classification: ClassificationSummary | None = None,
) -> str:
    resources = _raw_classified_resources(inventory, classification)
    if not resources:
        return "  []"
    return "\n".join(
        "  - kind: {kind}\n"
        "    name: {name}\n"
        "    namespace: {namespace}\n"
        "    source: {source}\n"
        "    entity_key: {entity_key}".format(
            kind=resource.kind,
            name=resource.name,
            namespace=resource.namespace,
            source=resource.source,
            entity_key=resource.entity_key or "",
        )
        for resource in resources
    )


def _professional_resource_snapshot(
    inventory: NormalizedInventory | None,
    classification: ClassificationSummary | None,
) -> dict[str, Any]:
    category_by_key: dict[tuple[str, str, str], tuple[str, str]] = {}
    excluded_resources: list[dict[str, str]] = []
    if classification:
        for item in classification.resources:
            key = _resource_key(item.resource.kind, item.resource.namespace, item.resource.name)
            category_by_key[key] = (item.category.value, item.reason)
            if item.category.value == "excluded":
                excluded_resources.append(
                    {
                        "kind": item.resource.kind,
                        "name": item.resource.name,
                        "namespace": item.resource.namespace,
                        "reason": item.reason,
                    }
                )

    helm_releases: list[dict[str, str]] = []
    resources_by_kind: dict[str, list[dict[str, str]]] = {}
    if inventory:
        helm_releases = [
            {
                "release_name": release.release_name,
                "namespace": release.namespace,
                "chart_name": release.chart_name or "",
                "chart_version": release.chart_version or "",
                "app_version": release.app_version or "",
                "revision": str(release.revision or ""),
                "status": release.status or "",
            }
            for release in sorted(inventory.helm_releases, key=lambda item: item.release_name)
        ]
        for resource in sorted(inventory.resources, key=lambda item: (item.kind, item.name)):
            category, reason = category_by_key.get(
                _resource_key(resource.kind, resource.namespace, resource.name),
                ("unclassified", ""),
            )
            resources_by_kind.setdefault(resource.kind, []).append(
                {
                    "kind": resource.kind,
                    "name": resource.name,
                    "namespace": resource.namespace,
                    "api_version": resource.api_version or "",
                    "status": resource.status_summary or "",
                    "source": resource.source,
                    "category": category,
                    "reason": reason,
                }
            )

    return {
        "helm_releases": helm_releases,
        "resources_by_kind": resources_by_kind,
        "excluded_resources": sorted(
            excluded_resources,
            key=lambda item: (item["kind"], item["name"]),
        ),
    }


def _resource_key(kind: str, namespace: str, name: str) -> tuple[str, str, str]:
    return (kind.lower(), namespace, name)


def _excluded_resources_yaml(classification: ClassificationSummary | None) -> str:
    if not classification or not classification.excluded:
        return "  []"
    return _classified_resources_yaml(classification.excluded)


def _excluded_resources_markdown(classification: ClassificationSummary | None) -> str:
    if not classification or not classification.excluded:
        return "- No blocked or out-of-scope resources were observed."
    lines = []
    for item in classification.excluded:
        lines.append(
            f"- {item.resource.kind}/{item.resource.name} "
            f"namespace={item.resource.namespace or '<cluster>'} reason={item.reason}"
        )
    return "\n".join(lines)


def _classification_manifest(classification: ClassificationSummary | None) -> dict[str, Any]:
    if not classification:
        return {
            "enabled": False,
            "helm_managed_count": 0,
            "raw_k8s_count": 0,
            "excluded_count": 0,
            "warning_only_count": 0,
            "resources": [],
            "warnings": [],
        }
    return {
        "enabled": True,
        "namespace": classification.namespace,
        "helm_managed_count": classification.helm_managed_count,
        "raw_k8s_count": classification.raw_k8s_count,
        "excluded_count": classification.excluded_count,
        "warning_only_count": classification.warning_only_count,
        "resources": [
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
        ],
        "warnings": classification.warnings,
    }


def _reconstruction_manifest(reconstruction: ReconstructionPlan) -> dict[str, Any]:
    return {
        "target_namespace": reconstruction.target_namespace,
        "raw_manifest_count": reconstruction.raw_manifest_count,
        "helm_release_count": reconstruction.helm_release_count,
        "generated_manifests": [
            {
                "kind": plan.kind,
                "name": plan.name,
                "namespace": plan.namespace,
                "file_path": plan.file_path,
                "relative_path": plan.relative_path,
                "warnings": plan.warnings,
            }
            for plan in reconstruction.raw_manifests
        ],
        "generated_values": [
            {
                "release_name": plan.release_name,
                "source_release_name": plan.source_release_name,
                "chart_ref": plan.chart_ref,
                "chart_version": plan.chart_version,
                "chart_source": plan.chart_source,
                "repo_name": plan.repo_name,
                "repo_url": plan.repo_url,
                "credential_secret_ref": plan.credential_secret_ref,
                "file_path": plan.values_file_path,
                "relative_path": plan.values_relative_path,
                "warnings": plan.warnings,
            }
            for plan in reconstruction.helm_releases
        ],
        "warnings": reconstruction.warnings,
    }


def _classified_resources_yaml(resources: list[ClassifiedResource]) -> str:
    return "\n".join(
        "  - kind: {kind}\n"
        "    name: {name}\n"
        "    namespace: {namespace}\n"
        "    category: {category}\n"
        "    reason: {reason}\n"
        "    helm_release_name: {helm_release_name}".format(
            kind=item.resource.kind,
            name=item.resource.name,
            namespace=item.resource.namespace,
            category=item.category.value,
            reason=item.reason,
            helm_release_name=item.helm_release_name or "",
        )
        for item in resources
    )


def _helm_inventory_yaml(inventory: NormalizedInventory | None) -> str:
    if not inventory or not inventory.helm_releases:
        return "  []"
    return "\n".join(
        "  - release_name: {release_name}\n"
        "    namespace: {namespace}\n"
        "    chart_name: {chart_name}\n"
        "    chart_version: {chart_version}\n"
        "    status: {status}".format(
            release_name=release.release_name,
            namespace=release.namespace,
            chart_name=release.chart_name or "",
            chart_version=release.chart_version or "",
            status=release.status or "",
        )
        for release in inventory.helm_releases
    )


def _unknowns_yaml(inventory: NormalizedInventory | None) -> str:
    if not inventory:
        return "  - Inventory is missing from snapshots and MCP enrichment."
    return (
        "  - Exact install command synthesis requires a later generation phase.\n"
        "  - Secret values are intentionally unavailable and must be supplied by humans."
    )


def _assert_required_sections(content: str) -> None:
    missing = [section for section in REQUIRED_HUMAN_MOP_SECTIONS if section not in content]
    if missing:
        raise ValueError(f"Human MoP template is missing required sections: {', '.join(missing)}")
