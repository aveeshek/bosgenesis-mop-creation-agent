# Project Structure Specification

## Intent

The repository mirrors the spec-driven layout of `bosgenesis-k8s-data-ingestion-agent`, adapted for non-deterministic MoP creation, evidence-grounded reasoning, document generation, and agentic memory.

## Top-level layout

- `src/`: future Python package module contracts.
- `config/`: non-secret runtime configuration specifications.
- `deploy/`: raw Kubernetes deployment specification structure.
- `charts/`: Helm chart specification structure.
- `tests/`: future unit, policy, contract, and evaluation test strategy.
- `docs/`: project specification, design, algorithm, and MoP output contracts.
- `codex/`: Codex MCP integration guidance and iterative refinement prompts.
- `knowledge-base/`: durable design knowledge, inferred installation patterns, schemas, and decisions.
- `memory/`: LangMem and backing memory-store contracts.
- `playbook/`: operator deployment, validation, and rollback procedure specifications.
- `skills/`: future Codex/agent skill definitions.
- `artifacts/`: generated MoP PDF and Markdown installation notes artifact contracts.
- `evaluations/`: future quality, grounding, reproducibility, and safety evaluation specs.

## No-code constraint

Every folder in this initial scaffold contains a `SPEC.md` file. All initial files are Markdown specifications only.
