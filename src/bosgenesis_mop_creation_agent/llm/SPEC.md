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

If standalone mode requires LLM reasoning and the model is unavailable, the run fails unless deterministic-only fallback is explicitly enabled.

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
