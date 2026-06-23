from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

import yaml

from bosgenesis_mop_creation_agent.sources.snapshot_models import InventoryResource


RUNTIME_METADATA_FIELDS = {
    "creationTimestamp",
    "deletionGracePeriodSeconds",
    "deletionTimestamp",
    "finalizers",
    "generation",
    "managedFields",
    "ownerReferences",
    "resourceVersion",
    "selfLink",
    "uid",
}

RUNTIME_ANNOTATIONS = {
    "kubectl.kubernetes.io/last-applied-configuration",
    "deployment.kubernetes.io/revision",
    "control-plane.alpha.kubernetes.io/leader",
}

PVC_RUNTIME_ANNOTATIONS = {
    "pv.kubernetes.io/bind-completed",
    "pv.kubernetes.io/bound-by-controller",
    "volume.beta.kubernetes.io/storage-provisioner",
    "volume.kubernetes.io/selected-node",
    "volume.kubernetes.io/storage-provisioner",
}

SERVICE_RUNTIME_FIELDS = {
    "clusterIP",
    "clusterIPs",
    "healthCheckNodePort",
    "ipFamilies",
    "ipFamilyPolicy",
    "sessionAffinityConfig",
}

PVC_RUNTIME_FIELDS = {"volumeName"}

SENSITIVE_KEY_PARTS = (
    "api_key",
    "apikey",
    "auth",
    "credential",
    "passwd",
    "password",
    "privatekey",
    "secret",
    "token",
)

REDACTED = "<REDACTED_PROVIDE_APPROVED_VALUE>"


API_VERSION_BY_KIND = {
    "ConfigMap": "v1",
    "CronJob": "batch/v1",
    "DaemonSet": "apps/v1",
    "Deployment": "apps/v1",
    "Ingress": "networking.k8s.io/v1",
    "Job": "batch/v1",
    "PersistentVolumeClaim": "v1",
    "Service": "v1",
    "StatefulSet": "apps/v1",
}


def normalize_manifest(
    resource: InventoryResource,
    target_namespace: str,
    *,
    generated_name: str | None = None,
    service_name_rewrites: Mapping[str, str] | None = None,
) -> tuple[dict[str, Any], list[str]]:
    manifest = _manifest_payload(resource)
    warnings: list[str] = []

    if not manifest:
        warnings.append("source_manifest_missing_minimal_manifest_generated")
        manifest = {}

    normalized = deepcopy(manifest)
    normalized["apiVersion"] = normalized.get("apiVersion") or resource.api_version or _api_version(resource.kind)
    normalized["kind"] = normalized.get("kind") or resource.kind
    metadata = normalized.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    source_name = metadata.get("name") or resource.name
    metadata["name"] = generated_name or source_name
    metadata["namespace"] = target_namespace
    if generated_name and generated_name != source_name:
        annotations = metadata.get("annotations")
        if not isinstance(annotations, dict):
            annotations = {}
        annotations.setdefault("bosgenesis.io/generated-by", "bosgenesis-mop-creation-agent")
        annotations.setdefault("bosgenesis.io/original-name", str(source_name))
        metadata["annotations"] = annotations
    _remove_runtime_metadata(metadata)
    _remove_kind_runtime_metadata(normalized.get("kind"), metadata)
    normalized["metadata"] = metadata

    normalized.pop("status", None)
    _remove_kind_runtime_fields(normalized)
    if normalized.get("kind") == "Ingress" and service_name_rewrites:
        warnings.extend(_rewrite_ingress_backend_services(normalized, service_name_rewrites))
    _redact_sensitive_values(normalized)
    if _requires_spec(resource.kind) and not isinstance(normalized.get("spec"), dict):
        warnings.append("source_spec_missing_manifest_requires_human_completion")

    return normalized, warnings


def dump_manifest(manifest: dict[str, Any]) -> str:
    return yaml.safe_dump(manifest, sort_keys=False, explicit_start=True)


def _manifest_payload(resource: InventoryResource) -> dict[str, Any]:
    payload = resource.normalized_payload
    if _looks_like_manifest(payload):
        return payload
    for key in ("manifest", "resource", "object", "raw", "normalized"):
        value = payload.get(key)
        if isinstance(value, dict) and _looks_like_manifest(value):
            return value
    return {}


