from bosgenesis_mop_creation_agent.sources.snapshot_models import (
    InventoryHelmRelease,
    InventoryResource,
    NormalizedInventory,
)
from bosgenesis_mop_creation_agent.sources.snapshot_selector import SnapshotSelector


class FakeReader:
    def __init__(self, *, enabled: bool, inventory: NormalizedInventory | None = None) -> None:
        self.enabled = enabled
        self.inventory = inventory
        self.calls: list[tuple[str, str]] = []

    def read(self, namespace: str, snapshot_selector: str) -> NormalizedInventory | None:
        self.calls.append((namespace, snapshot_selector))
        return self.inventory


def test_snapshot_selector_prefers_postgres() -> None:
    postgres_inventory = NormalizedInventory(
        source="postgres",
        namespace="bosgenesis",
        snapshot_id="pg-run",
        resources=[InventoryResource(kind="Deployment", name="api", namespace="bosgenesis", source="k8s")],
    )
    clickhouse_inventory = NormalizedInventory(
        source="clickhouse",
        namespace="bosgenesis",
        snapshot_id="ch-run",
        resources=[
            InventoryResource(kind="Service", name="api", namespace="bosgenesis", source="k8s")
        ],
    )

    selector = SnapshotSelector(
        postgres_reader=FakeReader(enabled=True, inventory=postgres_inventory),
        clickhouse_reader=FakeReader(enabled=True, inventory=clickhouse_inventory),
    )

    result = selector.read("bosgenesis", "latest")

    assert result.inventory == postgres_inventory
    assert result.sources_attempted == ["postgres"]
    assert result.warnings == []


def test_snapshot_selector_falls_back_to_clickhouse_when_postgres_missing() -> None:
    clickhouse_inventory = NormalizedInventory(
        source="clickhouse",
        namespace="bosgenesis",
        snapshot_id="ch-run",
        resources=[
            InventoryResource(kind="Service", name="api", namespace="bosgenesis", source="k8s")
        ],
        helm_releases=[
            InventoryHelmRelease(release_name="api", namespace="bosgenesis", chart_name="repo/api")
        ],
    )

    selector = SnapshotSelector(
        postgres_reader=FakeReader(enabled=True, inventory=None),
        clickhouse_reader=FakeReader(enabled=True, inventory=clickhouse_inventory),
    )

    result = selector.read("bosgenesis", "latest")

    assert result.inventory == clickhouse_inventory
    assert result.sources_attempted == ["postgres", "clickhouse"]
    assert "postgres_snapshot_missing" in " ".join(result.warnings)
    assert "snapshot_fallback_used: clickhouse" in result.warnings


def test_snapshot_selector_warns_when_all_sources_missing() -> None:
    selector = SnapshotSelector(
        postgres_reader=FakeReader(enabled=False),
        clickhouse_reader=FakeReader(enabled=False),
    )

    result = selector.read("bosgenesis", "latest")

    assert result.inventory is None
    assert result.sources_attempted == []
    assert "postgres_snapshot_reader_disabled" in result.warnings
    assert "clickhouse_snapshot_reader_disabled" in result.warnings
    assert any("snapshot_inventory_missing" in warning for warning in result.warnings)
