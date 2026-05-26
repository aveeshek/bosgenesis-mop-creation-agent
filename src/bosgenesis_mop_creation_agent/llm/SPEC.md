# LLM Specification

## Intent

`llm/` defines the external model integration boundary for standalone autonomous mode.

## Initial target

- GPT-4.1 mini, or configured equivalent model.

## Responsibilities

- Encapsulate model provider configuration.
- Accept only redacted prompt inputs.
- Return schema-constrained reasoning outputs where possible.
- Distinguish observed facts, inferred facts, confidence, rationale, and unknowns.
- Emit Langfuse traces for prompts, generations, and validation metadata.
- Preserve `run_id` and `correlation_id`.

## Prompt contract

Prompts must include:

- source and target namespace;
- v1 scope constraints;
- public-repository-only constraint;
- no-secret and no-production-data constraints;
- evidence citations;
- requested output schema.

## Prohibited behavior

The LLM boundary must not receive:

- secret values;
- production data;
- unredacted connection strings;
- raw credentials;
- table rows, documents, messages, or cache values.

## Failure behavior

If standalone mode requires LLM reasoning and the model is unavailable, the run fails unless deterministic-only fallback is explicitly enabled.

