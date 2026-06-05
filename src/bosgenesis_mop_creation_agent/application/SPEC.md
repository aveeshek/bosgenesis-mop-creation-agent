# Application Inference Specification

## Intent

`application/` defines deferred/backlog application-mode schema and component inference contracts.

Application mode is deferred because Phase 12 is skipped for now. The module contract is retained for future implementation. When reactivated, it will augment `platform-only` output with metadata-only schema/topology guidance and must not execute schema creation or copy data.

## Targets

- PostgreSQL schemas.
- ClickHouse schemas.
- Redis keyspace shape.
- MongoDB databases and collections.
- Kafka brokers and topics.

## In scope

- Schema names.
- Table definitions.
- Indexes.
- Views/materialized views where discoverable.
- MongoDB database and collection names.
- MongoDB index and validation shape where discoverable.
- Redis key patterns and TTL policy hints.
- Kafka topic names, partitions, replication factor, and safe configs.
- Validation guidance.
- Manual rollback guidance.

## Out of scope

- SQL rows.
- MongoDB documents.
- Kafka messages.
- Redis values.
- Uploaded files.
- Credentials.
- Destructive DDL execution.
- Live mutation.

## Credential rule

Application-mode credentials must be explicit, read-only, redacted from every output, and never persisted as plaintext.

## LLM rule

LLM-assisted application inference may use redacted metadata only and must label inferred schema/topology guidance with confidence and required human confirmation.

