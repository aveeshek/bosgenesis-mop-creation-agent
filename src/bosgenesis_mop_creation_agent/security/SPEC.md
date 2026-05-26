# Security Specification

## Intent

`security/` defines policy, redaction, and credential-handling contracts.

## V1 policy

- One source namespace only.
- Namespace-only Kubernetes scope.
- Kubernetes and Helm based reconstruction.
- Public repositories only.
- No cluster-scoped migration.
- No RBAC migration unless later policy allows it.
- No command execution by this agent.

## Redaction rules

No secret values may appear in:

- logs;
- memory;
- prompts;
- traces;
- artifacts;
- evidence bundles passed to LLM;
- optional stores;
- API/MCP responses.

## Blocked content

- Kubernetes Secret data and `stringData`.
- Secret-like environment values.
- Inline credentials.
- Tokens.
- Passwords.
- Private keys.
- Connection strings with credentials.
- SQL rows.
- MongoDB documents.
- Kafka messages.
- Redis values.

## Credential handling

Credentials for application mode must be read-only, explicit, redacted, and never persisted as plaintext.

## Policy failures

Policy violations fail the run before artifact publication.

