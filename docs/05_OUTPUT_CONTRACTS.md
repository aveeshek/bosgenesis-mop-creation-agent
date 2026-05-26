# Output Contracts Specification

**Document status:** Initial scaffold  
**Applies to:** Human MoP, LLM/agent-readable installation guide, generated manifest/value snippets, metadata responses, and optional retrieval/index artifacts.

## 1. Purpose

This document defines the expected output contracts for `bosgenesis-mop-creation-agent`.

Outputs must align with the SPEC, HLD, LLD, and algorithm design:

- the agent generates procedures and artifacts only;
- the agent does not execute generated commands;
- source namespace defaults to `bosgenesis`;
- target namespace is supplied at runtime;
- generated artifacts must be safe, traceable, reproducible, and free of secret values or production data;
- inferred content must be labeled with confidence and rationale.

## 2. Primary Human MoP Contract

The human-readable MoP is the required primary artifact. It must be Markdown and must include these sections in order:

1. Document Header
2. Change Summary
3. Source and Target Namespace Overview
4. Pre-change Checklist
5. Access and Environment Verification
6. Source Namespace Export/Reference Snapshot
7. Target Namespace Preparation
8. Secret Placeholder and Prerequisite Inputs
9. Helm Release Recreation Steps
10. Raw Kubernetes Resource Recreation Steps
11. Application Schema/Topology Recreation Steps, when selected
12. Validation Steps
13. Go/No-Go Decision Points
14. Rollback Procedure
15. Post-change Activities
16. Execution Log
17. Appendix: Generated Manifests, Helm Values, Evidence, and Unknowns

## 3. Human MoP Section Requirements

| Section | Required content |
|---|---|
| Document Header | `mop_id`, `run_id`, `correlation_id`, source namespace, target namespace, generation mode, generated timestamp, caller, snapshot ID/timestamp when known. |
| Change Summary | What will be recreated, counts of Helm releases, raw Kubernetes resources, excluded resources, warnings, and application-mode targets if selected. |
| Source and Target Namespace Overview | Source evidence source, target namespace intent, assumptions, and non-goals. |
| Pre-change Checklist | Operator prerequisites, access checks, tool availability, context checks, and required approvals. |
| Access and Environment Verification | Copyable commands to confirm Kubernetes/Helm context and target namespace readiness. |
| Source Namespace Export/Reference Snapshot | Snapshot source, live MCP enrichment status, and evidence freshness. |
| Target Namespace Preparation | Namespace creation or verification instructions, without automatic execution by the agent. |
| Secret Placeholder and Prerequisite Inputs | Required secret names/keys or placeholders without secret values. |
| Helm Release Recreation Steps | Values files, dry-run commands, install/upgrade commands, validation checks, and rollback notes. |
| Raw Kubernetes Resource Recreation Steps | Generated manifest references, dry-run commands, apply commands, validation checks, and rollback notes. |
| Application Schema/Topology Recreation Steps | Metadata-only schema/topic/keyspace recreation steps when `application` mode is selected. |
| Validation Steps | Pod, deployment, service, ingress, Helm, PVC, and application-mode validation checks as applicable. |
| Go/No-Go Decision Points | Explicit stop/continue checkpoints and failed-action guidance. |
| Rollback Procedure | Helm uninstall, raw manifest delete, and cautious application-mode cleanup guidance. |
| Post-change Activities | Documentation, trace/artifact retention, and handoff notes. |
| Execution Log | Blank operator-fillable execution table. |
| Appendix | Generated manifests, values files, evidence references, excluded resources, warnings, and unknowns. |

## 4. Agent-Readable Installation Guide Contract

The agent-readable guide is the required second primary artifact. It must be Markdown and optimized for autonomous execution by another LLM/agent.

It must include:

- machine-parseable metadata;
- source namespace, target namespace, generation mode, `run_id`, `correlation_id`, and evidence timestamp;
- execution phases;
- dependency graph or ordered dependency list;
- command blocks;
- expected outcomes;
- validation checks;
- rollback hints;
- evidence references;
- inference labels, confidence, and rationale;
- unknowns and required human inputs;
- explicit no-data-copy and no-secret constraints.

The guide filename should use:

```text
/data/mops/<file-name>.agent.md
```

## 5. Command Contract

All executable commands in the MoP must be copyable and namespace-explicit.

Helm command pattern:

```bash
helm upgrade --install <release-name> <chart-ref> \
  --namespace <target-namespace> \
  --create-namespace \
  -f values-<release-name>.yaml \
  --dry-run

helm upgrade --install <release-name> <chart-ref> \
  --namespace <target-namespace> \
  --create-namespace \
  -f values-<release-name>.yaml \
  --atomic \
  --timeout 10m
```

Raw Kubernetes command pattern:

```bash
kubectl apply -f generated/<kind>-<name>.yaml -n <target-namespace> --dry-run=server -o yaml
kubectl apply -f generated/<kind>-<name>.yaml -n <target-namespace>
```

If a chart reference, value, resource, or ordering decision is inferred rather than observed, the MoP must label it as inferred and require human confirmation.

## 6. Generated File Contract

Local storage is mandatory. A successful run must produce:

```text
/data/mops/<file-name>.md
/data/mops/<file-name>.agent.md
```

When generated snippets exist, they must be referenced from the MoP and stored under:

```text
/data/mops/<mop-id>/generated/*.yaml
/data/mops/<mop-id>/values/*.yaml
/data/mops/<mop-id>/evidence/*.json
```

Generated manifests must:

- rewrite `metadata.namespace` to the target namespace;
- remove runtime metadata;
- exclude blocked resource kinds;
- contain no secret values or production data.

## 7. API Response Contract

The generation response must include:

```text
status
mop_id
run_id
correlation_id
source_namespace
target_namespace
local_file_path
mongo_saved
qdrant_saved
resource_count
helm_release_count
excluded_resource_count
warning_count
trace_ids
warnings
created_at
content, only when return_content is true
artifacts.human_mop_path
artifacts.agent_guide_path
```

Optional stores may fail without failing the run, but local storage failure must fail the request.

## 8. MCP Output Contract

MCP tool responses must be agent-readable and include:

- structured metadata fields matching the API response;
- concise human summary;
- artifact retrieval hints;
- warnings and unknowns;
- trace identifiers;
- no secret values.

## 9. Evidence Contract

Every generated step must be grounded by at least one of:

- PostgreSQL ETL snapshot evidence;
- ClickHouse analytical inventory evidence;
- Kubernetes Inspector MCP evidence;
- Helm Manager MCP evidence;
- Data Ingestion Agent evidence;
- application-mode metadata evidence;
- explicitly labeled inference with confidence and rationale.

Evidence references must appear in the appendix or inline where useful.

## 10. Safety Contract

The final MoP and generated snippets must not contain:

- Kubernetes Secret data or `stringData`;
- secret-like values from Helm values, environment variables, manifests, schemas, connection strings, or traces;
- production table rows, documents, messages, cache values, uploaded files, or business data;
- executable commands for blocked resource kinds;
- cluster-scoped mutation steps in v1.

Validation failure for secret leakage, blocked resources, or production data leakage must stop artifact publication.

## 11. Optional Index and Store Contracts

MongoDB, Qdrant, PostgreSQL metadata, ClickHouse metrics, Redis, pgvector, and LangMem are optional.

Optional persisted/indexed records must include:

- `mop_id`;
- `run_id`;
- `correlation_id`;
- source namespace;
- target namespace;
- generation mode;
- section name or artifact type;
- evidence references;
- trace identifiers where available.

Optional stores must receive redacted content only.
