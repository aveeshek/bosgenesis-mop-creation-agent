from __future__ import annotations

import json
import re
from threading import Lock
from typing import Literal, Protocol

from bosgenesis_mop_creation_agent.config.settings import MemoryBackendSettings
from bosgenesis_mop_creation_agent.memory.models import MemoryRecord


class RedisClient(Protocol):
    def lrange(self, name: str, start: int, end: int) -> list[bytes | str]: ...

    def rpush(self, name: str, *values: str) -> int: ...

    def ltrim(self, name: str, start: int, end: int) -> bool: ...


class MemoryAdapter:
    name = "memory"

    def read(self, namespace_key: str, limit: int) -> tuple[list[MemoryRecord], str, list[str]]:
        raise NotImplementedError

    def write(self, records: list[MemoryRecord]) -> tuple[str, list[str]]:
        raise NotImplementedError


class InProcessLangMemAdapter(MemoryAdapter):
    """Small LangMem-shaped adapter used until external LangMem storage is configured."""

    name = "langmem"

    def __init__(self) -> None:
        self._records: dict[str, list[MemoryRecord]] = {}
        self._lock = Lock()

    def read(self, namespace_key: str, limit: int) -> tuple[list[MemoryRecord], str, list[str]]:
        with self._lock:
            records = list(self._records.get(namespace_key, []))[-limit:]
        records.reverse()
        return records, "ok", []

    def write(self, records: list[MemoryRecord]) -> tuple[str, list[str]]:
        with self._lock:
            for record in records:
                self._records.setdefault(record.namespace_key, []).append(record)
        return "ok", []


class RedisMemoryAdapter(MemoryAdapter):
    name = "redis"

    def __init__(
        self,
        settings: MemoryBackendSettings,
        client: RedisClient | None = None,
        max_records_per_namespace: int = 200,
        allowed_kinds: set[str] | None = None,
    ) -> None:
        self._settings = settings
        self._client = client
        self._max_records_per_namespace = max_records_per_namespace
        self._allowed_kinds = allowed_kinds or {"short_term"}

    def read(self, namespace_key: str, limit: int) -> tuple[list[MemoryRecord], str, list[str]]:
        if not self._settings.enabled:
            return [], "disabled", []
        try:
            client = self._redis()
            raw_values = client.lrange(_redis_key(self._settings, namespace_key), -limit, -1)
            records = []
            for raw_value in raw_values:
                value = raw_value.decode("utf-8") if isinstance(raw_value, bytes) else raw_value
                records.append(MemoryRecord.model_validate_json(value))
            records.reverse()
            return records, "ok", []
        except Exception as exc:
            return [], "unavailable", [f"redis_memory_unavailable:{exc}"]

    def write(self, records: list[MemoryRecord]) -> tuple[str, list[str]]:
        if not self._settings.enabled:
            return "disabled", []
        records = [record for record in records if record.kind in self._allowed_kinds]
        if not records:
            return "ok", []
        try:
            client = self._redis()
            by_namespace: dict[str, list[MemoryRecord]] = {}
            for record in records:
                by_namespace.setdefault(record.namespace_key, []).append(record)
            for namespace_key, namespace_records in by_namespace.items():
                key = _redis_key(self._settings, namespace_key)
                client.rpush(
                    key,
                    *[
                        json.dumps(record.model_dump(mode="json"), sort_keys=True)
                        for record in namespace_records
                    ],
                )
                client.ltrim(key, -self._max_records_per_namespace, -1)
            return "ok", []
        except Exception as exc:
            return "unavailable", [f"redis_memory_unavailable:{exc}"]

    def _redis(self) -> RedisClient:
        if self._client is not None:
            return self._client
        try:
            from redis import Redis
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise RuntimeError("redis package is not installed") from exc
        host, port = _parse_host_port(self._settings.endpoint)
        self._client = Redis(
            host=host,
            port=port,
            db=self._settings.db,
            socket_connect_timeout=self._settings.timeout_seconds,
            socket_timeout=self._settings.timeout_seconds,
            decode_responses=False,
        )
        return self._client


class UnavailableExternalAdapter(MemoryAdapter):
    def __init__(self, name: str, settings: MemoryBackendSettings, reason: str) -> None:
        self.name = name
        self._settings = settings
        self._reason = reason

    def read(self, namespace_key: str, limit: int) -> tuple[list[MemoryRecord], str, list[str]]:
        if not self._settings.enabled:
            return [], "disabled", []
        return [], "unavailable", [f"{self.name}_memory_unavailable:{self._reason}"]

    def write(self, records: list[MemoryRecord]) -> tuple[str, list[str]]:
        if not self._settings.enabled:
            return "disabled", []
        return "unavailable", [f"{self.name}_memory_unavailable:{self._reason}"]


