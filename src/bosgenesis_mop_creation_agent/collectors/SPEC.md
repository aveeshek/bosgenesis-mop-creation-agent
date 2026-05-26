# Collectors Specification

## Intent

`collectors/` gathers raw evidence through approved clients and stores.

## Collector types

- Snapshot collector.
- Kubernetes namespace resource collector.
- Helm release collector.
- Data ingestion evidence collector.
- Application-mode schema/topology metadata collector.
- Public repository metadata collector.

## Snapshot collection

Snapshot collection prefers:

1. PostgreSQL latest ETL snapshot.
2. ClickHouse analytical inventory.
3. Live MCP-only fallback when explicitly enabled.

## Resource collection

Collectors must gather enough evidence to classify:

- Helm-managed resources;
- raw Kubernetes resources;
- excluded resources;
- warning-only resources.

## Application-mode collection

Application collectors are metadata-only and may target PostgreSQL, ClickHouse, MongoDB, Redis, and Kafka.

They must not collect table rows, MongoDB documents, Kafka messages, Redis values, uploaded files, or business data.

## Public repository collection

Repository hints are v1 public-repository-only. Private/custom repo discovery is future scope.

## Safety

Collectors must not mutate state and must not collect secret values.

