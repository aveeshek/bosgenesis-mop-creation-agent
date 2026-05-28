from __future__ import annotations

import json
from typing import Any, Callable

from bosgenesis_mop_creation_agent.config.settings import InventoryPostgresSettings
from bosgenesis_mop_creation_agent.sources.snapshot_models import (
    InventoryHelmRelease,
    InventoryResource,
    NormalizedInventory,
)


ConnectionFactory = Callable[[], Any]


class PostgresSnapshotReader:
    def __init__(
        self,
        settings: InventoryPostgresSettings,
        connection_factory: ConnectionFactory | None = None,
    ) -> None:
        self._settings = settings
        self._connection_factory = connection_factory

    @property
    def enabled(self) -> bool:
        return self._settings.enabled

    def read(self, namespace: str, snapshot_selector: str) -> NormalizedInventory | None:
        if not self._settings.enabled:
            return None
        if not self._settings.dsn and self._connection_factory is None:
            raise ValueError("PostgreSQL snapshot reader requires POSTGRES_DSN")

        conn = self._connect()
        try:
            run = self._select_run(conn, namespace, snapshot_selector)
            if run is None:
                return None
            resources = self._select_resources(conn, namespace, run["run_id"])
            helm_releases = self._select_helm_releases(conn, namespace, run["run_id"])
            observed_at = run.get("finished_at") or _latest_observed_at(resources, helm_releases)
            run_id = str(run["run_id"])
            return NormalizedInventory(
                source="postgres",
                namespace=namespace,
                snapshot_id=run_id,
                run_id=run_id,
                correlation_id=_optional_str(run.get("correlation_id")),
                observed_at=observed_at,
                resources=resources,
                helm_releases=helm_releases,
            )
        finally:
            close = getattr(conn, "close", None)
            if callable(close):
                close()

    def _connect(self):
        if self._connection_factory is not None:
            return self._connection_factory()
        import psycopg

        return psycopg.connect(self._settings.dsn)

    def _select_run(self, conn, namespace: str, snapshot_selector: str) -> dict[str, Any] | None:
        schema = self._settings.schema_name
        if snapshot_selector == "latest":
            query = f"""
                SELECT run_id, correlation_id, finished_at
                FROM {schema}.scan_runs
                WHERE namespace = %s
                ORDER BY finished_at DESC NULLS LAST, started_at DESC NULLS LAST
                LIMIT 1
            """
            params = (namespace,)
        else:
            query = f"""
                SELECT run_id, correlation_id, finished_at
                FROM {schema}.scan_runs
                WHERE namespace = %s AND run_id = %s
                LIMIT 1
            """
            params = (namespace, snapshot_selector)
        return _first_mapping(conn.execute(query, params))

    def _select_resources(self, conn, namespace: str, run_id: str) -> list[InventoryResource]:
        schema = self._settings.schema_name
        rows = _all_mappings(
            conn.execute(
                f"""
                SELECT namespace, source, api_version, resource_kind, resource_name,
                       entity_key, status_summary, content_hash, observed_at,
                       normalized_payload
                FROM {schema}.resource_snapshots
                WHERE namespace = %s AND run_id = %s
                ORDER BY resource_kind, resource_name
                """,
                (namespace, run_id),
            )
        )
        return [
            InventoryResource(
                kind=str(row["resource_kind"]),
                name=str(row["resource_name"]),
                namespace=str(row["namespace"]),
                source=str(row.get("source") or "postgres"),
                api_version=row.get("api_version"),
                entity_key=_optional_str(row.get("entity_key")),
                status_summary=row.get("status_summary"),
                content_hash=_optional_str(row.get("content_hash")),
                observed_at=row.get("observed_at"),
                normalized_payload=_json_dict(row.get("normalized_payload")),
            )
            for row in rows
        ]

    def _select_helm_releases(self, conn, namespace: str, run_id: str) -> list[InventoryHelmRelease]:
        schema = self._settings.schema_name
        rows = _all_mappings(
            conn.execute(
                f"""
                SELECT namespace, release_name, chart_name, chart_version, app_version,
                       revision, status, entity_key, content_hash, observed_at,
                       normalized_payload
                FROM {schema}.helm_release_snapshots
                WHERE namespace = %s AND run_id = %s
                ORDER BY release_name
                """,
                (namespace, run_id),
            )
        )
        return [
            InventoryHelmRelease(
                release_name=str(row["release_name"]),
                namespace=str(row["namespace"]),
                chart_name=row.get("chart_name"),
                chart_version=row.get("chart_version"),
                app_version=row.get("app_version"),
                revision=_optional_int(row.get("revision")),
                status=row.get("status"),
                entity_key=_optional_str(row.get("entity_key")),
                content_hash=_optional_str(row.get("content_hash")),
                observed_at=row.get("observed_at"),
                normalized_payload=_json_dict(row.get("normalized_payload")),
            )
            for row in rows
        ]


def _first_mapping(cursor) -> dict[str, Any] | None:
    row = cursor.fetchone()
    if row is None:
        return None
    return _to_mapping(cursor, row)


def _all_mappings(cursor) -> list[dict[str, Any]]:
    return [_to_mapping(cursor, row) for row in cursor.fetchall()]


def _to_mapping(cursor, row) -> dict[str, Any]:
    if isinstance(row, dict):
        return row
    columns = [desc[0] for desc in cursor.description]
    return dict(zip(columns, row, strict=False))


def _json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            loaded = json.loads(value)
            return loaded if isinstance(loaded, dict) else {}
        except json.JSONDecodeError:
            return {}
    return {}


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _latest_observed_at(
    resources: list[InventoryResource],
    helm_releases: list[InventoryHelmRelease],
):
    observed = [
        item.observed_at for item in [*resources, *helm_releases] if item.observed_at is not None
    ]
    return max(observed) if observed else None
