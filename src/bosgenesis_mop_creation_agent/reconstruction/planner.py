from __future__ import annotations

import hashlib
from pathlib import Path

from bosgenesis_mop_creation_agent.classification.models import (
    ClassificationSummary,
    ClassifiedResource,
    ResourceCategory,
)
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
    for classified in _raw_reconstruction_items(classification):
        resource = classified.resource
        plan_name = _generated_resource_name(resource.kind, resource.name)
        manifest, manifest_warnings = normalize_manifest(
            resource,
            target_namespace,
            generated_name=plan_name if plan_name != resource.name else None,
        )
        plan_warnings = list(manifest_warnings)
        if resource.kind == "Ingress" and plan_name != resource.name:
            plan_warnings.append(f"ingress_name_prefixed_from:{resource.name}")
        if classified.category == ResourceCategory.HELM_MANAGED and resource.kind == "Ingress":
            plan_warnings.append("ingress_reconstructed_from_helm_managed_source")
        filename = _manifest_filename(resource.kind, plan_name)
        file_path = generated_dir / filename
        file_path.write_text(dump_manifest(manifest), encoding="utf-8")
        warnings.extend(
            f"raw_manifest:{resource.kind}/{resource.name}:{warning}"
            for warning in plan_warnings
        )
        raw_plans.append(
            build_raw_plan(
                kind=resource.kind,
                name=plan_name,
                target_namespace=target_namespace,
                file_path=str(file_path),
                relative_path=f"generated/{filename}",
                evidence_ref=_resource_evidence(inventory, resource.entity_key or resource.name),
                warnings=plan_warnings,
            )
        )

    helm_plans = []
    for release in inventory.helm_releases:
        values_filename = f"values-{_safe_name(release.release_name)}.yaml"
        values_file = values_dir / values_filename
        values_file.write_text(redacted_values_yaml(release), encoding="utf-8")
        chart_ref = _chart_ref(release)
        chart_metadata = _chart_metadata(release)
        release_warnings = []
        if chart_ref.startswith("<"):
            release_warnings.append("chart_ref_missing_human_input_required")
            warnings.append(f"helm_release:{release.release_name}:chart_ref_missing_human_input_required")
        if (
            chart_metadata["chart_source"] == "private"
            and not chart_metadata.get("repo_url")
            and not str(chart_ref).startswith("oci://")
        ):
            release_warnings.append("private_repo_url_required")
            warnings.append(f"helm_release:{release.release_name}:private_repo_url_required")
        helm_plans.append(
            build_helm_plan(
                release_name=release.release_name,
                chart_ref=chart_ref,
                chart_version=chart_metadata.get("chart_version"),
                chart_source=str(chart_metadata["chart_source"]),
                repo_name=chart_metadata.get("repo_name"),
                repo_url=chart_metadata.get("repo_url"),
                credential_secret_ref=chart_metadata.get("credential_secret_ref"),
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
    if release.chart_name and _is_installable_chart_ref(release.chart_name):
        return release.chart_name
    hint = release.normalized_payload.get("operator_chart_hint")
    if isinstance(hint, dict):
        chart_ref = hint.get("chart_ref")
        repo_name = hint.get("repo_name")
        chart_name = hint.get("chart_name")
        if isinstance(chart_ref, str) and chart_ref:
            return chart_ref
        if isinstance(repo_name, str) and repo_name and isinstance(chart_name, str) and chart_name:
            return f"{repo_name}/{chart_name}"
        if isinstance(chart_name, str) and chart_name and _is_installable_chart_ref(chart_name):
            return chart_name
    release_payload = release.normalized_payload.get("release")
    if isinstance(release_payload, dict):
        chart = release_payload.get("chart")
        if isinstance(chart, str) and chart and _is_installable_chart_ref(chart):
            return chart
    live = release.normalized_payload.get("mcp_live")
    if isinstance(live, dict):
        live_release = live.get("release")
        if isinstance(live_release, dict):
            chart = live_release.get("chart")
            if isinstance(chart, str) and chart and _is_installable_chart_ref(chart):
                return chart
    return "<chart-ref-required>"


def _chart_metadata(release: InventoryHelmRelease) -> dict[str, str | None]:
    hint = release.normalized_payload.get("operator_chart_hint")
    if isinstance(hint, dict):
        return {
            "chart_source": str(hint.get("source_type") or "operator_hint"),
            "chart_version": _string_or_none(hint.get("chart_version")) or release.chart_version,
            "repo_name": _string_or_none(hint.get("repo_name")),
            "repo_url": _string_or_none(hint.get("repo_url")),
            "credential_secret_ref": _string_or_none(hint.get("credential_secret_ref")),
        }
    return {
        "chart_source": "observed",
        "chart_version": release.chart_version,
        "repo_name": None,
        "repo_url": None,
        "credential_secret_ref": None,
    }


def _string_or_none(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _is_installable_chart_ref(value: str) -> bool:
    return (
        "/" in value
        or value.startswith("oci://")
        or value.startswith("./")
        or value.startswith("../")
        or value.endswith(".tgz")
    )


def _manifest_filename(kind: str, name: str) -> str:
    return f"{kind.lower()}-{_safe_name(name)}.yaml"


def _raw_reconstruction_items(classification: ClassificationSummary) -> list[ClassifiedResource]:
    items = list(classification.raw_k8s)
    seen = {
        (item.resource.kind, item.resource.namespace, item.resource.name)
        for item in items
    }
    for item in classification.helm_managed:
        key = (item.resource.kind, item.resource.namespace, item.resource.name)
        if item.resource.kind == "Ingress" and key not in seen:
            items.append(item)
            seen.add(key)
    return items


def _generated_resource_name(kind: str, name: str) -> str:
    if kind != "Ingress":
        return name
    safe_name = _safe_name(name).strip("-.") or "ingress"
    if safe_name.startswith("agent-ai-"):
        return safe_name
    candidate = f"agent-ai-{safe_name}"
    if len(candidate) <= 63:
        return candidate
    digest = hashlib.sha1(safe_name.encode("utf-8")).hexdigest()[:8]
    prefix = "agent-ai-"
    trimmed_length = 63 - len(prefix) - len(digest) - 1
    trimmed = safe_name[:trimmed_length].rstrip("-.") or "ingress"
    return f"{prefix}{trimmed}-{digest}"


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in "-." else "-" for char in value.lower())


def _resource_evidence(inventory: NormalizedInventory, entity_key: str) -> str:
    return f"{inventory.source}:{inventory.snapshot_id}:{entity_key}"
