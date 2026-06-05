from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


MemoryKind = Literal["short_term", "episodic", "knowledge"]


class MemoryRecord(BaseModel):
    memory_id: str
    namespace_key: str
    kind: MemoryKind
    summary: str
    labels: list[str] = Field(default_factory=list)
    source_mop_id: str | None = None
    source_run_id: str | None = None
    confidence: str = "medium"
    redaction_status: str = "non_secret_summary_only"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MemoryContext(BaseModel):
    enabled: bool = False
    namespace_key: str
    status: str = "disabled"
    records: list[MemoryRecord] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @property
    def read_count(self) -> int:
        return len(self.records)


class MemoryWriteResult(BaseModel):
    enabled: bool = False
    namespace_key: str
    status: str = "disabled"
    written_count: int = 0
    backend_status: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class MemoryTraceEvent(BaseModel):
    event: str
    namespace_key: str
    status: str
    read_count: int = 0
    written_count: int = 0
    warnings: list[str] = Field(default_factory=list)

