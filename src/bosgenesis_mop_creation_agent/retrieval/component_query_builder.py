from __future__ import annotations

from typing import Any

from bosgenesis_mop_creation_agent.classification.models import ClassificationSummary
from bosgenesis_mop_creation_agent.retrieval.models import ComponentIdentity, ComponentQuery
from bosgenesis_mop_creation_agent.sources.snapshot_models import (
    InventoryHelmRelease,
    InventoryResource,
    NormalizedInventory,
)


def build_component_queries(
    inventory: NormalizedInventory | None,
    classification: ClassificationSummary | None,
) -> list[ComponentQuery]:
    if inventory is None:
        return []

    queries: list[ComponentQuery] = []
    seen: set[str] = set()

    for release in inventory.helm_releases:
        query = _helm_query(release)
        if query.query_id not in seen:
            queries.append(query)
            seen.add(query.query_id)

    classified_resources = classification.resources if classification else []
    classified_keys = {
        f"{item.resource.kind}/{item.resource.namespace}/{item.resource.name}"
        for item in classified_resources
    }
    for item in classified_resources:
        query = _resource_query(item.resource, item.helm_release_name)
        if query.query_id not in seen:
            queries.append(query)
            seen.add(query.query_id)

    for resource in inventory.resources:
        resource_key = f"{resource.kind}/{resource.namespace}/{resource.name}"
        if resource_key in classified_keys:
            continue
        query = _resource_query(resource, None)
        if query.query_id not in seen:
            queries.append(query)
            seen.add(query.query_id)

    return queries


def _helm_query(release: InventoryHelmRelease) -> ComponentQuery:
    labels = _labels(release.normalized_payload)
    component = ComponentIdentity(
        kind="HelmRelease",
        name=release.release_name,
        namespace=release.namespace,
        labels=labels,
        helm_release_name=release.release_name,
        helm_chart_name=release.chart_name,
        helm_chart_version=release.chart_version,
        image_repositories=_image_repositories(release.normalized_payload),
    )
    terms = _compact(
        [
            "HelmRelease",
            release.release_name,
            release.chart_name,
            release.chart_version,
            labels.get("app.kubernetes.io/name"),
            labels.get("app.kubernetes.io/instance"),
        ]
    )
    return ComponentQuery(
        query_id=f"helm:{release.release_name}",
        component=component,
        query_text=" ".join(terms),
        exact_terms=terms,
    )


def _resource_query(resource: InventoryResource, helm_release_name: str | None) -> ComponentQuery:
    labels = _labels(resource.normalized_payload)
    annotations = _annotations(resource.normalized_payload)
    helm_release = (
        helm_release_name
        or annotations.get("meta.helm.sh/release-name")
        or labels.get("app.kubernetes.io/instance")
    )
    component = ComponentIdentity(
        kind=resource.kind,
        name=resource.name,
        namespace=resource.namespace,
        labels=labels,
        helm_release_name=helm_release,
        image_repositories=_image_repositories(resource.normalized_payload),
        service_names=_service_names(resource),
        ingress_hosts=_ingress_hosts(resource.normalized_payload),
    )
    terms = _compact(
        [
            resource.kind,
            resource.name,
            helm_release,
            labels.get("app.kubernetes.io/name"),
            labels.get("app.kubernetes.io/component"),
            labels.get("app"),
            *_image_repositories(resource.normalized_payload),
            *_ingress_hosts(resource.normalized_payload),
        ]
    )
    return ComponentQuery(
        query_id=f"resource:{resource.kind}:{resource.name}",
        component=component,
        query_text=" ".join(terms),
        exact_terms=terms,
    )


def _labels(payload: dict[str, Any]) -> dict[str, str]:
    labels = (((payload or {}).get("metadata") or {}).get("labels") or {})
    return {str(key): str(value) for key, value in labels.items() if value is not None}


def _annotations(payload: dict[str, Any]) -> dict[str, str]:
    annotations = (((payload or {}).get("metadata") or {}).get("annotations") or {})
    return {str(key): str(value) for key, value in annotations.items() if value is not None}


def _image_repositories(payload: Any) -> list[str]:
    images: list[str] = []
    _collect_images(payload, images)
    normalized = []
    for image in images:
        repo = image.split("@", 1)[0].rsplit(":", 1)[0] if "/" in image else image.split(":", 1)[0]
        if repo and repo not in normalized:
            normalized.append(repo)
    return normalized


def _collect_images(value: Any, images: list[str]) -> None:
    if isinstance(value, dict):
        image = value.get("image")
        if isinstance(image, str) and image not in images:
            images.append(image)
        for nested in value.values():
            _collect_images(nested, images)
    elif isinstance(value, list):
        for item in value:
            _collect_images(item, images)


def _service_names(resource: InventoryResource) -> list[str]:
    return [resource.name] if resource.kind == "Service" else []


def _ingress_hosts(payload: dict[str, Any]) -> list[str]:
    hosts: list[str] = []
    for rule in (((payload or {}).get("spec") or {}).get("rules") or []):
        if isinstance(rule, dict) and rule.get("host"):
            hosts.append(str(rule["host"]))
    return hosts


def _compact(values: list[str | None]) -> list[str]:
    compacted: list[str] = []
    for value in values:
        if value and value not in compacted:
            compacted.append(value)
    return compacted