def _looks_like_manifest(payload: dict[str, Any]) -> bool:
    return any(key in payload for key in ("apiVersion", "kind", "metadata", "spec", "data"))


def _api_version(kind: str) -> str:
    return API_VERSION_BY_KIND.get(kind, "v1")


def _remove_runtime_metadata(metadata: dict[str, Any]) -> None:
    for field in RUNTIME_METADATA_FIELDS:
        metadata.pop(field, None)
    annotations = metadata.get("annotations")
    if isinstance(annotations, dict):
        for key in RUNTIME_ANNOTATIONS:
            annotations.pop(key, None)
        if not annotations:
            metadata.pop("annotations", None)


def _remove_kind_runtime_metadata(kind: str | None, metadata: dict[str, Any]) -> None:
    if kind != "PersistentVolumeClaim":
        return
    annotations = metadata.get("annotations")
    if not isinstance(annotations, dict):
        return
    for key in PVC_RUNTIME_ANNOTATIONS:
        annotations.pop(key, None)
    if not annotations:
        metadata.pop("annotations", None)


def _remove_kind_runtime_fields(manifest: dict[str, Any]) -> None:
    spec = manifest.get("spec")
    if not isinstance(spec, dict):
        return
    if manifest.get("kind") == "Service":
        for field in SERVICE_RUNTIME_FIELDS:
            spec.pop(field, None)
    if manifest.get("kind") == "PersistentVolumeClaim":
        for field in PVC_RUNTIME_FIELDS:
            spec.pop(field, None)


def _rewrite_ingress_backend_services(
    manifest: dict[str, Any],
    service_name_rewrites: Mapping[str, str],
) -> list[str]:
    warnings: list[str] = []
    spec = manifest.get("spec")
    if not isinstance(spec, dict):
        return warnings

    default_backend = spec.get("defaultBackend")
    if isinstance(default_backend, dict):
        warnings.extend(_rewrite_backend_service(default_backend, service_name_rewrites))

    for rule in spec.get("rules") or []:
        if not isinstance(rule, dict):
            continue
        http = rule.get("http")
        if not isinstance(http, dict):
            continue
        for path in http.get("paths") or []:
            if not isinstance(path, dict):
                continue
            backend = path.get("backend")
            if isinstance(backend, dict):
                warnings.extend(_rewrite_backend_service(backend, service_name_rewrites))
    return warnings


def _rewrite_backend_service(
    backend: dict[str, Any],
    service_name_rewrites: Mapping[str, str],
) -> list[str]:
    service = backend.get("service")
    if not isinstance(service, dict):
        return []
    current_name = service.get("name")
    if not isinstance(current_name, str):
        return []
    rewritten_name = service_name_rewrites.get(current_name)
    if not rewritten_name or rewritten_name == current_name:
        return []
    service["name"] = rewritten_name
    return [f"ingress_backend_service_rewritten:{current_name}->{rewritten_name}"]


def _requires_spec(kind: str) -> bool:
    return kind in {
        "CronJob",
        "DaemonSet",
        "Deployment",
        "Ingress",
        "Job",
        "PersistentVolumeClaim",
        "Service",
        "StatefulSet",
    }


def _redact_sensitive_values(value: Any, key_hint: str = "") -> Any:
    if isinstance(value, dict):
        for key, nested in list(value.items()):
            key_text = str(key)
            if _is_sensitive_key(key_text):
                value[key] = REDACTED
            else:
                value[key] = _redact_sensitive_values(nested, key_text)
        return value
    if isinstance(value, list):
        for index, item in enumerate(value):
            if _is_env_var(item):
                env_name = str(item.get("name", ""))
                if _is_sensitive_key(env_name) and "value" in item:
                    item["value"] = REDACTED
            value[index] = _redact_sensitive_values(item, key_hint)
        return value
    return value


def _is_env_var(value: Any) -> bool:
    return isinstance(value, dict) and isinstance(value.get("name"), str)


def _is_sensitive_key(key: str) -> bool:
    key_lower = key.lower().replace("-", "_")
    return any(part in key_lower for part in SENSITIVE_KEY_PARTS)
