# Samples Specification

## Intent

`samples/` contains copy-pasteable non-secret request bodies and examples for
operators, Postman, curl, and release-candidate validation.

## Rules

- Samples must not contain real credentials.
- Samples must use safe target namespaces.
- Application-mode samples must state that Phase 15 treats application mode as a
  deferred/human-review metadata contract, not executable schema recreation.
