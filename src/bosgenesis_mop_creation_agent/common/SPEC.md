# Common Utilities Specification

## Intent

`common/` contains shared utilities that do not own business logic.

## Future modules

- `errors.py`
- `ids.py`
- `time.py`
- `logging.py`

## Responsibilities

- Stable ID generation for `mop_id`, `run_id`, and `correlation_id`.
- Timestamp helpers.
- Shared exception types.
- Structured logging helpers.
- Safe redaction wrappers for common log fields.

## Rules

Common utilities must remain dependency-light and must not call upstream MCP servers, LLMs, persistence stores, or rendering logic directly.

## Safety

Common logging helpers must default to redacted output.

