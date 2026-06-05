from __future__ import annotations

import hashlib
import logging
import re

from bosgenesis_mop_creation_agent.classification.models import ClassificationSummary
from bosgenesis_mop_creation_agent.config.settings import MemorySettings
from bosgenesis_mop_creation_agent.memory.adapters import (
    InProcessLangMemAdapter,
    LettaDisabledAdapter,
    MemoryAdapter,
    PgVectorMemoryAdapter,
    RedisMemoryAdapter,
    UnavailableExternalAdapter,
)
from bosgenesis_mop_creation_agent.memory.models import MemoryContext, MemoryRecord, MemoryWriteResult
from bosgenesis_mop_creation_agent.retrieval.models import ReferenceLookupResult
from bosgenesis_mop_creation_agent.sources.snapshot_models import NormalizedInventory


LOGGER = logging.getLogger(__name__)
SECRET_PATTERNS = (
    re.compile(r"(?i)(password|secret|token|credential|api[_-]?key|connection[_-]?string)\s*[:=]"),
    re.compile(r"(?i)bearer\s+[a-z0-9._~+/=-]{12,}"),
)


class AgentMemoryService:
    def __init__(
        self,
        settings: MemorySettings,
        adapters: list[MemoryAdapter] | None = None,
    ) -> None:
        self._settings = settings
        self._adapters = adapters if adapters is not None else _build_adapters(settings)

    def read_context(
        self,
        *,
        namespace_key: str,
        correlation_id: str,
        run_id: str,
    ) -> MemoryContext:
        if not self._settings.enabled:
            return MemoryContext(enabled=False, namespace_key=namespace_key)

        records: list[MemoryRecord] = []
        warnings: list[str] = []
        backend_status: list[str] = []
        for adapter in self._adapters:
            adapter_records, status, adapter_warnings = adapter.read(
                namespace_key,
                self._settings.max_context_items,
            )
            backend_status.append(f"{adapter.name}:{status}")
            warnings.extend(adapter_warnings)
            records.extend(adapter_records)

        deduped = _dedupe(records)[: self._settings.max_context_items]
        status = "ok" if deduped else "empty"
        LOGGER.info(
            "memory_context_read",
            extra={
                "correlation_id": correlation_id,
                "run_id": run_id,
                "namespace_key": namespace_key,
                "status": status,
                "read_count": len(deduped),
                "backend_status": backend_status,
            },
        )
        return MemoryContext(
            enabled=True,
            namespace_key=namespace_key,
            status=status,
            records=deduped,
            warnings=warnings,
        )

    def write_generation_summary(
        self,
        *,
        namespace_key: str,
        mop_id: str,
        run_id: str,
        correlation_id: str,
        target_namespace: str,
        inventory: NormalizedInventory | None,
        classification: ClassificationSummary | None,
        qdrant_references: ReferenceLookupResult | None,
        warnings: list[str],
    ) -> MemoryWriteResult:
        if not self._settings.enabled:
            return MemoryWriteResult(enabled=False, namespace_key=namespace_key)

        records = self._safe_records(
            namespace_key=namespace_key,
            mop_id=mop_id,
            run_id=run_id,
            target_namespace=target_namespace,
            inventory=inventory,
            classification=classification,
            qdrant_references=qdrant_references,
            warnings=warnings,
        )
        backend_status: dict[str, str] = {}
        all_warnings: list[str] = []
        written_count = 0
        for adapter in self._adapters:
            status, adapter_warnings = adapter.write(records)
            backend_status[adapter.name] = status
            all_warnings.extend(adapter_warnings)
            if status == "ok":
                written_count = max(written_count, len(records))

        status = "ok" if written_count else "not_written"
        LOGGER.info(
            "memory_summary_written",
            extra={
                "correlation_id": correlation_id,
                "run_id": run_id,
                "namespace_key": namespace_key,
                "status": status,
                "written_count": written_count,
                "backend_status": backend_status,
            },
        )
        return MemoryWriteResult(
            enabled=True,
            namespace_key=namespace_key,
            status=status,
            written_count=written_count,
            backend_status=backend_status,
            warnings=all_warnings,
        )

    def _safe_records(
        self,
        *,
        namespace_key: str,
        mop_id: str,
        run_id: str,
        target_namespace: str,
        inventory: NormalizedInventory | None,
        classification: ClassificationSummary | None,
        qdrant_references: ReferenceLookupResult | None,
        warnings: list[str],
    ) -> list[MemoryRecord]:
        resource_count = inventory.resource_count if inventory else 0
        helm_count = inventory.helm_release_count if inventory else 0
        raw_count = classification.raw_k8s_count if classification else 0
        warning_only_count = classification.warning_only_count if classification else 0
        qdrant_count = qdrant_references.reference_count if qdrant_references else 0
        summary = _safe_summary(
            (
                f"Generated namespace reconstruction summary for target {target_namespace}. "
                f"Resources={resource_count}, helm_releases={helm_count}, raw_k8s={raw_count}, "
                f"warning_only={warning_only_count}, qdrant_references={qdrant_count}, "
                f"warnings={len(warnings)}."
            ),
            self._settings.max_summary_chars,
        )
        labels = ["mop_generation", "non_secret_summary", "advisory_memory"]
        records: list[MemoryRecord] = []
        if self._settings.short_term_enabled:
            records.append(
                _record(namespace_key, "short_term", summary, labels, mop_id, run_id)
            )
        if self._settings.episodic_enabled:
            records.append(
                _record(namespace_key, "episodic", summary, labels, mop_id, run_id)
            )
        if self._settings.knowledge_enabled:
            knowledge = _safe_summary(
                (
                    f"Namespace pattern: helm_releases={helm_count}; "
                    f"raw_k8s={raw_count}; warning_only={warning_only_count}. "
                    "Use only as prior context; current evidence remains authoritative."
                ),
                self._settings.max_summary_chars,
            )
            records.append(
                _record(namespace_key, "knowledge", knowledge, labels, mop_id, run_id)
            )
        return [record for record in records if _is_safe(record.summary)]


