# BOS Genesis MoP Creation Agent - High Level Design

**Document status:** Initial scaffold  
**Agent name:** `bosgenesis-mop-creation-agent`  
**Primary mode:** On-demand only  
**Default source namespace:** `bosgenesis` from configuration  
**Target namespace:** Provided at runtime  
**Primary purpose:** Generate a human-executable Method of Procedure (MoP) and an LLM/agent-readable installation guide that can recreate or mimic BOS Genesis namespace resources into a target namespace using copyable commands and structured autonomous-execution instructions.

The agent is not an executor. It creates a safe, line-by-line MoP with commands, expected outputs, validation checkpoints, rollback notes, and execution log sections. It also creates an agent-readable Markdown guide for autonomous execution by another LLM/agent. It uses the latest inventory captured by the Analytical MoP ETL Agent and enriches it, when needed, through the existing Helm MCP and Kubernetes Inspector MCP.

The agent is non-deterministic by design. In Codex-integrated MCP mode, Codex can drive iterative reasoning and call the agent repeatedly to refine output. In standalone REST mode, the agent uses LangChain, GPT-4.1 mini or configured equivalent, and LangMem-backed memory to reason about ambiguous next steps.

## 1. High-Level Architecture

```mermaid
flowchart LR
    Caller["Codex / LLM / BOS AI Studio / n8n"] --> API["MoP Creation Agent API"]
    Codex["Codex MCP Client"] --> MCP["On-demand MCP Endpoint"]
    MCP --> Orchestrator["MoP Creation Orchestrator"]
    API --> Orchestrator

    Orchestrator --> Snapshot["Latest ETL Snapshot Reader"]
    Snapshot --> PG[("PostgreSQL Inventory")]
    Snapshot --> CH[("ClickHouse Inventory")]

    Orchestrator --> K8S["K8s Inspector MCP"]
    Orchestrator --> HELM["Helm Manager MCP"]
    K8S --> KAPI["Kubernetes API"]
    HELM --> HCLI["Helm CLI"]
    HCLI --> KAPI

    Orchestrator --> Classifier["Resource Classifier"]
    Orchestrator --> Reasoning["Reasoning Layer"]
    Reasoning --> LangChain["LangChain Standalone Flow"]
    LangChain --> LLM["External LLM: GPT-4.1 mini"]
    Classifier --> Reasoning
    Reasoning --> Normalizer["Manifest Normalizer"]
    Normalizer --> Renderer["MoP and Guide Renderer"]

    Renderer --> Local[("Local File Storage")]
    Renderer --> Mongo[("MongoDB MoP Store")]
    Renderer --> Qdrant[("Qdrant MoP Index")]

    Orchestrator --> Obs["Observability Adapter"]
    Obs --> Langfuse["Langfuse"]
    Obs --> SigNoz["SigNoz / OTel"]

    Orchestrator --> Memory["Memory Layer"]
    Memory --> Redis[("Redis Optional")]
    Memory --> PGV[("pgvector Optional")]
    Memory --> LangMem["LangMem Optional"]
    Memory -. "disabled" .-> Letta["Letta Future Adapter"]
```

## 2. Responsibility Split

| Layer | Responsibility |
|---|---|
| API Layer | Accept on-demand generation requests and return file metadata/content. |
| MCP Layer | Expose on-demand Codex tools for generation, refinement, retrieval, and configuration inspection. |
| Orchestrator | Coordinate snapshot read, MCP enrichment, classification, normalization, rendering, persistence, tracing, and response shaping. |
| Snapshot Reader | Read latest Analytical MoP ETL Agent data from PostgreSQL and ClickHouse. |
| K8s MCP Client | Validate live Kubernetes resource state using the existing K8s Inspector MCP. |
| Helm MCP Client | Validate Helm releases, values, manifests, and history using the existing Helm MCP. |
| Resource Classifier | Split resources into Helm-managed, raw Kubernetes, excluded, and warning-only categories. |
| Manifest Normalizer | Remove runtime metadata, redact sensitive fields, and rewrite namespace references for the target namespace. |
| Reasoning Layer | Use deterministic rules first, then LLM reasoning for ambiguous installation order, missing public repo/chart details, values reconstruction, unknowns, and application-mode metadata guidance. |
| MoP and Guide Renderer | Generate final human MoP and agent-readable Markdown guide. |
| Persistence Layer | Save to local file, MongoDB, Qdrant, and metadata stores when enabled. |
| Observability Layer | Emit Langfuse and SigNoz traces, structured logs, and generation metrics. |
| Memory Layer | Save and retrieve generation patterns, previous MoPs, template decisions, short-term run state, episodic memory, and knowledge memory. |

## 3. End-to-End Flow

```mermaid
sequenceDiagram
    participant C as Caller/Codex
    participant A as MoP Creation Agent
    participant PG as PostgreSQL
    participant CH as ClickHouse
    participant K as K8s MCP
    participant H as Helm MCP
    participant M as MongoDB/Qdrant
    participant O as Langfuse/SigNoz

    C->>A: POST /mop-creation/generate target_namespace
    A->>O: start trace
    A->>PG: read latest source namespace snapshot
    A->>CH: read analytical inventory if enabled
    A->>K: validate latest namespace summary/resources
    A->>H: read Helm releases, values, manifests, history
    A->>A: classify resources
    A->>A: normalize manifests and rewrite target namespace
    A->>A: reason over install order, unknowns, and public repo/chart evidence
    A->>A: generate Markdown MoP and agent-readable guide
    A->>A: write local file
    A->>M: save MoP and index chunks if enabled
    A->>O: end trace
    A-->>C: return file path, metadata, and optional content
```

