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


HELM_READ_TOOLS = {
    "helm_list_releases",
    "helm_release_status",
    "helm_release_history",
    "helm_get_values",
    "helm_get_manifest",
    "helm_repo_list",
}


@dataclass
class HelmManagerClient:
    base: BaseMcpClient

    @classmethod
    def from_settings(
        cls,
        settings: EndpointSettings,
        transport: McpTransport | None = None,
    ) -> "HelmManagerClient":
        return cls(
            BaseMcpClient(
                endpoint_url=settings.endpoint,
                enabled=settings.enabled,
                allowed_tools=HELM_READ_TOOLS,
                timeout_seconds=settings.timeout_seconds,
                transport=transport or StreamableHttpMcpTransport(settings.host_header),
                source_name="helm_manager_mcp",
            )
        )

    def collect(self, namespace: str, correlation_id: str) -> tuple[dict[str, Any], list[str]]:
        warnings: list[str] = []
        try:
            available_tools = self.base.available_tools()
        except McpClientError as exc:
            return {}, [f"helm_mcp_tools_list_failed: {exc}"]
        if "helm_list_releases" not in available_tools:
            return {}, []
        try:
            releases_payload = self.base.call_tool(
                "helm_list_releases",
                {
                    "namespace": namespace,
                    "actor": "bosgenesis-mop-creation-agent",
                    "correlation_id": correlation_id,
                },
            )
        except McpClientError as exc:
            return {}, [f"helm_mcp_helm_list_releases_failed: {exc}"]

        releases = _items(releases_payload)
        enriched: list[dict[str, Any]] = []
        for release in releases:
            release_name = release.get("name") or release.get("release_name")
            if not release_name:
                continue
            bundle: dict[str, Any] = {"release": release}
            for output_key, tool_name in (
                ("status", "helm_release_status"),
                ("history", "helm_release_history"),
                ("values", "helm_get_values"),
                ("manifest", "helm_get_manifest"),
            ):
                if tool_name not in available_tools:
                    continue
                try:
                    bundle[output_key] = self.base.call_tool(
                        tool_name,
                        {
                            "namespace": namespace,
                            "release_name": str(release_name),
                            "actor": "bosgenesis-mop-creation-agent",
                            "correlation_id": correlation_id,
                        },
                    )
                except McpClientError as exc:
                    warnings.append(f"helm_mcp_{tool_name}_{release_name}_failed: {exc}")
            enriched.append(bundle)

        repo_list = {}
        if "helm_repo_list" in available_tools:
            try:
                repo_list = self.base.call_tool(
                    "helm_repo_list",
                    {"actor": "bosgenesis-mop-creation-agent", "correlation_id": correlation_id},
                )
            except McpClientError as exc:
                warnings.append(f"helm_mcp_helm_repo_list_failed: {exc}")

        return {"releases": enriched, "repo_list": repo_list}, warnings


def _items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("releases", "items", "data", "output", "result"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []
