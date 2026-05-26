# LangChain Adapter Specification

## Intent

`langchain/` defines model, prompt, and tool adapter helpers used by standalone reasoning.

LangGraph owns the standalone workflow graph, state transitions, critique loops, and repair loops. LangChain should be used where it provides useful model/tool abstractions, not as the only orchestration layer.

Codex-integrated MCP mode may bypass these adapters when Codex provides the reasoning loop.

## Adapter responsibilities

1. Build prompt inputs from redacted evidence.
2. Call the configured model gateway.
3. Wrap tool/model calls for LangGraph nodes.
4. Normalize model outputs.
5. Return structured outputs to the LangGraph workflow.

## Inputs

- Redacted evidence bundle.
- Resource classifications.
- Generation mode.
- Requested output artifacts.
- Memory context.
- Scope and safety constraints.

## Outputs

- Reasoning plan.
- Dependency graph.
- Inference labels and confidence.
- Unknowns and required human inputs.
- Validation notes.

## Traceability

Every LangChain-backed model/tool call must be traceable in Langfuse and correlated with OpenTelemetry/SigNoz spans.
