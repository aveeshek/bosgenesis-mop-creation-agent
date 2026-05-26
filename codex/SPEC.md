# Codex Integration Specification

## Intent

`codex/` defines how Codex should call and refine the MoP Creation Agent through MCP.

## Workflow

Codex may call the agent repeatedly to:

- collect evidence;
- request initial MoP generation;
- critique missing steps;
- refine document ordering;
- retrieve artifacts;
- validate safety and grounding.

## Safety

Codex must not request raw Kubernetes, Helm, or database access for this workflow when an MCP boundary exists.

