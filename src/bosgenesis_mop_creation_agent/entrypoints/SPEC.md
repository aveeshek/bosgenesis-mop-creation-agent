# Entrypoints Specification

## Intent

`entrypoints/` defines process startup contracts for the runtime.

## Runtime commands

Runtime command targets:

```text
api
worker
service
```

- `api`: REST and MCP server.
- `worker`: reserved for a future external worker process.
- `service`: reserved for combined REST, MCP, and external worker orchestration.

## Required startup behavior

Startup must:

- load configuration;
- validate v1 scope defaults;
- report safe effective configuration with secrets redacted;
- initialize observability;
- initialize optional memory adapters;
- expose health readiness without requiring upstream dependencies to be healthy;
- fail fast only for mandatory local runtime requirements.
- start background generation within the API process for the current async implementation.

## Runtime mode rule

The agent is on-demand only in v1. It must not start a periodic scheduler unless a later specification explicitly adds one.
