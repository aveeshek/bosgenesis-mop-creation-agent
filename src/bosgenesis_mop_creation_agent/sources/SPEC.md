# Sources Specification

## Intent

`sources/` reads durable inventory and analytical evidence before live MCP enrichment.

## Initial source readers

- `postgres_snapshot_reader.py`
- `clickhouse_snapshot_reader.py`
- `snapshot_models.py`
- `snapshot_selector.py`

## Selection order

Snapshot selection must prefer:

1. PostgreSQL latest ETL snapshot.
2. ClickHouse analytical inventory.
3. Live MCP-only fallback when explicitly enabled by policy in a later phase.

Phase 3 does not use live Kubernetes or Helm fallback. If both stored snapshot sources are
disabled, unavailable, or empty, generation continues with empty valid artifacts and explicit
warnings.

## Responsibilities

- Read latest source namespace inventory.
- Support explicit `source_snapshot_id` when provided.
- Return redacted, stable source records.
- Preserve snapshot timestamp and provenance.
- Report unavailable sources as warnings when fallback is allowed.

## Safety

Source readers must not mutate stores, must not read secret values, and must not return production data.
