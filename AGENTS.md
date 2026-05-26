# AGENTS.md - BOS Genesis MoP Creation Agent

## Project purpose

This repository will implement `bosgenesis-mop-creation-agent`, a non-deterministic, LLM-assisted agent that inspects one BOS Genesis Kubernetes namespace through existing MCP servers, reasons about how the namespace was installed, and generates reproducible Method of Procedure documents.

The agent must produce:

- a human-readable MoP suitable for manual copy-and-execute installation;
- an LLM/agent-readable Markdown installation guide suitable for autonomous execution by another agent.

## Hard safety rules

- Operate inside the configured namespace only. The default namespace is `bosgenesis`.
- Use existing BOS Genesis MCP servers for Kubernetes, Helm, and data/component inspection.
- Never call raw `kubectl`, raw `helm`, database CLIs, or broker CLIs from the agent runtime unless a future approved MCP boundary explicitly allows it.
- Never mutate Kubernetes, Helm, databases, streams, or application resources while generating a MoP.
- Never collect, reveal, or persist secret values.
- Secrets may be referenced only by name, key shape, expected existence, or placeholder instructions.
- Every tool call, reasoning step, document decision, and generated artifact must have a `run_id`, `correlation_id`, trace context, and structured audit event.
- LLM output must be grounded in collected evidence and marked when inferred.
- Generated installation guides must recreate structure and configuration without copying production data.

## Required root folders

- `codex`
- `knowledge-base`
- `memory`
- `playbook`
- `skills`

## Initial development posture

This scaffold intentionally contains specification files only. Future implementation code, Helm templates, Kubernetes manifests, scripts, and dependency manifests should be added only after these module contracts are reviewed and accepted.

