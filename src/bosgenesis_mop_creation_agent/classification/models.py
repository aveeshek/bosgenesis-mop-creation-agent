from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from bosgenesis_mop_creation_agent.sources.snapshot_models import InventoryResource


class ResourceCategory(StrEnum):
    HELM_MANAGED = "helm_managed"
    RAW_K8S = "raw_k8s"
    EXCLUDED = "excluded"
    WARNING_ONLY = "warning_only"


class ClassifiedResource(BaseModel):
    resource: InventoryResource
    category: ResourceCategory
    reason: str
    evidence: list[str] = Field(default_factory=list)
    helm_release_name: str | None = None


class ClassificationSummary(BaseModel):
    namespace: str
    resources: list[ClassifiedResource] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @property
    def helm_managed(self) -> list[ClassifiedResource]:
        return self._by_category(ResourceCategory.HELM_MANAGED)

    @property
    def raw_k8s(self) -> list[ClassifiedResource]:
        return self._by_category(ResourceCategory.RAW_K8S)

    @property
    def excluded(self) -> list[ClassifiedResource]:
        return self._by_category(ResourceCategory.EXCLUDED)

    @property
    def warning_only(self) -> list[ClassifiedResource]:
        return self._by_category(ResourceCategory.WARNING_ONLY)

    @property
    def helm_managed_count(self) -> int:
        return len(self.helm_managed)

    @property
    def raw_k8s_count(self) -> int:
        return len(self.raw_k8s)

    @property
    def excluded_count(self) -> int:
        return len(self.excluded)

    @property
    def warning_only_count(self) -> int:
        return len(self.warning_only)

    def _by_category(self, category: ResourceCategory) -> list[ClassifiedResource]:
        return [item for item in self.resources if item.category == category]
