from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import timedelta
import json
from typing import Any, Protocol

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from bosgenesis_mop_creation_agent.common.logging import get_logger


logger = get_logger(__name__)


class McpClientError(RuntimeError):
    pass


class McpTransport(Protocol):
    async def list_tools(
        self,
        endpoint_url: str,
        timeout_seconds: float,
    ) -> set[str]:
        """List remote MCP tool names."""

    async def call_tool(
        self,
        endpoint_url: str,
        tool_name: str,
        arguments: dict[str, Any],
        timeout_seconds: float,
    ) -> Any:
        """Call a remote MCP tool."""


@dataclass
class InMemoryMcpTransport:
    responses: dict[str, Any] = field(default_factory=dict)
    calls: list[tuple[str, str, dict[str, Any]]] = field(default_factory=list)
    available_tools: set[str] | None = None

    async def list_tools(
        self,
        endpoint_url: str,
        timeout_seconds: float,
    ) -> set[str]:
        self.calls.append((endpoint_url, "tools/list", {}))
        if self.available_tools is not None:
            return set(self.available_tools)
        return set(self.responses)

    async def call_tool(
        self,
        endpoint_url: str,
        tool_name: str,
        arguments: dict[str, Any],
        timeout_seconds: float,
    ) -> Any:
        self.calls.append((endpoint_url, tool_name, arguments))
        response = self.responses.get(tool_name)
        if isinstance(response, Exception):
            raise response
        return response if response is not None else {}


@dataclass
class StreamableHttpMcpTransport:
    host_header: str | None = None

    async def list_tools(
        self,
        endpoint_url: str,
        timeout_seconds: float,
    ) -> set[str]:
        timeout = timedelta(seconds=timeout_seconds)
        headers = {"Host": self.host_header} if self.host_header else None
        async with streamablehttp_client(
            endpoint_url,
            headers=headers,
            timeout=timeout,
            sse_read_timeout=timeout,
            httpx_client_factory=_create_internal_mcp_http_client,
        ) as (read_stream, write_stream, _get_session_id):
            async with ClientSession(read_stream, write_stream, read_timeout_seconds=timeout) as session:
                await session.initialize()
                result = await session.list_tools()
                return {tool.name for tool in result.tools}

    async def call_tool(
        self,
        endpoint_url: str,
        tool_name: str,
        arguments: dict[str, Any],
        timeout_seconds: float,
    ) -> Any:
        timeout = timedelta(seconds=timeout_seconds)
        headers = {"Host": self.host_header} if self.host_header else None
        async with streamablehttp_client(
            endpoint_url,
            headers=headers,
            timeout=timeout,
            sse_read_timeout=timeout,
            httpx_client_factory=_create_internal_mcp_http_client,
        ) as (read_stream, write_stream, _get_session_id):
            async with ClientSession(read_stream, write_stream, read_timeout_seconds=timeout) as session:
                await session.initialize()
                result = await session.call_tool(
                    tool_name,
                    arguments,
                    read_timeout_seconds=timeout,
                )
                return _unwrap_call_tool_result(result)


@dataclass
class BaseMcpClient:
    endpoint_url: str | None
    enabled: bool
    allowed_tools: set[str]
    timeout_seconds: float = 30
    transport: McpTransport = field(default_factory=StreamableHttpMcpTransport)
    source_name: str = "mcp"

    def available_tools(self) -> set[str]:
        return asyncio.run(self.available_tools_async())

    async def available_tools_async(self) -> set[str]:
        if not self.enabled:
            raise McpClientError(f"{self.source_name}_disabled")
        if not self.endpoint_url:
            raise McpClientError(f"{self.source_name}_endpoint_missing")
        try:
            logger.info(
                "mcp_tools_list_started",
                extra={"mcp_source": self.source_name, "endpoint_url": self.endpoint_url},
            )
            tools = await self.transport.list_tools(self.endpoint_url, self.timeout_seconds)
            allowed = tools.intersection(self.allowed_tools)
            logger.info(
                "mcp_tools_list_completed",
                extra={
                    "mcp_source": self.source_name,
                    "available_tool_count": len(tools),
                    "allowed_tool_count": len(allowed),
                },
            )
            return allowed
        except Exception as exc:
            logger.warning(
                "mcp_tools_list_failed",
                extra={"mcp_source": self.source_name, "error": str(exc)},
            )
            raise McpClientError(str(exc)) from exc

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        return asyncio.run(self.call_tool_async(tool_name, arguments))

    async def call_tool_async(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        if not self.enabled:
            raise McpClientError(f"{self.source_name}_disabled")
        if not self.endpoint_url:
            raise McpClientError(f"{self.source_name}_endpoint_missing")
        if tool_name not in self.allowed_tools:
            raise McpClientError(f"{self.source_name}_tool_not_allowed: {tool_name}")
        try:
            logger.info(
                "mcp_call_started",
                extra={
                    "mcp_source": self.source_name,
                    "tool_name": tool_name,
                    "endpoint_url": self.endpoint_url,
                },
            )
            result = await self.transport.call_tool(
                self.endpoint_url,
                tool_name,
                dict(arguments),
                self.timeout_seconds,
            )
            logger.info(
                "mcp_call_completed",
                extra={"mcp_source": self.source_name, "tool_name": tool_name},
            )
            return result
        except Exception as exc:
            logger.warning(
                "mcp_call_failed",
                extra={
                    "mcp_source": self.source_name,
                    "tool_name": tool_name,
                    "error": str(exc),
                },
            )
            raise McpClientError(str(exc)) from exc


def _unwrap_call_tool_result(result: Any) -> Any:
    if getattr(result, "isError", False):
        text = _content_text(getattr(result, "content", None))
        raise McpClientError(text or f"MCP tool returned error: {result!r}")

    structured_content = getattr(result, "structuredContent", None)
    if structured_content is not None:
        return _unwrap_result_key(structured_content)

    text = _content_text(getattr(result, "content", None))
    if text:
        try:
            return _unwrap_result_key(json.loads(text))
        except json.JSONDecodeError:
            return text

    return {}


def _content_text(content: Any) -> str:
    if not isinstance(content, list):
        return ""
    chunks: list[str] = []
    for item in content:
        text = getattr(item, "text", None)
        if text:
            chunks.append(str(text))
    return "\n".join(chunks)


def _unwrap_result_key(payload: Any) -> Any:
    if isinstance(payload, dict) and "result" in payload and len(payload) == 1:
        return payload["result"]
    return payload


def _create_internal_mcp_http_client(
    headers: dict[str, str] | None = None,
    timeout: httpx.Timeout | None = None,
    auth: httpx.Auth | None = None,
) -> httpx.AsyncClient:
    kwargs: dict[str, Any] = {
        "follow_redirects": True,
        "trust_env": False,
    }
    if timeout is not None:
        kwargs["timeout"] = timeout
    if headers is not None:
        kwargs["headers"] = headers
    if auth is not None:  # pragma: no cover
        kwargs["auth"] = auth
    return httpx.AsyncClient(**kwargs)
