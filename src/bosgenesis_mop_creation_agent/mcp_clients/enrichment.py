from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from bosgenesis_mop_creation_agent.mcp_clients.data_ingestion_client import DataIngestionClient
from bosgenesis_mop_creation_agent.mcp_clients.helm_manager_client import HelmManagerClient
from bosgenesis_mop_creation_agent.mcp_clients.k8s_inspector_client import K8sInspectorClient
from bosgenesis_mop_creation_agent.sources.snapshot_models import (
    InventoryHelmRelease,
    InventoryResource,
    NormalizedInventory,
)


@dataclass(frozen=True)
class McpEnrichmentResult:
    inventory: NormalizedInventory | None
    warnings: list[str]
    sources_attempted: list[str]
    evidence: dict[str, Any]


@dataclass
class McpEnrichmentService:
    k8s_client: K8sInspectorClient
    helm_client: HelmManagerClient
    data_ingestion_client: DataIngestionClient | None = None

    def enrich(
        self,
        *,
        namespace: str,
        correlation_id: str,
        snapshot_inventory: NormalizedInventory | None,
    ) -> McpEnrichmentResult:
        warnings: list[str] = []
        sources_attempted: list[str] = []
        evidence: dict[str, Any] = {}

        k8s_payload, k8s_warnings = self.k8s_client.collect(namespace, correlation_id)
        sources_attempted.append("k8s_inspector_mcp")
        warnings.extend(k8s_warnings)
        evidence["k8s_inspector_mcp"] = k8s_payload

        helm_payload, helm_warnings = self.helm_client.collect(namespace, correlation_id)
        sources_attempted.append("helm_manager_mcp")
        warnings.extend(helm_warnings)
        evidence["helm_manager_mcp"] = helm_payload

        if self.data_ingestion_client is not None:
            data_payload, data_warnings = self.data_ingestion_client.collect(correlation_id)
            sources_attempted.append("data_ingestion_mcp")
            warnings.extend(data_warnings)
            evidence["data_ingestion_mcp"] = data_payload

        live_inventory = _inventory_from_mcp(namespace, k8s_payload, helm_payload)
        merged = merge_inventory(snapshot_inventory, live_inventory)
        return McpEnrichmentResult(
            inventory=merged,
            warnings=warnings,
            sources_attempted=sources_attempted,
            evidence=evidence,
        )


def merge_inventory(
    snapshot_inventory: NormalizedInventory | None,
    live_inventory: NormalizedInventory | None,
) -> NormalizedInventory | None:
    if snapshot_inventory is None:
        return live_inventory
    if live_inventory is None:
        return snapshot_inventory

    resources = {
        (item.kind, item.namespace, item.name): item for item in snapshot_inventory.resources
    }
    for item in live_inventory.resources:
        resources[(item.kind, item.namespace, item.name)] = item

    releases = {
        item.release_name: item for item in snapshot_inventory.helm_releases
    }
    for item in live_inventory.helm_releases:
        existing = releases.get(item.release_name)
        releases[item.release_name] = _merge_release(existing, item)

    return NormalizedInventory(
        source=f"{snapshot_inventory.source}+{live_inventory.source}",
        namespace=snapshot_inventory.namespace,
        snapshot_id=snapshot_inventory.snapshot_id,
        run_id=snapshot_inventory.run_id,
        correlation_id=snapshot_inventory.correlation_id,
        observed_at=live_inventory.observed_at or snapshot_inventory.observed_at,
        resources=sorted(resources.values(), key=lambda item: (item.kind, item.name)),
        helm_releases=sorted(releases.values(), key=lambda item: item.release_name),
        warnings=[*snapshot_inventory.warnings, *live_inventory.warnings],
    )


def _inventory_from_mcp(
    namespace: str,
    k8s_payload: dict[str, Any],
    helm_payload: dict[str, Any],
) -> NormalizedInventory | None:
    resources = _resources_from_k8s_payload(namespace, k8s_payload)
    releases = _releases_from_helm_payload(namespace, helm_payload)
    if not resources and not releases:
        return None
    snapshot_id = f"mcp-live-{uuid4()}"
    return NormalizedInventory(
        source="mcp_live",
        namespace=namespace,
        snapshot_id=snapshot_id,
        run_id=snapshot_id,
        observed_at=datetime.now(UTC),
        resources=resources,
        helm_releases=releases,
    )


