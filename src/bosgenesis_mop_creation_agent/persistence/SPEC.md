# Persistence Specification

## Intent

`persistence/` stores generated artifacts, metadata, and metrics.

## Future modules

- `local_storage.py`
- `mongodb_store.py`
- `postgres_metadata_store.py`
- `clickhouse_metrics_store.py`

## Mandatory local storage

Successful runs must write:

```text
/data/mops/<file-name>.pdf
/data/mops/<file-name>.installation.md
```

When snippets exist:

```text
/data/mops/<mop-id>/generated/*.yaml
/data/mops/<mop-id>/values/*.yaml
/data/mops/<mop-id>/evidence/*.json
```

Local storage failure fails the run.

## Optional stores

- MongoDB stores full redacted MoP text representation, installation notes, and generation trace.
- PostgreSQL stores run and artifact metadata.
- ClickHouse stores generation metrics and analytical events.

Optional store failures must produce warnings but may not fail the run when local storage succeeds.

## Safety

Persistence receives only validated and redacted content.

Qdrant writes are explicitly out of scope for this package. Use `retrieval/` for read-only Qdrant prior-reference lookup.
