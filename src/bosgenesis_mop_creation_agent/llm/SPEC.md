# LLM Specification

## Intent

`llm/` defines the external model integration boundary for standalone autonomous mode.

## Supported model profiles

The LLM boundary supports named model profiles selected by `llm.default_model`.
The initial supported profiles are:

- `gpt-4.1-mini` through Azure OpenAI.
- `gpt-5` through Azure OpenAI.
- `gemma4` through the namespace-local Ollama service.
- `llama70b` through the namespace-local Ollama service.

Azure OpenAI deployments are accessed through Azure CLI or workload identity.
Ollama models are accessed through configured in-cluster `base_url` values.

## Responsibilities

- Encapsulate model provider configuration.
- Resolve the active model from a named profile without requiring code changes.
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

If optional LLM reasoning is enabled and the model is unavailable, generation must still complete with deterministic artifacts and a warning. Model failure must not block MoP creation unless a future explicit policy changes this behavior.

## Phase 6.2 repair/suggestion layer

The Phase 6.2 repair layer is optional and disabled by default.

It must follow this authority order:

```text
Observed evidence > deterministic normalization > LLM suggestion > human fill-in
```

The LLM repair layer must not silently modify generated executable YAML. It may only
return clearly labeled suggestions with `executable_yaml_allowed=false`.

The repair response must validate against the strict `RepairSuggestionEnvelope`
Pydantic schema. The prompt must include the JSON schema and require JSON only:

```json
{
  "suggestions": [
    {
      "target_type": "raw_manifest",
      "target_name": "Deployment/example",
      "issue": "source_spec_missing",
      "suggestion": "Ask the owner to confirm replicas, selectors, and image.",
      "confidence": 0.91,
      "rationale": "Evidence is incomplete for executable YAML generation.",
      "evidence_refs": ["artifact.json#classification"]
    }
  ]
}
```

Suggestions are accepted only when:

- evidence is strong;
- schema is known;
- confidence is at or above the configured threshold;
- output can be validated;
- rationale and evidence references are present.

Otherwise, the agent must leave the gap for human completion.

The artifact must include LLM parser diagnostics so operators can distinguish:

- valid JSON with no suggestions;
- valid suggestions rejected below the confidence threshold;
- invalid JSON/prose/thinking text;
- JSON that fails the strict Pydantic schema.

For Ollama models, the parser may use response metadata or additional kwargs as
a parse-only fallback when `.content` is empty. Raw fallback text must never be
persisted in artifacts; only diagnostics such as response source, character
count, parse status, and rejection counts may be stored.

## Phase 10 bounded reasoning layer

The Phase 10 bounded reasoning layer is optional and controlled by
`llm.reasoning_enabled`. It uses LangGraph when available, with a direct
LangChain-compatible model fallback when the LangGraph package is unavailable.

It must follow this authority order:

```text
Observed evidence > deterministic reconstruction > Qdrant prior references > LLM suggestion > human approval
```

The layer may evaluate:

- ambiguity detection;
- Helm chart/public repository suggestions;
- install-order sanity;
- missing manifest/spec explanation;
- required human inputs;
- confidence and rationale labels.

The layer must receive only a redacted bounded evidence pack containing summary
counts, gap candidates, evidence references, redacted Qdrant citations, and
optional non-secret memory summaries. Memory context is prior run context only;
it is not current observed evidence. The layer must not receive raw Secret
values, production data, unredacted manifests, table rows, connection strings,
or credentials.

The response must validate against `ReasoningEnvelope`. Accepted findings must
be written only as advisory artifact metadata and rendered guidance:

- `label=llm_suggestion_requires_human_review`
- `authoritative=false`
- `executable_yaml_allowed=false`

The bounded reasoning layer must not:

- generate executable manifests as final truth;
- generate Helm commands without deterministic validation;
- mutate generated YAML;
- approve the final MoP.

When deterministic evidence has no candidate gaps, the layer may be skipped and
must report `deterministic_sufficient`. Low-confidence findings are rejected and
converted into diagnostics/human-review needs.

If the first bounded reasoning response is malformed, wrapped in markdown, or
contains repairable JSON formatting issues, the parser may extract or repair the
JSON for schema validation. If parsing still fails, the agent may make exactly
one deterministic retry with the same redacted evidence pack and an instruction
to return only `{"findings": []}` or valid `ReasoningEnvelope` JSON. The retry
must not include or persist the raw malformed response. If the retry also fails,
generation must continue with deterministic artifacts and an
`llm_reasoning_invalid_structured_output` warning.
