# LangGraph Workflow Specification

## Intent

`langgraph/` defines standalone REST-triggered autonomous reasoning workflows using explicit graph state, nodes, transitions, critique loops, and repair loops.

## Responsibilities

- Own the standalone reasoning graph.
- Model state transitions between evidence preparation, prior reference lookup, planning, critique, repair, validation, and final plan acceptance.
- Call LangChain/model adapters where useful.
- Preserve deterministic-first behavior before LLM-assisted nodes.
- Support interruption-safe, traceable execution.

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