class PgVectorMemoryAdapter(MemoryAdapter):
    name = "pgvector"

    def __init__(
        self,
        settings: MemoryBackendSettings,
        allowed_kinds: set[Literal["episodic"]] | None = None,
    ) -> None:
        self._settings = settings
        self._allowed_kinds = allowed_kinds or {"episodic"}
        self._initialized = False
        self._vector_extension_status = "not_attempted"

    def read(self, namespace_key: str, limit: int) -> tuple[list[MemoryRecord], str, list[str]]:
        if not self._settings.enabled:
            return [], "disabled", []
        try:
            with self._connect() as conn:
                self._ensure_schema(conn)
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT memory_id, namespace_key, kind, summary, labels,
                               source_mop_id, source_run_id, confidence,
                               redaction_status, created_at
                        FROM {table}
                        WHERE namespace_key = %s AND kind = ANY(%s)
                        ORDER BY created_at DESC
                        LIMIT %s
                        """.format(table=_safe_sql_identifier(self._settings.table)),
                        (namespace_key, list(self._allowed_kinds), limit),
                    )
                    rows = cur.fetchall()
            return [_record_from_pg_row(row) for row in rows], "ok", []
        except Exception as exc:
            return [], "unavailable", [f"pgvector_memory_unavailable:{exc}"]

    def write(self, records: list[MemoryRecord]) -> tuple[str, list[str]]:
        if not self._settings.enabled:
            return "disabled", []
        records = [record for record in records if record.kind in self._allowed_kinds]
        if not records:
            return "ok", []
        try:
            with self._connect() as conn:
                self._ensure_schema(conn)
                with conn.cursor() as cur:
                    for record in records:
                        cur.execute(
                            """
                            INSERT INTO {table} (
                                memory_id, namespace_key, kind, summary, labels,
                                source_mop_id, source_run_id, confidence,
                                redaction_status, created_at
                            )
                            VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s)
                            ON CONFLICT (memory_id) DO UPDATE SET
                                summary = EXCLUDED.summary,
                                labels = EXCLUDED.labels,
                                confidence = EXCLUDED.confidence,
                                redaction_status = EXCLUDED.redaction_status
                            """.format(table=_safe_sql_identifier(self._settings.table)),
                            (
                                record.memory_id,
                                record.namespace_key,
                                record.kind,
                                record.summary,
                                json.dumps(record.labels),
                                record.source_mop_id,
                                record.source_run_id,
                                record.confidence,
                                record.redaction_status,
                                record.created_at,
                            ),
                        )
                conn.commit()
            return "ok", []
        except Exception as exc:
            return "unavailable", [f"pgvector_memory_unavailable:{exc}"]

    def _connect(self):
        if not self._settings.dsn:
            raise ValueError("memory_pgvector_dsn_missing")
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise RuntimeError("psycopg package is not installed") from exc
        return psycopg.connect(
            self._settings.dsn,
            connect_timeout=int(self._settings.timeout_seconds),
        )

    def _ensure_schema(self, conn) -> None:
        if self._initialized:
            return
        table = _safe_sql_identifier(self._settings.table)
        with conn.cursor() as cur:
            try:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                self._vector_extension_status = "available"
            except Exception:
                conn.rollback()
                self._vector_extension_status = "unavailable"
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS {table} (
                    memory_id TEXT PRIMARY KEY,
                    namespace_key TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    labels JSONB NOT NULL DEFAULT '[]'::jsonb,
                    source_mop_id TEXT,
                    source_run_id TEXT,
                    confidence TEXT,
                    redaction_status TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
                """.format(table=table)
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS {table}_namespace_kind_created_idx
                ON {table} (namespace_key, kind, created_at DESC)
                """.format(table=table)
            )
        conn.commit()
        self._initialized = True


class LettaDisabledAdapter(MemoryAdapter):
    name = "letta"

    def read(self, namespace_key: str, limit: int) -> tuple[list[MemoryRecord], str, list[str]]:
        return [], "disabled_future_placeholder", []

    def write(self, records: list[MemoryRecord]) -> tuple[str, list[str]]:
        return "disabled_future_placeholder", []


def _redis_key(settings: MemoryBackendSettings, namespace_key: str) -> str:
    safe_namespace = re.sub(r"[^a-zA-Z0-9_.:-]", "_", namespace_key)
    return f"{settings.key_prefix}:{safe_namespace}:records"


def _parse_host_port(endpoint: str | None) -> tuple[str, int]:
    if not endpoint:
        raise ValueError("redis_endpoint_missing")
    endpoint = endpoint.removeprefix("redis://")
    host, separator, port_text = endpoint.partition(":")
    if not host:
        raise ValueError("redis_host_missing")
    if not separator:
        return host, 6379
    return host, int(port_text)


def _safe_sql_identifier(value: str | None) -> str:
    if not value:
        return "mop_agent_memory"
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", value):
        raise ValueError("unsafe_pgvector_table_name")
    return value


def _record_from_pg_row(row: tuple) -> MemoryRecord:
    (
        memory_id,
        namespace_key,
        kind,
        summary,
        labels,
        source_mop_id,
        source_run_id,
        confidence,
        redaction_status,
        created_at,
    ) = row
    return MemoryRecord(
        memory_id=memory_id,
        namespace_key=namespace_key,
        kind=kind,
        summary=summary,
        labels=list(labels or []),
        source_mop_id=source_mop_id,
        source_run_id=source_run_id,
        confidence=confidence or "medium",
        redaction_status=redaction_status,
        created_at=created_at,
    )
