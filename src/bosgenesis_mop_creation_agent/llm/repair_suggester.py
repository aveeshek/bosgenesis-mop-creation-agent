from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from bosgenesis_mop_creation_agent.classification.models import ClassificationSummary
from bosgenesis_mop_creation_agent.config.settings import LlmSettings
from bosgenesis_mop_creation_agent.llm.model_gateway import ChatModel, build_chat_model
from bosgenesis_mop_creation_agent.llm.models import (
    RepairSuggestion,
    RepairSuggestionDiagnostics,
    RepairSuggestionEnvelope,
    RepairSuggestionResult,
)
from bosgenesis_mop_creation_agent.reconstruction.models import ReconstructionPlan
from bosgenesis_mop_creation_agent.retrieval.models import ReferenceLookupResult


MAX_CANDIDATES = 20


def build_repair_suggestions(
    *,
    settings: LlmSettings,
    reconstruction: ReconstructionPlan,
    classification: ClassificationSummary | None,
    correlation_id: str,
    prior_references: ReferenceLookupResult | None = None,
    chat_model: ChatModel | None = None,
) -> RepairSuggestionResult:
    diagnostics = RepairSuggestionDiagnostics(minimum_confidence=settings.minimum_confidence)
    if not settings.repair_suggestions_enabled:
        return RepairSuggestionResult(enabled=False, status="disabled", diagnostics=diagnostics)

    candidates = _repair_candidates(reconstruction, classification)
    diagnostics.candidate_count = len(candidates)
    if not candidates:
        diagnostics.parse_status = "not_attempted_no_candidates"
        return RepairSuggestionResult(
            enabled=True,
            attempted=False,
            status="no_candidates",
            diagnostics=diagnostics,
        )

    try:
        model = chat_model or build_chat_model(settings)
        response = model.invoke(
            _prompt(
                candidates,
                settings.minimum_confidence,
                correlation_id,
                prior_references,
            )
        )
        content, response_source = _extract_model_content(response)
        suggestions, diagnostics = _parse_suggestions(
            content,
            settings.minimum_confidence,
            candidate_count=len(candidates),
            response_source=response_source,
        )
    except Exception as exc:
        diagnostics.parse_status = "failed"
        return RepairSuggestionResult(
            enabled=True,
            attempted=True,
            status="failed",
            warnings=[f"llm_repair_suggestions_failed:{exc}"],
            diagnostics=diagnostics,
        )

    status = "generated"
    warnings = []
    if not suggestions:
        status = (
            "invalid_structured_output"
            if diagnostics.parse_status.startswith("invalid")
            else "no_high_confidence_suggestions"
        )
    if diagnostics.parse_status.startswith("invalid"):
        warnings.append("llm_repair_suggestions_invalid_structured_output")

    return RepairSuggestionResult(
        enabled=True,
        attempted=True,
        status=status,
        suggestions=suggestions,
        warnings=warnings,
        diagnostics=diagnostics,
    )


def _repair_candidates(
    reconstruction: ReconstructionPlan,
    classification: ClassificationSummary | None,
) -> list[dict[str, Any]]:
    candidates = []
    for warning in reconstruction.warnings:
        target_type, target_name, issue = _split_warning(warning)
        candidates.append(
            {
                "target_type": target_type,
                "target_name": target_name,
                "issue": issue,
                "evidence_refs": [],
            }
        )
    if classification:
        for item in classification.warning_only:
            if item.resource.kind == "Pod":
                continue
            candidates.append(
                {
                    "target_type": "warning_only_resource",
                    "target_name": f"{item.resource.kind}/{item.resource.name}",
                    "issue": item.reason,
                    "evidence_refs": item.evidence,
                }
            )
    return candidates[:MAX_CANDIDATES]


def _split_warning(warning: str) -> tuple[str, str, str]:
    parts = warning.split(":", 2)
    if len(parts) == 3:
        return parts[0], parts[1], parts[2]
    if len(parts) == 2:
        return parts[0], parts[1], "unspecified"
    return "general", warning, "unspecified"


