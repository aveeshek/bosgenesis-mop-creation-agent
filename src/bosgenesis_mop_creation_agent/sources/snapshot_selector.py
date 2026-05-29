from __future__ import annotations

from bosgenesis_mop_creation_agent.common.logging import get_logger
from bosgenesis_mop_creation_agent.sources.clickhouse_snapshot_reader import ClickHouseSnapshotReader
from bosgenesis_mop_creation_agent.sources.postgres_snapshot_reader import PostgresSnapshotReader
from bosgenesis_mop_creation_agent.sources.snapshot_models import SnapshotReadResult


logger = get_logger(__name__)


class SnapshotSelector:
    def __init__(
        self,
        postgres_reader: PostgresSnapshotReader,
        clickhouse_reader: ClickHouseSnapshotReader,
    ) -> None:
        self._postgres_reader = postgres_reader
        self._clickhouse_reader = clickhouse_reader

    def read(self, namespace: str, snapshot_selector: str) -> SnapshotReadResult:
        warnings: list[str] = []
        attempted: list[str] = []

        if self._postgres_reader.enabled:
            attempted.append("postgres")
            try:
                inventory = self._postgres_reader.read(namespace, snapshot_selector)
            except Exception as exc:  # noqa: BLE001 - readers degrade to fallback warnings.
                logger.warning(
                    "postgres_snapshot_read_failed",
                    extra={"namespace": namespace, "error": str(exc)},
                )
                warnings.append(f"postgres_snapshot_read_failed: {exc}")
            else:
                if inventory and inventory.total_count > 0:
                    return SnapshotReadResult(
                        inventory=inventory,
                        warnings=warnings,
                        sources_attempted=attempted,
                    )
                warnings.append(
                    f"postgres_snapshot_missing: no inventory for namespace={namespace} "
                    f"selector={snapshot_selector}"
                )
        else:
            warnings.append("postgres_snapshot_reader_disabled")

        if self._clickhouse_reader.enabled:
            attempted.append("clickhouse")
            try:
                inventory = self._clickhouse_reader.read(namespace, snapshot_selector)
            except Exception as exc:  # noqa: BLE001 - readers degrade to fallback warnings.
                logger.warning(
                    "clickhouse_snapshot_read_failed",
                    extra={"namespace": namespace, "error": str(exc)},
                )
                warnings.append(f"clickhouse_snapshot_read_failed: {exc}")
            else:
                if inventory and inventory.total_count > 0:
                    warnings.append("snapshot_fallback_used: clickhouse")
                    return SnapshotReadResult(
                        inventory=inventory,
                        warnings=warnings,
                        sources_attempted=attempted,
                    )
                warnings.append(
                    f"clickhouse_snapshot_missing: no inventory for namespace={namespace} "
                    f"selector={snapshot_selector}"
                )
        else:
            warnings.append("clickhouse_snapshot_reader_disabled")

        warnings.append(
            "snapshot_inventory_missing: generated artifacts contain no discovered resources; "
            "continuing to governed MCP enrichment"
        )
        return SnapshotReadResult(warnings=warnings, sources_attempted=attempted)
