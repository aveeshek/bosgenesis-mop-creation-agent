# Persistence Specification

## Intent

`persistence/` stores generated artifacts, metadata, and metrics.

## Current implementation note

Local artifact writing is currently implemented in `rendering/artifact_writer.py`.
This package-level `persistence/` module remains reserved for durable metadata
stores and future extraction of local storage responsibilities.

## Future modules

- `local_storage.py`
- `mongodb_store.py`
- `postgres_metadata_store.py`
- `clickhouse_metrics_store.py`

## Mandatory local storage

Successful runs must write:

```text
/data/mops/<mop-id>/artifact.json
/data/mops/<mop-id>/<file-name>.human-mop.md
/data/mops/<mop-id>/<file-name>.pdf
/data/mops/<mop-id>/<file-name>.installation.md
/data/mops/<mop-id>/machine_execution_plan.yaml
```

When snippets exist:

```text
/data/mops/<mop-id>/generated/*.yaml
/data/mops/<mop-id>/values/*.yaml
/data/mops/<mop-id>/evidence/*.json
```

Local storage failure fails the run.

Artifact APIs may expose:

```text
/data/mops/<mop-id>/generated.zip
```

Zip archives are derived artifacts and may be recreated from the run directory.

## Housekeeping

Housekeeping APIs may delete:

- one run directory by `mop_id`;
- all run directories under the configured local storage root when `confirm=true`.

Delete operations must be path-guarded to the configured local storage root and
must remove matching in-memory run metadata.

## Optional stores

- MongoDB stores full redacted MoP text representation, installation notes, and generation trace.
- PostgreSQL stores run and artifact metadata.
- ClickHouse stores generation metrics and analytical events.

Optional store failures must produce warnings but may not fail the run when local storage succeeds.

## Safety

Persistence receives only validated and redacted content.

Qdrant writes are explicitly out of scope for this package. Use `retrieval/` for read-only Qdrant prior-reference lookup.
