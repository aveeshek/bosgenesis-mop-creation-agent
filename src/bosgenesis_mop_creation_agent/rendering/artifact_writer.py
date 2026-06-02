from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from bosgenesis_mop_creation_agent.classification.models import (
    ClassificationSummary,
    ClassifiedResource,
)
from bosgenesis_mop_creation_agent.config.settings import LlmSettings
from bosgenesis_mop_creation_agent.llm.models import RepairSuggestionResult
from bosgenesis_mop_creation_agent.llm.repair_suggester import build_repair_suggestions
from bosgenesis_mop_creation_agent.models.requests import MoPGenerationRequest
from bosgenesis_mop_creation_agent.reconstruction.models import (
    HelmReleasePlan,
    RawManifestPlan,
    ReconstructionPlan,
)
from bosgenesis_mop_creation_agent.reconstruction.planner import build_reconstruction_plan
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
        artifact_manifest_path = run_dir / "artifact.json"
        reconstruction = build_reconstruction_plan(
            inventory=inventory,
            classification=classification,
            target_namespace=request.target_namespace,
            generated_dir=generated_dir,
            values_dir=values_dir,
        )
        repair_suggestions = build_repair_suggestions(
            settings=self._llm_settings,
            reconstruction=reconstruction,
            classification=classification,
            correlation_id=correlation_id,
        )
        all_warnings = [*warnings, *reconstruction.warnings, *repair_suggestions.warnings]

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
            repair_suggestions=repair_suggestions,
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
        _assert_required_sections(human_mop_content)

        human_mop_markdown_path.write_text(human_mop_content, encoding="utf-8")
        installation_notes_path.write_text(installation_notes_content, encoding="utf-8")
        _write_placeholder_pdf(human_mop_pdf_path, human_mop_content)

        manifest = {
            "artifact_type": "phase6_reconstruction_mop_artifact",
            "schema_version": "1.0",
            "mop_id": mop_id,
            "run_id": run_id,
            "correlation_id": correlation_id,
            "source_namespace": source_namespace,
            "target_namespace": request.target_namespace,
            "generation_mode": request.mode.value,
            "created_at": created_at.isoformat(),
            "status": "generated",
            "external_calls": {
                "kubernetes": "k8s_inspector_mcp" in (mcp_sources_attempted or []),
                "helm": "helm_manager_mcp" in (mcp_sources_attempted or []),
                "qdrant": False,
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
        repair_suggestions: RepairSuggestionResult,
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
            "generation_mode": request.mode.value,
            "source_snapshot_id_or_timestamp": (
                inventory.snapshot_id if inventory else request.source_snapshot_id
            ),
            "run_id": run_id,
            "correlation_id": correlation_id,
            "change_reason": "Phase 6 platform reconstruction artifact generation with normalized raw manifests and Helm value files.",
            "helm_release_count": str(inventory.helm_release_count if inventory else 0),
            "helm_release_summary": _helm_summary(inventory),
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
            "qdrant_prior_references": "- None. Qdrant lookup is not executed in Phase 6.",
            "inference_labels_and_rationale": (
                _repair_suggestions_markdown(repair_suggestions)
            ),
            "excluded_resources": _excluded_resources_markdown(classification),
            "generation_status": "generated",
            "qdrant_lookup_status": "not_executed",
            "qdrant_reference_count": "0",
            "required_human_inputs_yaml": empty_yaml_list,
            "k8s_mcp_status": _source_status("k8s_inspector_mcp", mcp_sources_attempted),
            "k8s_evidence_references_yaml": _source_refs("k8s_inspector_mcp", mcp_sources_attempted),
            "helm_mcp_status": _source_status("helm_manager_mcp", mcp_sources_attempted),
            "helm_evidence_references_yaml": _source_refs("helm_manager_mcp", mcp_sources_attempted),
            "data_ingestion_status": _source_status("data_ingestion_mcp", mcp_sources_attempted),
            "data_ingestion_references_yaml": _source_refs(
                "data_ingestion_mcp",
                mcp_sources_attempted,
            ),
            "qdrant_references_yaml": empty_yaml_list,
            "helm_releases_yaml": _helm_inventory_yaml(inventory),
            "raw_kubernetes_resources_yaml": _resource_inventory_yaml(inventory, classification),
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
                _inferences_yaml(repair_suggestions)
            ),
            "unknowns_yaml": _unknowns_yaml(inventory),
            "confidence_summary_yaml": (
                "  overall: medium_when_snapshot_found_low_when_missing"
            ),
            "human_mop_pdf_path": str(human_mop_pdf_path),
            "installation_notes_path": str(installation_notes_path),
            "generated_manifests_dir": str(generated_dir),
            "generated_values_dir": str(values_dir),
            "evidence_dir": str(evidence_dir),
        }


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
        "    type: helm\n"
        "    depends_on: [apply_configmaps, apply_pvcs, prepare_secret_placeholders]\n"
        f"    evidence_refs: [{plan.evidence_ref}]\n"
        "    qdrant_refs: []\n"
        "    inference:\n"
        "      label: observed\n"
        "      confidence: medium\n"
        "      rationale: Release was discovered from Helm evidence; values are redacted.\n"
        "    command: |\n"
        f"      {plan.dry_run_command}\n"
        f"      {plan.install_command}\n"
        f"    expected: Helm release {plan.release_name} is deployed.\n"
        "    on_failure: STOP; inspect Helm output and generated values file.\n"
        "    mutates_target: true\n"
        "    requires_human_approval: true"
    )


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
    commands = [
        *reconstruction.validation_commands,
        *[plan.validation_command for plan in reconstruction.helm_releases],
        *[plan.validation_command for plan in reconstruction.raw_manifests],
    ]
    if not commands:
        return "  []"
    return "\n".join(
        "  - step_id: validate-{index}\n"
        "    title: Validation command {index}\n"
        "    type: validation\n"
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
        "    requires_human_approval: false".format(index=index, command=command)
        for index, command in enumerate(commands, 1)
    )


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


