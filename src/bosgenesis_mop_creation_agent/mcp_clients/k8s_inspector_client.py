from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bosgenesis_mop_creation_agent.config.settings import EndpointSettings
from bosgenesis_mop_creation_agent.mcp_clients.base import (
    BaseMcpClient,
    McpClientError,
    McpTransport,
    StreamableHttpMcpTransport,
)


K8S_READ_TOOLS = {
    "k8s_get_namespace",
    "k8s_set_namespace",
    "k8s_get_resource",
    "k8s_namespace_summary",
    "k8s_list_pods",
    "k8s_list_deployments",
    "k8s_list_statefulsets",
    "k8s_list_daemonsets",
    "k8s_list_services",
    "k8s_list_ingresses",
    "k8s_list_pvcs",
    "k8s_list_configmaps",
    "k8s_list_jobs",
    "k8s_list_cronjobs",
    "k8s_list_events",
}


@dataclass
class K8sInspectorClient:
    base: BaseMcpClient
    detail_enrichment_kinds: set[str] | None = None

    @classmethod
    def from_settings(
        cls,
        settings: EndpointSettings,
        transport: McpTransport | None = None,
    ) -> "K8sInspectorClient":
        return cls(
            base=BaseMcpClient(
                endpoint_url=settings.endpoint,
                enabled=settings.enabled,
                allowed_tools=K8S_READ_TOOLS,
                timeout_seconds=settings.timeout_seconds,
                transport=transport or StreamableHttpMcpTransport(settings.host_header),
                source_name="k8s_inspector_mcp",
            ),
            detail_enrichment_kinds=set(getattr(settings, "detail_enrichment_kinds", []) or []),
        )

    def collect(self, namespace: str, correlation_id: str) -> tuple[dict[str, Any], list[str]]:
        payload: dict[str, Any] = {}
        warnings: list[str] = []
        tool_map = {
            "namespace_summary": "k8s_namespace_summary",
            "pods": "k8s_list_pods",
            "deployments": "k8s_list_deployments",
            "statefulsets": "k8s_list_statefulsets",
            "daemonsets": "k8s_list_daemonsets",
            "services": "k8s_list_services",
            "ingresses": "k8s_list_ingresses",
            "pvcs": "k8s_list_pvcs",
            "configmaps": "k8s_list_configmaps",
            "jobs": "k8s_list_jobs",
            "cronjobs": "k8s_list_cronjobs",
            "events": "k8s_list_events",
        }
        try:
            available_tools = self.base.available_tools()
        except McpClientError as exc:
            return {}, [f"k8s_mcp_tools_list_failed: {exc}"]
        if "k8s_set_namespace" in available_tools:
            try:
                payload["namespace_context"] = self.base.call_tool(
                    "k8s_set_namespace",
                    {
                        "namespace": namespace,
                        "actor": "bosgenesis-mop-creation-agent",
                    },
                )
            except McpClientError as exc:
                warnings.append(f"k8s_mcp_k8s_set_namespace_failed: {exc}")
        for key, tool_name in tool_map.items():
            if tool_name not in available_tools:
                continue
            try:
                payload[key] = self.base.call_tool(
                    tool_name,
                    {
                        "namespace": namespace,
                        "actor": "bosgenesis-mop-creation-agent",
                        "correlation_id": correlation_id,
                    },
                )
            except McpClientError as exc:
                warnings.append(f"k8s_mcp_{tool_name}_failed: {exc}")
        if "k8s_get_resource" not in available_tools:
            if self._has_detail_candidates(payload):
                warnings.append("k8s_mcp_detail_enrichment_unavailable:k8s_get_resource_not_advertised")
        else:
            detail_warnings = self._enrich_resource_details(
                payload=payload,
                namespace=namespace,
                correlation_id=correlation_id,
            )
            warnings.extend(detail_warnings)
        return payload, warnings

    def _has_detail_candidates(self, payload: dict[str, Any]) -> bool:
        candidate_keys = {
            "deployments",
            "statefulsets",
            "daemonsets",
            "services",
            "ingresses",
            "pvcs",
            "configmaps",
            "jobs",
            "cronjobs",
        }
        return any(_items(payload.get(key)) for key in candidate_keys)

    def _enrich_resource_details(
        self,
        *,
        payload: dict[str, Any],
        namespace: str,
        correlation_id: str,
    ) -> list[str]:
        warnings: list[str] = []
        payload_kind_map = {
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
        allowed_kinds = self.detail_enrichment_kinds or set(payload_kind_map.values())
        for payload_key, kind in payload_kind_map.items():
            if kind not in allowed_kinds:
                continue
            items = _items(payload.get(payload_key))
            if not items:
                continue
            enriched_items = []
            for item in items:
                name = _name(item)
                if not name:
                    enriched_items.append(item)
                    continue
                try:
                    detail = self.base.call_tool(
                        "k8s_get_resource",
                        {
                            "namespace": namespace,
                            "kind": kind,
                            "name": name,
                            "actor": "bosgenesis-mop-creation-agent",
                            "correlation_id": correlation_id,
                        },
                    )
                except McpClientError as exc:
                    warnings.append(f"k8s_mcp_k8s_get_resource_{kind}_{name}_failed: {exc}")
                    enriched_items.append(item)
                    continue
                resource = detail.get("resource") if isinstance(detail, dict) else None
                status = detail.get("status") if isinstance(detail, dict) else None
                if status == "ok" and isinstance(resource, dict):
                    enriched_items.append(resource)
                elif status == "denied":
                    message = detail.get("message") or detail.get("error") or "policy_denied"
                    warnings.append(f"k8s_mcp_k8s_get_resource_{kind}_{name}_denied: {message}")
                    enriched_items.append(item)
                else:
                    warnings.append(f"k8s_mcp_k8s_get_resource_{kind}_{name}_empty")
                    enriched_items.append(item)
            payload[payload_key] = {"items": enriched_items}
        return warnings


def _items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("items", "resources", "data", "output", "result"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _name(item: dict[str, Any]) -> str | None:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    value = item.get("name") or item.get("resource_name") or metadata.get("name")
    return str(value) if value else None