## 4. Runtime and Generation Modes

Runtime invocation:

- Codex-integrated MCP mode: Codex drives iterative generation, critique, and refinement.
- Standalone REST mode: REST trigger starts an autonomous LangChain flow using GPT-4.1 mini or a configured equivalent model.

Generation:

- `platform-only`: Kubernetes and Helm resources only.
- `application`: platform-only plus metadata-only schema/topology guidance for PostgreSQL, ClickHouse, Redis, MongoDB, Kafka, and similar approved targets.

## 5. Existing MCP Integration

### Kubernetes Inspector MCP

Used for namespace summary, pods, deployments, statefulsets, services, ingresses, PVCs, events, and optional bounded logs.

The MoP Creation Agent must use this MCP as the live Kubernetes validation boundary. It must not call raw `kubectl` while generating the MoP.

### Helm Manager MCP

Used for release list, release status, release history, values, manifests, chart details, and optional template preview.

The MoP Creation Agent must use this MCP as the Helm validation boundary. It must not call raw `helm` while generating the MoP.

### Analytical MoP ETL Agent

The latest ETL snapshot is the preferred starting point for inventory. MCP enrichment should be used to validate, fill gaps, or resolve ambiguity when snapshot data is incomplete or stale.

## 6. Resource Categorization

```mermaid
flowchart TB
    R["Resource Inventory"] --> Managed{"Has Helm metadata?"}
    Managed -->|"Yes"| HelmManaged["Helm-managed resource"]
    Managed -->|"No"| Raw["Raw Kubernetes resource"]

    HelmManaged --> HSection["Generate Helm recreation section"]
    Raw --> Safe{"Safe supported kind?"}
    Safe -->|"Yes"| KSection["Generate kubectl apply section"]
    Safe -->|"No"| Excluded["Excluded / manual note"]

    HSection --> MoP["Final MoP"]
    KSection --> MoP
    Excluded --> MoP
```

## 7. Deployment View

```mermaid
flowchart TB
    subgraph BOS["Namespace: bosgenesis"]
        API["MoP Creation Agent API"]
        PVC[("Local MoP PVC")]
        K8S["K8s Inspector MCP"]
        HELM["Helm Manager MCP"]
        PG[("PostgreSQL")]
        CH[("ClickHouse")]
        MG[("MongoDB")]
        QD[("Qdrant")]
        LF["Langfuse"]
        SZ["SigNoz"]
    end

    API --> PVC
    API --> K8S
    API --> HELM
    API --> PG
    API --> CH
    API --> MG
    API --> QD
    API --> LF
    API --> SZ
```

## 8. Data Stores

| Store | Purpose |
|---|---|
| Local file storage | Required output MoP file. |
| PostgreSQL | Read ETL latest snapshot and store request metadata when enabled. |
| ClickHouse | Read analytical inventory and write generation metrics when enabled. |
| MongoDB | Store full MoP document and raw generation trace. |
| Qdrant | Store MoP chunks for future retrieval and analytics. |
| Redis | Optional short-lived cache and idempotency lock. |
| pgvector | Optional semantic search alternative. |
| LangMem | Optional memory extraction/update around MoP patterns. |
| Letta | Future disabled adapter and future memory-layer option. |

## 9. Observability Model

```mermaid
flowchart LR
    Request["Generate MoP Request"] --> Trace["Trace Context"]
    Trace --> S1["read_latest_snapshot"]
    Trace --> S2["enrich_from_mcp"]
    Trace --> S3["classify_resources"]
    Trace --> S4["normalize_manifests"]
    Trace --> S5["render_mop"]
    Trace --> S6["persist_mop"]
    Trace --> S7["return_response"]

    S1 --> LF["Langfuse"]
    S2 --> LF
    S3 --> LF
    S4 --> LF
    S5 --> LF
    S6 --> LF
    S7 --> LF

    S1 --> SZ["SigNoz"]
    S2 --> SZ
    S3 --> SZ
    S4 --> SZ
    S5 --> SZ
    S6 --> SZ
    S7 --> SZ
```

## 10. Safety Boundaries

- The agent generates procedures; it does not execute them.
- Source namespace defaults to `bosgenesis` and must come from configuration.
- Target namespace is supplied at runtime and appears in generated commands and normalized manifests.
- v1 is single-namespace, namespace-only, Kubernetes/Helm based, and public-repository only.
- Secret values must never be copied into generated MoPs. Secret creation steps must use placeholders or references to pre-existing secret material.
- Runtime metadata, status fields, UIDs, resource versions, managed fields, pod names, and other non-recreatable state must be removed from generated manifests.
- Excluded or unsafe resources must be documented as manual notes rather than converted into executable commands.
- Agent-readable guides must not contain production data and must distinguish observed facts from inferred guidance.
