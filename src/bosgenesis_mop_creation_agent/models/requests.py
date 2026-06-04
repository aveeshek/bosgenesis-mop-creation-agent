from enum import StrEnum
import re

from pydantic import BaseModel, Field, field_validator


class GenerationMode(StrEnum):
    PLATFORM_ONLY = "platform-only"
    APPLICATION = "application"


class OutputArtifact(StrEnum):
    HUMAN_MOP_PDF = "human_mop_pdf"
    INSTALLATION_NOTES = "installation_notes"


class MoPGenerationRequest(BaseModel):
    source_namespace: str | None = None
    target_namespace: str
    source_snapshot_id: str = "latest"
    mode: GenerationMode = GenerationMode.PLATFORM_ONLY
    include_helm: bool = True
    include_raw_k8s: bool = True
    include_validation_steps: bool = True
    include_rollback_steps: bool = True
    include_application_schema: bool = False
    output_artifacts: list[OutputArtifact] = Field(
        default_factory=lambda: [
            OutputArtifact.HUMAN_MOP_PDF,
            OutputArtifact.INSTALLATION_NOTES,
        ]
    )
    return_content: bool = False
    caller: str = "api"
    correlation_id: str | None = None


class NamespaceSwitchRequest(BaseModel):
    namespace: str
    caller: str = "api"

    @field_validator("namespace")
    @classmethod
    def validate_namespace(cls, value: str) -> str:
        namespace = value.strip()
        if not re.fullmatch(r"[a-z0-9]([-a-z0-9]*[a-z0-9])?", namespace):
            raise ValueError("namespace must be a Kubernetes RFC1123 label")
        if len(namespace) > 63:
            raise ValueError("namespace must be 63 characters or fewer")
        return namespace


class QdrantIngestMoPRequest(BaseModel):
    mop_id: str
    caller: str = "api"
    confirm: bool = False
