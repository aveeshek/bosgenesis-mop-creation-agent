from __future__ import annotations

from typing import Any

import yaml

from bosgenesis_mop_creation_agent.classification.models import (
    ClassificationSummary,
    ClassifiedResource,
    ResourceCategory,
)
from bosgenesis_mop_creation_agent.sources.snapshot_models import (
    InventoryResource,
    NormalizedInventory,
)


BLOCKED_KINDS = {
    "Secret",
    "ServiceAccount",
    "Role",
    "RoleBinding",
    "ClusterRole",
    "ClusterRoleBinding",
    "Namespace",
    "Node",
    "PersistentVolume",
    "CustomResourceDefinition",
    "StorageClass",
    "IngressClass",
    "PriorityClass",
    "MutatingWebhookConfiguration",
    "ValidatingWebhookConfiguration",
}

CLUSTER_SCOPED_KINDS = {
    "ClusterRole",
    "ClusterRoleBinding",
    "CustomResourceDefinition",
    "IngressClass",
    "Namespace",
    "Node",
    "PersistentVolume",
    "PriorityClass",
    "StorageClass",
}

RAW_RECONSTRUCTABLE_KINDS = {
    "ConfigMap",
    "CronJob",
    "DaemonSet",
    "Deployment",
    "Ingress",
    "Job",
    "PersistentVolumeClaim",
    "Service",
    "StatefulSet",
}


def classify_inventory(inventory: NormalizedInventory | None) -> ClassificationSummary | None:
    if inventory is None:
        return None

    release_names = {
        release.release_name
        for release in inventory.helm_releases
        if release.namespace == inventory.namespace
    }
    manifest_index = _helm_manifest_index(inventory)
    classified = [
        classify_resource(
            resource,
            source_namespace=inventory.namespace,
            helm_release_names=release_names,
            helm_manifest_index=manifest_index,
        )
        for resource in inventory.resources
    ]
    warnings = _warning_summary(classified)
    return ClassificationSummary(
        namespace=inventory.namespace,
        resources=classified,
        warnings=warnings,
    )


def classify_resource(
    resource: InventoryResource,
    *,
    source_namespace: str,
    helm_release_names: set[str],
    helm_manifest_index: dict[tuple[str, str], str] | None = None,
) -> ClassifiedResource:
    if resource.namespace != source_namespace:
        return _classified(
            resource,
            ResourceCategory.EXCLUDED,
            "outside_source_namespace",
            [f"resource_namespace={resource.namespace}", f"source_namespace={source_namespace}"],
        )

    if resource.kind in BLOCKED_KINDS:
        return _classified(
            resource,
            ResourceCategory.EXCLUDED,
            "blocked_kind",
            [f"kind={resource.kind}"],
        )

    if resource.kind in CLUSTER_SCOPED_KINDS or not resource.namespace:
        return _classified(
            resource,
            ResourceCategory.EXCLUDED,
            "cluster_scoped_or_missing_namespace",
            [f"kind={resource.kind}"],
        )

    manifest_release_name = (helm_manifest_index or {}).get((resource.kind, resource.name))
    if manifest_release_name:
        return _classified(
            resource,
            ResourceCategory.HELM_MANAGED,
            "helm_manifest_membership_detected",
            [
                f"helm_manifest:{manifest_release_name}",
                f"kind={resource.kind}",
                f"name={resource.name}",
            ],
            helm_release_name=manifest_release_name,
        )

    helm_release_name, helm_evidence = _helm_evidence(resource, helm_release_names)
    if helm_release_name:
        return _classified(
            resource,
            ResourceCategory.HELM_MANAGED,
            "helm_metadata_detected",
            helm_evidence,
            helm_release_name=helm_release_name,
        )

    if resource.kind in RAW_RECONSTRUCTABLE_KINDS:
        return _classified(
            resource,
            ResourceCategory.RAW_K8S,
            "supported_namespaced_raw_resource",
            [f"kind={resource.kind}", f"namespace={resource.namespace}"],
        )

    return _classified(
        resource,
        ResourceCategory.WARNING_ONLY,
        "unsupported_namespaced_resource_manual_note",
        [f"kind={resource.kind}", f"namespace={resource.namespace}"],
    )


