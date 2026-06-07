# MCP Clients Specification

## Intent

`mcp_clients/` wraps approved upstream MCP servers and is the live evidence boundary for Kubernetes, Helm, and data-ingestion context.

## Initial clients

- Kubernetes Inspector MCP client.
- Helm Manager MCP client.
- Data Ingestion Agent MCP client.

## Kubernetes Inspector use

Read/enrichment tools may include namespace summary, deployments, statefulsets, services, ingresses, PVCs, events, and bounded optional logs where policy allows.

When the Kubernetes Inspector MCP advertises `k8s_set_namespace`, the MoP agent
must call it before namespace summary, list, or detail enrichment tools. The
requested source namespace becomes the inspector's single active policy
namespace for that session. This prevents false policy denials such as reading
`signoz` while the inspector remains locked to `bosgenesis`, and it does not
permit cross-namespace reads.

## Helm Manager use

Read/enrichment tools may include release list, status, history, values, manifest, chart details, and template preview where policy allows.

## Data Ingestion use

Used for latest normalized/analytical evidence when exposed through MCP.

## Rules

- Use allowlisted read-only tools during MoP generation.
- Do not expose mutation tools to orchestration.
- Do not call raw `kubectl` or raw `helm`.
- Record request and response hashes for auditability.
- Preserve upstream tool names and correlation IDs where possible.
- Redact secret-like fields before evidence leaves the client layer.
- Represent unavailable MCP dependencies as warnings when policy permits fallback.