def _inferences_yaml(result: RepairSuggestionResult) -> str:
    base = (
        "  - label: observed_or_inferred\n"
        "    confidence: medium\n"
        "    rationale: Phase 6 writes normalized manifests and Helm values from available evidence; missing chart refs or specs require human completion.\n"
        "    authority_order: Observed evidence > deterministic normalization > LLM suggestion > human fill-in"
    )
    if not result.enabled:
        return base + "\n  - label: llm_repair_disabled\n    confidence: high\n    rationale: Optional LLM repair suggestions are disabled."
    if not result.suggestions:
        return (
            base
            + f"\n  - label: llm_repair_{result.status}\n"
            "    confidence: high\n"
            "    rationale: No executable YAML was generated by the LLM repair layer."
        )
    blocks = [base]
    for suggestion in result.suggestions:
        blocks.append(
            "  - label: llm_suggestion_requires_human_review\n"
            f"    target: {suggestion.target_type}:{suggestion.target_name}\n"
            f"    confidence: {suggestion.confidence:.2f}\n"
            f"    rationale: {suggestion.rationale}\n"
            "    executable_yaml_allowed: false"
        )
    return "\n".join(blocks)


def _helm_summary(inventory: NormalizedInventory | None) -> str:
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
                "chart_ref": plan.chart_ref,
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


def _write_placeholder_pdf(path: Path, markdown_content: str) -> None:
    headings = [
        line.lstrip("# ").strip()
        for line in markdown_content.splitlines()
        if line.startswith("#") and line.strip("# ").strip()
    ]
    lines = ["BOS Genesis MoP Creation Agent", "Phase 6 PDF Placeholder", *headings[:30]]
    content_stream = _pdf_text_stream(lines)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(content_stream)} >>\nstream\n".encode("ascii")
        + content_stream
        + b"\nendstream",
    ]

    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii"))
        output.extend(obj)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        (
            "trailer\n"
            f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            "startxref\n"
            f"{xref_offset}\n"
            "%%EOF\n"
        ).encode("ascii")
    )
    path.write_bytes(bytes(output))


def _pdf_text_stream(lines: list[str]) -> bytes:
    escaped_lines = [_escape_pdf_text(line[:90]) for line in lines]
    commands = ["BT", "/F1 12 Tf", "72 740 Td"]
    for index, line in enumerate(escaped_lines):
        if index:
            commands.append("0 -18 Td")
        commands.append(f"({line}) Tj")
    commands.append("ET")
    return "\n".join(commands).encode("ascii")


def _escape_pdf_text(value: str) -> str:
    ascii_value = value.encode("ascii", errors="ignore").decode("ascii")
    return ascii_value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