def _resources_from_k8s_payload(namespace: str, payload: dict[str, Any]) -> list[InventoryResource]:
    mapping = {
        "pods": "Pod",
        "deployments": "Deployment",
        "statefulsets": "StatefulSet",
        "daemonsets": "DaemonSet",
        "services": "Service",
        "ingresses": "Ingress",
        "pvcs": "PersistentVolumeClaim",
        "configmaps": "ConfigMap",
        "jobs": "Job",
        "cronjobs": "CronJob",
    }
    resources: list[InventoryResource] = []
    for payload_key, kind in mapping.items():
        for item in _items(payload.get(payload_key)):
            name = _name(item)
            if not name:
                continue
            resources.append(
                InventoryResource(
                    kind=kind,
                    name=name,
                    namespace=str(item.get("namespace") or namespace),
                    source="k8s_inspector_mcp",
                    entity_key=str(item.get("entity_key") or f"{kind}:{namespace}:{name}"),
                    status_summary=_status(item),
                    normalized_payload=item,
                )
            )
    return resources


def _releases_from_helm_payload(namespace: str, payload: dict[str, Any]) -> list[InventoryHelmRelease]:
    releases: list[InventoryHelmRelease] = []
    for bundle in _items(payload.get("releases")):
        release_payload = bundle.get("release") if isinstance(bundle.get("release"), dict) else bundle
        release_name = (
            release_payload.get("name")
            or release_payload.get("release_name")
            or bundle.get("name")
            or bundle.get("release_name")
        )
        if not release_name:
            continue
        status_payload = bundle.get("status") if isinstance(bundle.get("status"), dict) else {}
        releases.append(
            InventoryHelmRelease(
                release_name=str(release_name),
                namespace=str(release_payload.get("namespace") or namespace),
                chart_name=_first_present([release_payload, status_payload], ["chart", "chart_name"]),
                chart_version=_first_present([release_payload, status_payload], ["chart_version"]),
                app_version=_first_present([release_payload, status_payload], ["app_version"]),
                revision=_optional_int(
                    _first_present([release_payload, status_payload], ["revision"])
                ),
                status=_first_present([release_payload, status_payload], ["status"]),
                entity_key=f"HelmRelease:{namespace}:{release_name}",
                normalized_payload={
                    "release": release_payload,
                    "status": status_payload,
                    "history": bundle.get("history"),
                    "manifest": bundle.get("manifest"),
                    "values_present": "values" in bundle,
                    "manifest_present": "manifest" in bundle,
                },
            )
        )
    return releases


def _merge_release(
    existing: InventoryHelmRelease | None,
    live: InventoryHelmRelease,
) -> InventoryHelmRelease:
    if existing is None:
        return live
    return existing.model_copy(
        update={
            "chart_name": live.chart_name or existing.chart_name,
            "chart_version": live.chart_version or existing.chart_version,
            "app_version": live.app_version or existing.app_version,
            "revision": live.revision or existing.revision,
            "status": live.status or existing.status,
            "normalized_payload": {
                **existing.normalized_payload,
                "mcp_live": live.normalized_payload,
            },
        }
    )


def _items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("items", "resources", "pods", "deployments", "services", "releases", "data", "output", "result"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _name(item: dict[str, Any]) -> str | None:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    return item.get("name") or item.get("resource_name") or metadata.get("name")


def _status(item: dict[str, Any]) -> str | None:
    for key in ("status_summary", "phase", "status"):
        value = item.get(key)
        if isinstance(value, str):
            return value
    return None


def _first_present(payloads: list[dict[str, Any]], keys: list[str]) -> str | None:
    for payload in payloads:
        for key in keys:
            value = payload.get(key)
            if value is not None:
                return str(value)
    return None


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
