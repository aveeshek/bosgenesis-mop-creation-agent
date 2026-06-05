# Redis Memory Specification

## Intent

Redis is the implemented durable backend for short-term run memory when the memory layer is enabled.

## Boundary

Redis memory must not contain secret values or production data. Records are namespace-scoped JSON memory summaries stored under `<key_prefix>:<namespace_key>:records`, with default prefix `mop-agent-memory` and default DB index `0`.

