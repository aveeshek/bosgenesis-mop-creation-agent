from enum import StrEnum

from pydantic import BaseModel, Field


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


class QdrantIngestMoPRequest(BaseModel):
    mop_id: str
    caller: str = "api"
    confirm: bool = False
