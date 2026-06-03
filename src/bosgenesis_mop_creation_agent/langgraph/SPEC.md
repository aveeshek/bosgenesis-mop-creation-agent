# LangGraph Workflow Specification

## Intent

`langgraph/` defines standalone REST-triggered autonomous reasoning workflows using explicit graph state, nodes, transitions, critique loops, and repair loops.

## Responsibilities

- Own the standalone reasoning graph.
- Model state transitions between evidence preparation, prior reference lookup, planning, critique, repair, validation, and final plan acceptance.
- Call LangChain/model adapters where useful.
- Preserve deterministic-first behavior before LLM-assisted nodes.
- Support interruption-safe, traceable execution.

## Current bounded graph

Phase 10 introduces a bounded one-node LangGraph flow for optional LLM reasoning
when deterministic reconstruction has candidate gaps. The graph input is a
redacted evidence pack plus prior Qdrant citations. The graph output is parsed
through a strict Pydantic schema and stored as advisory findings only.

If LangGraph is not installed or cannot be imported, the same prompt may be sent
through the configured LangChain-compatible model gateway without failing the
generation run.

## Future graph nodes

- `prepare_evidence`
- `load_memory_context`
- `build_initial_plan`
- `apply_qdrant_references`
- `llm_reasoning`
- `policy_critique`
- `repair_plan`
- `final_validation`
- `return_reasoning_plan`

## Safety

Graph state must contain redacted evidence only. Secret values, production data, and unredacted credentials must never enter graph state, prompts, traces, memory, or rendered artifacts.
