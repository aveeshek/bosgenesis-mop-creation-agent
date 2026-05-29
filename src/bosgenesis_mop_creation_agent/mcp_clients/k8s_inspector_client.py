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

    @classmethod
    def from_settings(
        cls,
        settings: EndpointSettings,
        transport: McpTransport | None = None,
    ) -> "K8sInspectorClient":
        return cls(
            BaseMcpClient(
                endpoint_url=settings.endpoint,
                enabled=settings.enabled,
                allowed_tools=K8S_READ_TOOLS,
                timeout_seconds=settings.timeout_seconds,
                transport=transport or StreamableHttpMcpTransport(settings.host_header),
                source_name="k8s_inspector_mcp",
            )
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
        return payload, warnings
