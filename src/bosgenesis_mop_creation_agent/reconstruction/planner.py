from __future__ import annotations

from pathlib import Path

from bosgenesis_mop_creation_agent.classification.models import ClassificationSummary
from bosgenesis_mop_creation_agent.reconstruction.command_builder import build_helm_plan, build_raw_plan
from bosgenesis_mop_creation_agent.reconstruction.helm_values import redacted_values_yaml
from bosgenesis_mop_creation_agent.reconstruction.manifest_normalizer import (
    dump_manifest,
    normalize_manifest,
)
from bosgenesis_mop_creation_agent.reconstruction.models import ReconstructionPlan
from bosgenesis_mop_creation_agent.sources.snapshot_models import InventoryHelmRelease, NormalizedInventory


def build_reconstruction_plan(
    *,
    inventory: NormalizedInventory | None,
    classification: ClassificationSummary | None,
    target_namespace: str,
    generated_dir: Path,
    values_dir: Path,
) -> ReconstructionPlan:
    generated_dir.mkdir(parents=True, exist_ok=True)
    values_dir.mkdir(parents=True, exist_ok=True)
    if inventory is None or classification is None:
        return ReconstructionPlan(
            target_namespace=target_namespace,
            warnings=["reconstruction_skipped_inventory_missing"],
        )

    raw_plans = []
    warnings = []
    for classified in classification.raw_k8s:
        resource = classified.resource
        manifest, manifest_warnings = normalize_manifest(resource, target_namespace)
        filename = _manifest_filename(resource.kind, resource.name)
        file_path = generated_dir / filename
        file_path.write_text(dump_manifest(manifest), encoding="utf-8")
        warnings.extend(
            f"raw_manifest:{resource.kind}/{resource.name}:{warning}"
            for warning in manifest_warnings
        )
        raw_plans.append(
            build_raw_plan(
                kind=resource.kind,
                name=resource.name,
                target_namespace=target_namespace,
                file_path=str(file_path),
                relative_path=f"generated/{filename}",
                evidence_ref=_resource_evidence(inventory, resource.entity_key or resource.name),
                warnings=manifest_warnings,
            )
        )

    helm_plans = []
    for release in inventory.helm_releases:
        values_filename = f"values-{_safe_name(release.release_name)}.yaml"
        values_file = values_dir / values_filename
        values_file.write_text(redacted_values_yaml(release), encoding="utf-8")
        chart_ref = _chart_ref(release)
        release_warnings = []
        if chart_ref.startswith("<"):
            release_warnings.append("chart_ref_missing_human_input_required")
            warnings.append(f"helm_release:{release.release_name}:chart_ref_missing_human_input_required")
        helm_plans.append(
            build_helm_plan(
                release_name=release.release_name,
                chart_ref=chart_ref,
                target_namespace=target_namespace,
                values_file_path=str(values_file),
                values_relative_path=f"values/{values_filename}",
                evidence_ref=_resource_evidence(
                    inventory,
                    release.entity_key or release.release_name,
                ),
                warnings=release_warnings,
            )
        )

    validation_commands = [
        f"kubectl get all,configmap,pvc,ingress -n {target_namespace}",
        f"helm list -n {target_namespace}",
    ]
    rollback_commands = [
        *[plan.rollback_command for plan in reversed(raw_plans)],
        *[plan.rollback_command for plan in reversed(helm_plans)],
    ]
    return ReconstructionPlan(
        target_namespace=target_namespace,
        raw_manifests=raw_plans,
        helm_releases=helm_plans,
        validation_commands=validation_commands,
        rollback_commands=rollback_commands,
        warnings=warnings,
    )


def _chart_ref(release: InventoryHelmRelease) -> str:
    if release.chart_name:
        return release.chart_name
    release_payload = release.normalized_payload.get("release")
    if isinstance(release_payload, dict):
        chart = release_payload.get("chart")
        if isinstance(chart, str) and chart:
            return chart
    live = release.normalized_payload.get("mcp_live")
    if isinstance(live, dict):
        live_release = live.get("release")
        if isinstance(live_release, dict):
            chart = live_release.get("chart")
            if isinstance(chart, str) and chart:
                return chart
    return "<chart-ref-required>"


def _manifest_filename(kind: str, name: str) -> str:
    return f"{kind.lower()}-{_safe_name(name)}.yaml"


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in "-." else "-" for char in value.lower())


def _resource_evidence(inventory: NormalizedInventory, entity_key: str) -> str:
    return f"{inventory.source}:{inventory.snapshot_id}:{entity_key}"