def _warning_summary(classified: list[ClassifiedResource]) -> list[str]:
    warning_only = [item for item in classified if item.category == ResourceCategory.WARNING_ONLY]
    pod_count = sum(1 for item in warning_only if item.resource.kind == "Pod")
    warnings = []
    if pod_count:
        warnings.append(
            f"manual_review_required:Pod:{pod_count}_runtime_artifacts_skipped"
        )
    warnings.extend(
        (
            f"manual_review_required:{item.resource.kind}/{item.resource.name}:"
            f"{item.reason}"
        )
        for item in warning_only
        if item.resource.kind != "Pod"
    )
    return warnings


def _helm_manifest_index(inventory: NormalizedInventory) -> dict[tuple[str, str], str]:
    index: dict[tuple[str, str], str] = {}
    for release in inventory.helm_releases:
        if release.namespace != inventory.namespace:
            continue
        for document in _helm_manifest_documents(release.normalized_payload):
            kind = document.get("kind")
            metadata = document.get("metadata") if isinstance(document.get("metadata"), dict) else {}
            name = metadata.get("name")
            namespace = metadata.get("namespace") or inventory.namespace
            if (
                isinstance(kind, str)
                and isinstance(name, str)
                and namespace == inventory.namespace
            ):
                index[(kind, name)] = release.release_name
    return index


def _helm_manifest_documents(payload: dict[str, Any]) -> list[dict[str, Any]]:
    manifest_payloads = [
        payload.get("manifest"),
        payload.get("mcp_live", {}).get("manifest")
        if isinstance(payload.get("mcp_live"), dict)
        else None,
    ]
    documents: list[dict[str, Any]] = []
    for manifest_payload in manifest_payloads:
        manifest_text = _manifest_text(manifest_payload)
        if not manifest_text:
            continue
        try:
            for document in yaml.safe_load_all(manifest_text):
                if isinstance(document, dict):
                    documents.append(document)
        except yaml.YAMLError:
            continue
    return documents


def _manifest_text(payload: Any) -> str | None:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for key in ("manifest", "output", "content", "yaml", "text"):
            value = payload.get(key)
            if isinstance(value, str):
                return value
    return None


def _helm_evidence(resource: InventoryResource, helm_release_names: set[str]) -> tuple[str | None, list[str]]:
    metadata = _metadata(resource.normalized_payload)
    labels = _map_value(metadata.get("labels"))
    annotations = _map_value(metadata.get("annotations"))

    release_name = _string_value(annotations.get("meta.helm.sh/release-name"))
    release_namespace = _string_value(annotations.get("meta.helm.sh/release-namespace"))
    managed_by = _string_value(labels.get("app.kubernetes.io/managed-by"))
    evidence: list[str] = []

    if managed_by == "Helm":
        evidence.append("label:app.kubernetes.io/managed-by=Helm")
    if release_name:
        evidence.append(f"annotation:meta.helm.sh/release-name={release_name}")
    if release_namespace:
        evidence.append(f"annotation:meta.helm.sh/release-namespace={release_namespace}")

    if release_name and (not helm_release_names or release_name in helm_release_names):
        return release_name, evidence

    if managed_by == "Helm" and release_name:
        return release_name, evidence

    if managed_by == "Helm" and resource.name in helm_release_names:
        evidence.append(f"release_name_match={resource.name}")
        return resource.name, evidence

    return None, evidence


def _metadata(payload: dict[str, Any]) -> dict[str, Any]:
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        return metadata
    return payload


def _map_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_value(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _classified(
    resource: InventoryResource,
    category: ResourceCategory,
    reason: str,
    evidence: list[str],
    *,
    helm_release_name: str | None = None,
) -> ClassifiedResource:
    return ClassifiedResource(
        resource=resource,
        category=category,
        reason=reason,
        evidence=evidence,
        helm_release_name=helm_release_name,
    )
