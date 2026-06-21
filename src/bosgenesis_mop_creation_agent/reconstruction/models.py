from __future__ import annotations

from pydantic import BaseModel, Field


class RawManifestPlan(BaseModel):
    kind: str
    name: str
    namespace: str
    file_path: str
    relative_path: str
    dry_run_command: str
    apply_command: str
    validation_command: str
    rollback_command: str
    evidence_ref: str
    warnings: list[str] = Field(default_factory=list)


class HelmReleasePlan(BaseModel):
    release_name: str
    chart_ref: str
    chart_version: str | None = None
    chart_source: str = "observed"
    repo_name: str | None = None
    repo_url: str | None = None
    credential_secret_ref: str | None = None
    values_file_path: str
    values_relative_path: str
    dry_run_command: str
    install_command: str
    validation_command: str
    rollback_command: str
    evidence_ref: str
    warnings: list[str] = Field(default_factory=list)


class ReconstructionPlan(BaseModel):
    target_namespace: str
    raw_manifests: list[RawManifestPlan] = Field(default_factory=list)
    helm_releases: list[HelmReleasePlan] = Field(default_factory=list)
    validation_commands: list[str] = Field(default_factory=list)
    rollback_commands: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @property
    def raw_manifest_count(self) -> int:
        return len(self.raw_manifests)

    @property
    def helm_release_count(self) -> int:
        return len(self.helm_releases)