def _prompt(
    candidates: list[dict[str, Any]],
    minimum_confidence: float,
    correlation_id: str,
    prior_references: ReferenceLookupResult | None,
) -> str:
    schema = RepairSuggestionEnvelope.model_json_schema()
    references = []
    if prior_references:
        references = [
            {
                "reference_id": item.reference_id,
                "source_mop_id": item.source_mop_id,
                "source_artifact_type": item.source_artifact_type,
                "component": item.component_identity.model_dump(mode="json"),
                "matched_fields": item.matched_fields,
                "score": item.score,
                "citation_label": item.citation_label,
                "excerpt": item.excerpt,
            }
            for item in prior_references.references[:5]
        ]
    return (
        "You are assisting BOS Genesis MoP generation as a suggestion-only repair layer.\n"
        "Authority order: Observed evidence > deterministic normalization > LLM suggestion > human fill-in.\n"
        "Prior Qdrant references are examples only. They are not current observed facts.\n"
        "Do not output executable YAML. Do not invent facts. Do not include secrets.\n"
        "Return JSON only. Do not return markdown, prose, code fences, or thinking text.\n"
        "Your response must validate against this JSON schema:\n"
        f"{json.dumps(schema, indent=2)}\n"
        f"Only include suggestions with confidence >= {minimum_confidence} when evidence is strong. "
        "Otherwise omit the candidate. If no suggestion is justified, return {\"suggestions\": []}.\n"
        "All suggestions require human review and executable_yaml_allowed must be false.\n"
        f"Correlation ID: {correlation_id}\n"
        f"Prior references:\n{json.dumps(references, indent=2)}\n"
        f"Candidates:\n{json.dumps(candidates, indent=2)}"
    )


def _parse_suggestions(
    content: str,
    minimum_confidence: float,
    *,
    candidate_count: int,
    response_source: str,
) -> tuple[list[RepairSuggestion], RepairSuggestionDiagnostics]:
    diagnostics = RepairSuggestionDiagnostics(
        candidate_count=candidate_count,
        response_chars=len(content),
        response_source=response_source,
        minimum_confidence=minimum_confidence,
    )
    payload, parse_status = _extract_json(content)
    diagnostics.parse_status = parse_status
    if payload is None:
        return [], diagnostics
    try:
        envelope = RepairSuggestionEnvelope.model_validate(payload)
    except ValidationError:
        diagnostics.parse_status = "invalid_schema"
        diagnostics.rejected_invalid_count = _count_raw_suggestions(payload)
        return [], diagnostics

    suggestions = []
    for suggestion in envelope.suggestions:
        suggestion.executable_yaml_allowed = False
        suggestion.label = "llm_suggestion_requires_human_review"
        if suggestion.confidence >= minimum_confidence:
            suggestions.append(suggestion)
        else:
            diagnostics.rejected_low_confidence_count += 1
    diagnostics.accepted_count = len(suggestions)
    return suggestions, diagnostics


def _extract_json(content: str) -> tuple[dict[str, Any] | None, str]:
    try:
        payload = json.loads(content)
        return payload if isinstance(payload, dict) else None, "valid_json"
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None, "invalid_no_json_object"
        try:
            payload = json.loads(content[start : end + 1])
            return payload if isinstance(payload, dict) else None, "valid_json_extracted"
        except json.JSONDecodeError:
            return None, "invalid_json"


def _count_raw_suggestions(payload: dict[str, Any]) -> int:
    raw = payload.get("suggestions")
    return len(raw) if isinstance(raw, list) else 0


def _extract_model_content(response: object) -> tuple[str, str]:
    content = getattr(response, "content", None)
    if content:
        return str(content), "content"

    for attr_name in ("additional_kwargs", "response_metadata"):
        payload = getattr(response, attr_name, None)
        content = _extract_content_from_mapping(payload)
        if content:
            return content, attr_name

    fallback = str(response)
    return fallback, "response_str" if fallback else "none"


def _extract_content_from_mapping(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""

    for key in ("content", "response", "text", "output"):
        value = payload.get(key)
        if value:
            return str(value)

    message = payload.get("message")
    if isinstance(message, dict):
        for key in ("content", "response", "text", "output", "thinking"):
            value = message.get(key)
            if value:
                return str(value)

    for key in ("thinking",):
        value = payload.get(key)
        if value:
            return str(value)
    return ""
