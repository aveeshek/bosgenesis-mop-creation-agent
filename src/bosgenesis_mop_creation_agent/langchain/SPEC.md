# LangChain Workflow Specification

## Intent

`langchain/` defines standalone REST-triggered autonomous orchestration using LangChain.

Codex-integrated MCP mode may bypass this workflow because Codex provides the reasoning loop.

## Workflow stages

1. Build redacted evidence summary.
2. Retrieve relevant LangMem memory.
3. Classify installation mechanisms.
4. Build dependency graph.
5. Reason about gaps, unknowns, public repository/chart hints, and order.
6. Draft reasoning plan.
7. Critique plan against policy and evidence.
8. Repair plan when validation fails.
9. Return accepted reasoning plan to core orchestration.

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

Every LangChain step must be traceable in Langfuse and correlated with OpenTelemetry/SigNoz spans.

