from __future__ import annotations

from typing import Any

from bosgenesis_mop_creation_agent.classification.models import ClassificationSummary
from bosgenesis_mop_creation_agent.models.requests import HelmChartHint
from bosgenesis_mop_creation_agent.sources.snapshot_models import (
    InventoryHelmRelease,
    NormalizedInventory,
)


def apply_helm_chart_hints(
    *,
    inventory: NormalizedInventory | None,
    classification: ClassificationSummary | None,
    hints: list[HelmChartHint],
) -> NormalizedInventory | None:
    """Apply operator-provided chart evidence before reconstruction planning."""
    if inventory is None or not hints:
        return inventory

    release_names = {
        item.helm_release_name
        for item in (classification.helm_managed if classification else [])
        if item.helm_release_name
    }
    release_names.update(release.release_name for release in inventory.helm_releases)

    releases = {release.release_name: release for release in inventory.helm_releases}
    for hint in hints:
        if hint.release_name not in release_names:
            continue
        existing = releases.get(hint.release_name)
        releases[hint.release_name] = _apply_hint(
            existing=existing,
            hint=hint,
            namespace=inventory.namespace,
        )

    return inventory.model_copy(
        update={
            "helm_releases": sorted(releases.values(), key=lambda item: item.release_name),
        }
    )


def _apply_hint(
    *,
    existing: InventoryHelmRelease | None,
    hint: HelmChartHint,
    namespace: str,
) -> InventoryHelmRelease:
    chart_ref = _chart_ref(hint)
    hint_payload = hint.model_dump(mode="json", exclude_none=True)
    hint_values = hint.values_overrides or {}
    normalized_payload: dict[str, Any] = {
        "operator_chart_hint": hint_payload,
    }
    if hint_values:
        normalized_payload["values"] = hint_values

    if existing is None:
        return InventoryHelmRelease(
            release_name=hint.release_name,
            namespace=namespace,
            chart_name=chart_ref,
            chart_version=hint.chart_version,
            status="operator_hint",
            entity_key=f"HelmRelease:{namespace}:{hint.release_name}",
            normalized_payload=normalized_payload,
        )

    merged_payload = {
        **existing.normalized_payload,
        "operator_chart_hint": hint_payload,
    }
    if hint_values and "values" not in merged_payload:
        merged_payload["values"] = hint_values
    return existing.model_copy(
        update={
            "chart_name": existing.chart_name or chart_ref,
            "chart_version": existing.chart_version or hint.chart_version,
            "normalized_payload": merged_payload,
        }
    )


def _chart_ref(hint: HelmChartHint) -> str | None:
    if hint.chart_ref:
        return hint.chart_ref
    if hint.repo_name and hint.chart_name:
        return f"{hint.repo_name}/{hint.chart_name}"
    if hint.chart_name:
        return hint.chart_name
    return None
