# Context Snapshot - BOS Genesis MoP Creation Agent

**Snapshot date:** 2026-06-02  
**Repository:** `C:\tmobile\genesis\agent-mop\bosgenesis-mop-creation-agent`  
**Remote:** `https://github.com/aveeshek/bosgenesis-mop-creation-agent.git`  
**Branch:** `main`  
**Latest committed phase:** Phase 8 - Markdown Installation Notes Renderer  
**Latest commit:** `2d69e25 Implement phase 8 markdown installation notes renderer`  
**Latest tag:** `phase08-markdown-installation-notes-renderer`  
**Working tree at snapshot creation:** clean before this snapshot file was added

## Product Intent

`bosgenesis-mop-creation-agent` is an on-demand, evidence-grounded agent that reads a single namespace inventory, enriches it through governed MCP servers, reasons about how the namespace was installed, and produces reconstruction artifacts.

The agent does not execute generated commands. It creates artifacts so a human or another LLM/agent can recreate a mirror namespace without copying production data.

Current v1 scope:

- one source namespace;
- namespace-only scope;
- Kubernetes and Helm based;
- public repositories only;
- no cluster-admin assumptions;
- no Secret value migration;
- no production data copy.

## Completed Milestones

- Phase 0: runtime foundation, FastAPI shell, health endpoint, config, logging, Docker, Helm/deploy scripts.
- Phase 1: REST and MCP contract.
- Phase 2: local artifact writer and valid empty artifact generation.
- Phase 3: PostgreSQL and ClickHouse snapshot readers with selection/fallback logic.
- Phase 4: governed MCP enrichment through K8s Inspector, Helm Manager, and related MCP boundaries.
- Phase 5: classification and safety for Helm-managed, raw Kubernetes, excluded, and warning-only resources.
- Phase 6: deterministic manifest and Helm reconstruction, target namespace rewrite, runtime metadata removal, command builders, validation/rollback command generation.
- Phase 6.1: deterministic K8s detail enrichment plus optional artifact preview.
- Phase 6.2: optional LLM repair/suggestion layer, confidence-gated and non-authoritative.
- Phase 8: machine-readable Markdown installation notes renderer, standalone YAML plan, full artifact download/archive APIs, housekeeping delete APIs, and docs/spec alignment.

Phase 7 production PDF renderer was intentionally skipped/deferred. The current PDF output is a valid placeholder for artifact/API contract stability.

## Current Output Model

A generated run writes under:

```text
/data/mops/<mop_id>/
```

Key artifacts:

- `artifact.json`
- `human-mop/*.md`
- `human-mop/*.pdf` placeholder
- `installation-notes/*.installation.md`
- `installation-notes/machine_execution_plan.yaml`
- `generated/*.yaml`
- `values/*.yaml`
- `evidence/*.json`

The Markdown installation notes include a canonical `machine_execution_plan` YAML block. The same plan is written as standalone YAML with YAML aliases disabled.

## Current REST Surface

Generation and retrieval:

```text
POST   /mop-creation/generate
GET    /mop-creation/{mop_id}
GET    /mop-creation/latest
GET    /mop-creation/{mop_id}/classification
GET    /config/effective
GET    /health
```

Artifact lifecycle:

```text
GET    /mop-creation/{mop_id}/artifacts
GET    /mop-creation/{mop_id}/artifacts/preview?path=<relative-path>
GET    /mop-creation/{mop_id}/artifacts/download?path=<relative-path>
GET    /mop-creation/{mop_id}/artifacts/archive?prefix=<relative-directory>
DELETE /mop-creation/{mop_id}
DELETE /mop-creation?confirm=true
```

Generation is asynchronous. `POST /mop-creation/generate` returns `accepted`; callers poll `GET /mop-creation/{mop_id}` until `generated` or `failed`.

## Current MCP Surface

Implemented MCP tools include:

```text
mop_creation_health
mop_creation_generate
mop_creation_get
mop_creation_latest
mop_creation_classification
mop_creation_artifacts
mop_creation_artifact_preview
mop_creation_effective_config
mop_creation_delete
mop_creation_delete_all
```

There is no built-in `mop_creation_refine` tool. Codex-driven refinement is external: Codex inspects artifacts, asks for another generation or code/doc update, and calls available tools again.

## LLM Policy

Authority order:

```text
Observed evidence > deterministic normalization > LLM suggestion > human fill-in
```

LLM repair/suggestion is optional and must never silently become executable fact. It may provide suggestions only when evidence is strong, schema is known, confidence is high, output can be validated, and the result is clearly labeled.

Supported model profile direction:

- default model should remain `gemma4:26b`;
- on-prem Ollama models include Gemma and Llama70B;
- Azure profiles may include GPT-4.1-mini and GPT-5.

Gemma tuning currently favors larger output capacity, with fallback extraction used only for parsing/diagnostics and not for storing raw fallback content.

## Important Safety Rules

- No raw `kubectl` or raw `helm` during generation.
- Live Kubernetes/Helm reads go through governed MCP servers.
- Secrets are excluded; secret-like values are redacted or represented as placeholders.
- Cluster-scoped resources are excluded.
- Runtime metadata and status fields are removed from generated manifests.
- Generated manifests must use only the target namespace.
- Artifact preview/download/archive/delete must stay under the configured artifact root.
- Bulk delete requires `confirm=true`.

## Validation State

Before the Phase 8 commit:

```text
python -m pytest
34 passed

python -m ruff check .
All checks passed
```

## Recently Updated Docs And Specs

Docs were aligned after Phase 8:

- `docs/SPEC.md`
- `docs/01_SPEC_MOP_CREATION_AGENT.md`
- `docs/02_HLD_MOP_CREATION_AGENT.md`
- `docs/03_LLD_MOP_CREATION_AGENT.md`
- `docs/04_ALGORITHM_MOP_CREATION_AGENT.md`
- `docs/05_OUTPUT_CONTRACTS.md`
- `docs/06_APPLICATION_MODE.md`
- `docs/07_SAMPLE_MOP_TEMPLATE.md`
- `docs/K8S_INSPECTOR_RESOURCE_DETAIL_ENRICHMENT_PLAN.md`

Python module `SPEC.md` files under `src/` were also reviewed and updated to match current implementation.

## Good Next Steps

Recommended next work:

1. Review the generated Markdown installation notes with another LLM/Codex instance and verify it can explain execution order from `machine_execution_plan`.
2. Manually dry-run selected generated Helm and raw Kubernetes commands from the notes.
3. Add stronger artifact lifecycle tests for path traversal and disallowed extension edge cases if not already comprehensive enough.
4. Decide whether Phase 7 production PDF rendering should be resumed or continue toward application-mode schema metadata.
5. If resuming Phase 7, implement a production PDF renderer from the sample-derived human MoP model, with layout verification and overflow checks.

## Operational Notes

The deployed ingress host used during testing was:

```text
http://mop-creation-agent.bosgenesis.local
```

Typical deploy validation flow:

```text
POST /mop-creation/generate
GET  /mop-creation/{mop_id}
GET  /mop-creation/{mop_id}/artifacts
GET  /mop-creation/{mop_id}/artifacts/download?path=installation-notes/<file>.installation.md
GET  /mop-creation/{mop_id}/artifacts/download?path=installation-notes/machine_execution_plan.yaml
GET  /mop-creation/{mop_id}/artifacts/archive?prefix=generated/
```

