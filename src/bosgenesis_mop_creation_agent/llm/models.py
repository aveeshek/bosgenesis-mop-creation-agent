from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RepairSuggestion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_type: str
    target_name: str
    issue: str
    suggestion: str
    confidence: float = 0.0
    rationale: str
    evidence_refs: list[str] = Field(default_factory=list)
    executable_yaml_allowed: bool = False
    label: str = "llm_suggestion_requires_human_review"

    @field_validator("confidence")
    @classmethod
    def confidence_must_be_probability(cls, value: float) -> float:
        if value < 0 or value > 1:
            raise ValueError("confidence must be between 0 and 1")
        return value


class RepairSuggestionEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suggestions: list[RepairSuggestion] = Field(default_factory=list)


class RepairSuggestionDiagnostics(BaseModel):
    candidate_count: int = 0
    response_chars: int = 0
    response_source: str = "none"
    parse_status: str = "not_attempted"
    accepted_count: int = 0
    rejected_low_confidence_count: int = 0
    rejected_invalid_count: int = 0
    minimum_confidence: float = 0.85


class RepairSuggestionResult(BaseModel):
    enabled: bool = False
    attempted: bool = False
    status: str = "disabled"
    authority_order: str = (
        "Observed evidence > deterministic normalization > LLM suggestion > human fill-in"
    )
    suggestions: list[RepairSuggestion] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    diagnostics: RepairSuggestionDiagnostics = Field(default_factory=RepairSuggestionDiagnostics)
