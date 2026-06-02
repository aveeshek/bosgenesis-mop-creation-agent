# Certificates Specification

## Intent

`certs/` is the local, non-committed certificate staging directory for external LLM access during development and deployment preparation.

## Allowed contents

This folder may contain local Azure/enterprise SSO certificate material required to authenticate or bootstrap LLM access, for example:

- `.cer`
- `.crt`
- `.pem`
- `.xml`
- local trust-bundle notes or exported public certificate metadata

## Safety rules

- Do not commit real certificate files.
- Do not commit private keys, client secrets, bearer tokens, refresh tokens, or credentials.
- Keep certificate files local or inject them through approved deployment secret/config mechanisms.
- Runtime code must prefer environment variables, mounted secrets, Azure CLI identity, or workload identity over hardcoded paths.
- LLM-generated repair content must never be treated as observed fact.

## Phase 6.2 LLM repair posture

The Phase 6.2 LLM repair layer must follow this authority order:

```text
Observed evidence > deterministic normalization > LLM suggestion > human fill-in
```

The LLM may propose executable repairs only when:

- evidence is strong;
- schema is known;
- confidence is high;
- output can be validated;
- generated content is clearly labeled.

Otherwise, the LLM must produce suggestion text and leave the executable field for human completion.
