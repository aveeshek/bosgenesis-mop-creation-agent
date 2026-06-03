from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ComponentIdentity(BaseModel):
    kind: str
    name: str
    namespace: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)
    helm_release_name: str | None = None
    helm_chart_name: str | None = None
    helm_chart_version: str | None = None
    image_repositories: list[str] = Field(default_factory=list)
    service_names: list[str] = Field(default_factory=list)
    ingress_hosts: list[str] = Field(default_factory=list)


class ComponentQuery(BaseModel):
    query_id: str
    component: ComponentIdentity
    query_text: str
    exact_terms: list[str] = Field(default_factory=list)


class ReferenceCitation(BaseModel):
    reference_id: str
    qdrant_collection: str
    source_mop_id: str | None = None
    source_artifact_type: str | None = None
    source_namespace: str | None = None
    component_identity: ComponentIdentity
    matched_fields: list[str] = Field(default_factory=list)
    score: float
    citation_label: str = "prior_reference_only_not_current_fact"
    confidence: str = "medium"
    redaction_status: str = "redacted"
    excerpt: str = ""


class ReferenceLookupResult(BaseModel):
    enabled: bool = False
    status: str = "disabled"
    references: list[ReferenceCitation] = Field(default_factory=list)
    queries: list[ComponentQuery] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @property
    def reference_count(self) -> int:
        return len(self.references)

    def citation_ids(self) -> list[str]:
        return [item.reference_id for item in self.references]


class QdrantPointPayload(BaseModel):
    point_id: str
    payload: dict[str, Any]

