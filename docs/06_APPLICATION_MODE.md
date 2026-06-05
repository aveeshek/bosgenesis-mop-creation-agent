# Application Mode Specification

**Document status:** Deferred/backlog; Phase 12 skipped for now
**Generation mode:** `application`

## 1. Intent

Application mode is a deferred/backlog generation mode. It is not part of the current active implementation plan because Phase 12 is intentionally skipped for now. When reactivated, it will augment `platform-only` Kubernetes and Helm reconstruction with metadata-only schema and topology inference for databases, caches, brokers, and application-level dependencies.

When reactivated, application mode remains a document-generation mode. The agent does not execute schema creation, copy data, mutate target systems, or perform migrations.

When this backlog mode is reactivated, standalone application-mode reasoning may use LangGraph/LangChain and the configured external LLM to infer schema/topology recreation guidance from redacted evidence. In Codex-integrated mode, Codex may iteratively refine the same guidance through the MCP surface.

## 2. Scope

Future application mode includes:

- all `platform-only` output;
- schema/topology discovery where approved evidence is available;
- metadata-only recreation instructions;
- metadata-only sections in both the human MoP artifacts and the Markdown installation notes;
- validation commands or checks;
- manual rollback guidance.

Future application mode excludes:

- table rows;
- MongoDB documents;
- Kafka messages;
- Redis values;
- uploaded files;
- business records;
- credential extraction;
- live mutation of application systems.

## 3. Supported Initial Targets

| Target | In scope | Out of scope |
|---|---|---|
| PostgreSQL | Schemas, tables, indexes, views, extensions, roles as placeholders where safe, grants as guidance. | Table rows, passwords, live migrations, destructive DDL execution. |
| ClickHouse | Databases, tables, engines, materialized views, dictionaries, indexes where discoverable. | Table data, credentials, cluster-wide mutation. |
| MongoDB | Database names, collection names, indexes, validation/schema shape where discoverable. | Documents, sample data, credentials. |
| Redis | Keyspace pattern summary, DB index usage, TTL policy hints, stream/group names where safe. | Key values, cached payloads, tokens, session data. |
| Kafka | Brokers, topic names, partitions, replication factor, configs, consumer group references where safe. | Messages, offsets as data migration, credentials. |

## 4. Evidence Sources

Future application-mode evidence may come from:

- explicitly provided read-only credentials;
- approved MCP/data-ingestion boundaries;
- Qdrant prior MoP/installation-note references for matching application components, when available;
- PostgreSQL/ClickHouse/MongoDB/Redis/Kafka metadata collectors in future implementation;
- ETL snapshot or analytical inventory when it already contains redacted metadata.

The agent must prefer approved MCP or data-ingestion boundaries when available. Direct datastore access requires explicit read-only credentials and redaction controls.

Qdrant references are optional prior guidance only. They may help explain how a component was previously installed, but they cannot replace direct metadata evidence for schema/topology output.

## 5. Credential Handling

Credentials must:

- be provided explicitly for the run or through approved secret configuration;
- be scoped to metadata/read-only access;
- be redacted from logs, traces, prompts, memory, stores, and artifacts;
- never be persisted as plaintext;
- never be rendered into the MoP.

If credentials are missing or insufficient, the agent must generate a warning and either skip the affected application-mode target or mark it as requiring human-provided schema input.

## 6. Collection Algorithm

```text
if mode == "application":
    run platform-only evidence flow first
    discover enabled application metadata targets
    for each target:
        verify read-only access or approved MCP boundary
        collect metadata only
        redact secret-like values
        normalize schema/topology into output contract
        create recreation steps and validation checks
        add warnings for unknowns or insufficient permissions
    if deterministic metadata is incomplete and LLM reasoning is enabled:
        request bounded advisory suggestions from redacted evidence and prior Qdrant references
        validate structured output and confidence threshold
        label accepted suggestions as llm_suggestion_requires_human_review
        never generate executable DDL, broker commands, or cache commands as final truth
```

When reactivated, application metadata collection must happen after namespace/platform classification so the agent can associate schemas and topics with Kubernetes workloads where evidence supports that relationship.

## 7. Output Requirements

When application mode is reactivated, generated human MoP artifacts and Markdown installation notes must include application schema/topology recreation guidance when application mode is selected. In the human MoP content this guidance belongs under `Deployment Execution`, `Validation`, `Go / No-Go`, and `Rollback Procedure` as appropriate; in the Markdown notes it may be a dedicated execution phase and must be represented in the machine execution plan when it is actionable.

That section must include:

- target type;
- evidence source;
- confidence level;
- schema/topology summary;
- recreation command or pseudocode blocks when safe;
- validation checks;
- rollback guidance;
- unknowns and required human inputs.
- evidence references and inference labels.

If a schema/topology item is inferred from Kubernetes configuration rather than directly observed, it must be labeled as inferred.

## 8. Safety Rules

- Never output data values.
- Never output credential values.
- Never include connection strings with embedded credentials.
- Never include Redis values, Kafka messages, MongoDB documents, or SQL table rows.
- Never execute generated DDL or broker commands.
- Redact secret-like values before sending evidence to any LLM or memory backend.
- Store only non-secret schema/topology summaries in LangMem or optional memory stores.
- Fail artifact validation if production data or secret-like values appear in generated content.

## 9. Failure and Degradation Behavior

| Condition | Behavior |
|---|---|
| Application credentials missing | Skip affected target and add warning. |
| Collector unavailable | Continue platform-only output and add warning. |
| Permission denied | Document unavailable metadata and required read-only permission. |
| Secret-like value detected | Fail artifact publication until redacted. |
| Data rows/messages/documents detected | Fail artifact publication until removed. |
| Incomplete metadata | Render partial schema/topology with confidence and unknowns. |

## 10. Validation Requirements

Future application-mode validation must check:

- no production data in artifacts;
- no secret-like values in artifacts;
- schema/topology sections are metadata-only;
- unknowns are listed explicitly;
- commands are marked as manual execution guidance;
- rollback guidance defaults to human review for destructive schema/topic cleanup.

## 11. Future Extensions

- Approved MCP servers for PostgreSQL, ClickHouse, MongoDB, Redis, and Kafka.
- Stronger schema diffing against a target namespace.
- Policy-as-code checks for generated DDL and broker commands.
- Quality scoring for schema completeness and evidence grounding.
