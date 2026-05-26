# Entrypoints Specification

## Intent

`entrypoints/` defines process startup contracts for the future runtime.

## Runtime commands

Future runtime commands:

```text
api
worker
service
```

- `api`: REST and MCP server only.
- `worker`: standalone reasoning worker only, if asynchronous operation is added.
- `service`: REST, MCP, and worker orchestration.

## Required startup behavior

Startup must:

- load configuration;
- validate v1 scope defaults;
- report safe effective configuration with secrets redacted;
- initialize observability;
- initialize optional memory adapters;
- expose health readiness without requiring upstream dependencies to be healthy;
- fail fast only for mandatory local runtime requirements.

## Runtime mode rule

The agent is on-demand only in v1. It must not start a periodic scheduler unless a later specification explicitly adds one.