def _build_adapters(settings: MemorySettings) -> list[MemoryAdapter]:
    adapters: list[MemoryAdapter] = []
    if settings.langmem_enabled:
        adapters.append(InProcessLangMemAdapter())
    adapters.extend(
        [
            RedisMemoryAdapter(settings.redis),
            PgVectorMemoryAdapter(settings.pgvector),
            UnavailableExternalAdapter(
                "qdrant",
                settings.qdrant,
                "Qdrant memory persistence is configured as optional future wiring",
            ),
            LettaDisabledAdapter(),
        ]
    )
    return adapters


def _record(
    namespace_key: str,
    kind: str,
    summary: str,
    labels: list[str],
    mop_id: str,
    run_id: str,
) -> MemoryRecord:
    digest = hashlib.sha256(f"{namespace_key}:{kind}:{mop_id}:{summary}".encode()).hexdigest()
    return MemoryRecord(
        memory_id=f"mem-{digest[:16]}",
        namespace_key=namespace_key,
        kind=kind,  # type: ignore[arg-type]
        summary=summary,
        labels=labels,
        source_mop_id=mop_id,
        source_run_id=run_id,
    )


def _safe_summary(value: str, max_chars: int) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned[:max_chars]


def _is_safe(value: str) -> bool:
    return not any(pattern.search(value) for pattern in SECRET_PATTERNS)


def _dedupe(records: list[MemoryRecord]) -> list[MemoryRecord]:
    seen: set[str] = set()
    deduped: list[MemoryRecord] = []
    for record in sorted(records, key=lambda item: item.created_at, reverse=True):
        if record.memory_id in seen:
            continue
        seen.add(record.memory_id)
        deduped.append(record)
    return deduped
