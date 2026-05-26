# Redis Memory Specification

## Intent

Redis may hold short-term run state, locks, cache entries, and progress markers.

## Boundary

Redis memory must not contain secret values or production data.

