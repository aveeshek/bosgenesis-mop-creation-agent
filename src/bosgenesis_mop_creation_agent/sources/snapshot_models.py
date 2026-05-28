from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class InventoryResource(BaseModel):
    kind: str
    name: str
    namespace: str
    source: str
    entity_key: str | None = None
    api_version: str | None = None
    status_summary: str | None = None
    content_hash: str | None = None
    observed_at: datetime | None = None
    normalized_payload: dict[str, Any] = Field(default_factory=dict)


class InventoryHelmRelease(BaseModel):
    release_name: str
    namespace: str
    chart_name: str | None = None
    chart_version: str | None = None
    app_version: str | None = None
    revision: int | None = None
    status: str | None = None
    entity_key: str | None = None
    content_hash: str | None = None
    observed_at: datetime | None = None
    normalized_payload: dict[str, Any] = Field(default_factory=dict)


class NormalizedInventory(BaseModel):
    source: str
    namespace: str
    snapshot_id: str
    run_id: str | None = None
    correlation_id: str | None = None
    observed_at: datetime | None = None
    resources: list[InventoryResource] = Field(default_factory=list)
    helm_releases: list[InventoryHelmRelease] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @property
    def resource_count(self) -> int:
        return len(self.resources)

    @property
    def helm_release_count(self) -> int:
        return len(self.helm_releases)

    @property
    def total_count(self) -> int:
        return self.resource_count + self.helm_release_count


class SnapshotReadResult(BaseModel):
    inventory: NormalizedInventory | None = None
    warnings: list[str] = Field(default_factory=list)
    sources_attempted: list[str] = Field(default_factory=list)

