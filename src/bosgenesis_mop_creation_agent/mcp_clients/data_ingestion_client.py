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


DATA_INGESTION_READ_TOOLS = {
    "data_ingestion_health",
    "data_ingestion_latest_scan",
}


@dataclass
class DataIngestionClient:
    base: BaseMcpClient

    @classmethod
    def from_settings(
        cls,
        settings: EndpointSettings,
        transport: McpTransport | None = None,
    ) -> "DataIngestionClient":
        return cls(
            BaseMcpClient(
                endpoint_url=settings.endpoint,
                enabled=settings.enabled,
                allowed_tools=DATA_INGESTION_READ_TOOLS,
                timeout_seconds=settings.timeout_seconds,
                transport=transport or StreamableHttpMcpTransport(settings.host_header),
                source_name="data_ingestion_mcp",
            )
        )

    def collect(self, correlation_id: str) -> tuple[dict[str, Any], list[str]]:
        payload: dict[str, Any] = {}
        warnings: list[str] = []
        try:
            available_tools = self.base.available_tools()
        except McpClientError as exc:
            return {}, [f"data_ingestion_mcp_tools_list_failed: {exc}"]
        for key, tool_name in (
            ("health", "data_ingestion_health"),
            ("latest_scan", "data_ingestion_latest_scan"),
        ):
            if tool_name not in available_tools:
                continue
            try:
                payload[key] = self.base.call_tool(
                    tool_name,
                    {"actor": "bosgenesis-mop-creation-agent", "correlation_id": correlation_id},
                )
            except McpClientError as exc:
                warnings.append(f"data_ingestion_mcp_{tool_name}_failed: {exc}")
        return payload, warnings
