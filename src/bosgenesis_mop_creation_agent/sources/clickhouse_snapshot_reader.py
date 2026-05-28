from __future__ import annotations

from typing import Any, Callable

from bosgenesis_mop_creation_agent.config.settings import InventoryClickHouseSettings
from bosgenesis_mop_creation_agent.sources.snapshot_models import (
    InventoryHelmRelease,
    InventoryResource,
    NormalizedInventory,
)


ClientFactory = Callable[[], Any]


class ClickHouseSnapshotReader:
    def __init__(
        self,
        settings: InventoryClickHouseSettings,
        client_factory: ClientFactory | None = None,
    ) -> None:
        self._settings = settings
        self._client_factory = client_factory

    @property
    def enabled(self) -> bool:
        return self._settings.enabled

    def read(self, namespace: str, snapshot_selector: str) -> NormalizedInventory | None:
        if not self._settings.enabled:
            return None

        client = self._client()
        try:
            run = self._select_run(client, namespace, snapshot_selector)
            if run is None:
                return None
            resources = self._select_resources(client, namespace, run["run_id"])
            helm_releases = self._select_helm_releases(client, namespace, run["run_id"])
            observed_at = run.get("finished_at") or _latest_observed_at(resources, helm_releases)
            run_id = str(run["run_id"])
            return NormalizedInventory(
                source="clickhouse",
                namespace=namespace,
                snapshot_id=run_id,
                run_id=run_id,
                correlation_id=_optional_str(run.get("correlation_id")),
                observed_at=observed_at,
                resources=resources,
                helm_releases=helm_releases,
            )
        finally:
            close = getattr(client, "close", None)
            if callable(close):
                close()

    def _client(self):
        if self._client_factory is not None:
            return self._client_factory()
        import clickhouse_connect

        kwargs = {
            "host": self._settings.host,
            "port": self._settings.port,
            "username": self._settings.user,
            "database": self._settings.database,
        }
        if self._settings.password is not None:
            kwargs["password"] = self._settings.password
        return clickhouse_connect.get_client(**kwargs)

    def _select_run(self, client, namespace: str, snapshot_selector: str) -> dict[str, Any] | None:
        database = self._settings.database
        if snapshot_selector == "latest":
            query = f"""
                SELECT run_id, correlation_id, finished_at
                FROM {database}.scan_run_facts
                WHERE namespace = {{namespace:String}}
                ORDER BY finished_at DESC
                LIMIT 1
            """
            params = {"namespace": namespace}
        else:
            query = f"""
                SELECT run_id, correlation_id, finished_at
                FROM {database}.scan_run_facts
                WHERE namespace = {{namespace:String}} AND run_id = {{run_id:String}}
                LIMIT 1
            """
            params = {"namespace": namespace, "run_id": snapshot_selector}
        return _first_row(client, query, params)

    def _select_resources(self, client, namespace: str, run_id: str) -> list[InventoryResource]:
        database = self._settings.database
        rows = _rows(
            client,
            f"""
            SELECT namespace, source, resource_kind, resource_name, entity_key,
                   status_summary, content_hash, observed_at
            FROM {database}.resource_status_facts
            WHERE namespace = {{namespace:String}} AND run_id = {{run_id:String}}
            ORDER BY resource_kind, resource_name
            """,
            {"namespace": namespace, "run_id": run_id},
        )
        return [
            InventoryResource(
                kind=str(row["resource_kind"]),
                name=str(row["resource_name"]),
                namespace=str(row["namespace"]),
                source=str(row.get("source") or "clickhouse"),
                entity_key=_optional_str(row.get("entity_key")),
                status_summary=row.get("status_summary"),
                content_hash=_optional_str(row.get("content_hash")),
                observed_at=row.get("observed_at"),
            )
            for row in rows
        ]

    def _select_helm_releases(self, client, namespace: str, run_id: str) -> list[InventoryHelmRelease]:
        database = self._settings.database
        rows = _rows(
            client,
            f"""
            SELECT namespace, release_name, chart_name, chart_version, app_version,
                   revision, status, entity_key, content_hash, observed_at
            FROM {database}.helm_release_facts
            WHERE namespace = {{namespace:String}} AND run_id = {{run_id:String}}
            ORDER BY release_name
            """,
            {"namespace": namespace, "run_id": run_id},
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
            )
            for row in rows
        ]


def _first_row(client, query: str, params: dict[str, Any]) -> dict[str, Any] | None:
    rows = _rows(client, query, params)
    return rows[0] if rows else None


def _rows(client, query: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    result = client.query(query, parameters=params)
    names = list(getattr(result, "column_names", []))
    return [dict(zip(names, row, strict=False)) for row in result.result_rows]


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
