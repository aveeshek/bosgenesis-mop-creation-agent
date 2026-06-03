from __future__ import annotations

import json
import logging
from typing import Any, TypedDict

from pydantic import ValidationError

from bosgenesis_mop_creation_agent.classification.models import ClassificationSummary
from bosgenesis_mop_creation_agent.config.settings import LlmSettings
from bosgenesis_mop_creation_agent.llm.model_gateway import ChatModel, build_chat_model
from bosgenesis_mop_creation_agent.llm.models import (
    BoundedReasoningResult,
    ReasoningDiagnostics,
    ReasoningEnvelope,
    ReasoningFinding,
)
from bosgenesis_mop_creation_agent.llm.repair_suggester import _extract_json, _extract_model_content
from bosgenesis_mop_creation_agent.reconstruction.models import ReconstructionPlan
from bosgenesis_mop_creation_agent.retrieval.models import ReferenceLookupResult


MAX_REASONING_CANDIDATES = 24
LOGGER = logging.getLogger(__name__)


def build_bounded_reasoning(
    *,
    settings: LlmSettings,
    reconstruction: ReconstructionPlan,
    classification: ClassificationSummary | None,
    correlation_id: str,
    prior_references: ReferenceLookupResult | None = None,
    chat_model: ChatModel | None = None,
) -> BoundedReasoningResult:
    diagnostics = ReasoningDiagnostics(minimum_confidence=settings.minimum_confidence)
    if not settings.reasoning_enabled:
        return BoundedReasoningResult(enabled=False, status="disabled", diagnostics=diagnostics)

    evidence_pack = _redacted_evidence_pack(reconstruction, classification, prior_references)
    candidates = evidence_pack["candidates"]
    diagnostics.candidate_count = len(candidates)
    if not candidates:
        diagnostics.parse_status = "not_attempted_deterministic_sufficient"
        LOGGER.info(
            "llm_reasoning_skipped",
            extra={
                "correlation_id": correlation_id,
                "phase": "llm_reasoning",
                "status": "deterministic_sufficient",
                "candidate_count": 0,
            },
        )
        return BoundedReasoningResult(
            enabled=True,
            attempted=False,
            status="deterministic_sufficient",
            diagnostics=diagnostics,
        )

    prompt = _prompt(evidence_pack, settings.minimum_confidence, correlation_id)
    diagnostics.prompt_chars = len(prompt)
    LOGGER.info(
        "llm_reasoning_started",
        extra={
            "correlation_id": correlation_id,
            "phase": "llm_reasoning",
            "candidate_count": len(candidates),
            "redacted_prompt": True,
            "model_profile": settings.default_model,
        },
    )
    try:
        model = chat_model or build_chat_model(settings)
        content, response_source, langgraph_used = _invoke_with_optional_langgraph(model, prompt)
        findings, diagnostics = _parse_findings(
            content,
            settings.minimum_confidence,
            candidate_count=len(candidates),
            prompt_chars=len(prompt),
            response_source=response_source,
            langgraph_used=langgraph_used,
        )
    except Exception as exc:
        diagnostics.parse_status = "failed"
        LOGGER.warning(
            "llm_reasoning_failed",
            extra={
                "correlation_id": correlation_id,
                "phase": "llm_reasoning",
                "status": "failed",
                "error": str(exc),
                "redacted_prompt": True,
            },
        )
        return BoundedReasoningResult(
            enabled=True,
            attempted=True,
            status="failed",
            warnings=[f"llm_reasoning_failed:{exc}"],
            diagnostics=diagnostics,
        )

    status = "generated"
    warnings = []
    if not findings:
        status = (
            "invalid_structured_output"
            if diagnostics.parse_status.startswith("invalid")
            else "no_high_confidence_findings"
        )
    if diagnostics.parse_status.startswith("invalid"):
        warnings.append("llm_reasoning_invalid_structured_output")

    LOGGER.info(
        "llm_reasoning_completed",
        extra={
            "correlation_id": correlation_id,
            "phase": "llm_reasoning",
            "status": status,
            "candidate_count": diagnostics.candidate_count,
            "accepted_count": diagnostics.accepted_count,
            "rejected_low_confidence_count": diagnostics.rejected_low_confidence_count,
            "parse_status": diagnostics.parse_status,
            "langgraph_used": diagnostics.langgraph_used,
            "redacted_prompt": True,
        },
    )
    return BoundedReasoningResult(
        enabled=True,
        attempted=True,
        status=status,
        findings=findings,
        warnings=warnings,
        diagnostics=diagnostics,
    )


def _redacted_evidence_pack(
    reconstruction: ReconstructionPlan,
    classification: ClassificationSummary | None,
    prior_references: ReferenceLookupResult | None,
) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for warning in reconstruction.warnings:
        candidates.append(
            {
                "focus_area": "missing_manifest_or_helm_gap",
                "target": warning.split(":", 2)[1] if ":" in warning else warning,
                "issue": warning,
                "evidence_refs": ["artifact.json#reconstruction.warnings"],
            }
        )
    for release in reconstruction.helm_releases:
        if release.chart_ref.startswith("<"):
            candidates.append(
                {
                    "focus_area": "helm_chart_public_repo_suggestion",
                    "target": f"HelmRelease/{release.release_name}",
                    "issue": "chart_reference_unknown_or_unproven",
                    "evidence_refs": [f"values/{release.values_relative_path}"],
                }
            )
    if classification:
        for item in classification.warning_only:
            if item.resource.kind == "Pod":
                continue
            candidates.append(
                {
                    "focus_area": "warning_only_resource_manual_note",
                    "target": f"{item.resource.kind}/{item.resource.name}",
                    "issue": item.reason,
                    "evidence_refs": item.evidence,
                }
            )

    references = []
    if prior_references:
        references = [
            {
                "reference_id": reference.reference_id,
                "component": (
                    f"{reference.component_identity.kind}/"
                    f"{reference.component_identity.name}"
                ),
                "source_mop_id": reference.source_mop_id,
                "score": reference.score,
                "citation_label": reference.citation_label,
                "excerpt": reference.excerpt[:500],
            }
            for reference in prior_references.references[:5]
        ]

    return {
        "scope": {
            "namespace_only": True,
            "public_repositories_only": True,
            "no_secret_values": True,
            "no_production_data": True,
            "llm_output_authoritative": False,
        },
        "summary": {
            "raw_manifest_count": reconstruction.raw_manifest_count,
            "helm_release_count": reconstruction.helm_release_count,
            "warning_count": len(reconstruction.warnings)
            + (classification.warning_only_count if classification else 0),
        },
        "candidates": candidates[:MAX_REASONING_CANDIDATES],
        "prior_references": references,
    }


def _prompt(evidence_pack: dict[str, Any], minimum_confidence: float, correlation_id: str) -> str:
    schema = ReasoningEnvelope.model_json_schema()
    return (
        "You are the bounded reasoning and gap-analysis layer for BOS Genesis MoP generation.\n"
        "You are not a source of truth and must not approve the MoP.\n"
        "Authority order: Observed evidence > deterministic reconstruction > Qdrant prior references > "
        "LLM suggestion > human approval.\n"
        "Prior Qdrant references are examples only. They are not current observed facts.\n"
        "Do not output executable YAML, kubectl manifests, Helm commands, secrets, or credentials.\n"
        "Return JSON only. Do not return markdown, prose, code fences, or thinking text.\n"
        "Focus on ambiguity detection, public Helm chart hints, install-order sanity, missing spec "
        "explanations, required human inputs, confidence, and rationale.\n"
        f"Only include findings with confidence >= {minimum_confidence}. "
        "If deterministic evidence is sufficient or confidence is low, return {\"findings\": []}.\n"
        "Every finding must keep label=llm_suggestion_requires_human_review, "
        "authoritative=false, executable_yaml_allowed=false.\n"
        f"Your response must validate against this JSON schema:\n{json.dumps(schema, indent=2)}\n"
        f"Correlation ID: {correlation_id}\n"
        f"Redacted evidence pack:\n{json.dumps(evidence_pack, indent=2)}"
    )


class _GraphState(TypedDict):
    prompt: str
    response: object | None


def _invoke_with_optional_langgraph(model: ChatModel, prompt: str) -> tuple[str, str, bool]:
    try:
        from langgraph.graph import END, StateGraph
    except ImportError:
        response = model.invoke(prompt)
        content, response_source = _extract_model_content(response)
        return content, response_source, False

    def call_model(state: _GraphState) -> _GraphState:
        return {"prompt": state["prompt"], "response": model.invoke(state["prompt"])}

    graph = StateGraph(_GraphState)
    graph.add_node("call_model", call_model)
    graph.set_entry_point("call_model")
    graph.add_edge("call_model", END)
    compiled = graph.compile()
    output = compiled.invoke({"prompt": prompt, "response": None})
    response = output["response"]
    content, response_source = _extract_model_content(response)
    return content, response_source, True


def _parse_findings(
    content: str,
    minimum_confidence: float,
    *,
    candidate_count: int,
    prompt_chars: int,
    response_source: str,
    langgraph_used: bool,
) -> tuple[list[ReasoningFinding], ReasoningDiagnostics]:
    diagnostics = ReasoningDiagnostics(
        candidate_count=candidate_count,
        prompt_chars=prompt_chars,
        response_chars=len(content),
        response_source=response_source,
        minimum_confidence=minimum_confidence,
        langgraph_used=langgraph_used,
    )
    payload, parse_status = _extract_json(content)
    diagnostics.parse_status = parse_status
    if payload is None:
        return [], diagnostics
    try:
        envelope = ReasoningEnvelope.model_validate(payload)
    except ValidationError:
        diagnostics.parse_status = "invalid_schema"
        diagnostics.rejected_invalid_count = _count_raw_findings(payload)
        return [], diagnostics

    findings = []
    for finding in envelope.findings:
        finding.label = "llm_suggestion_requires_human_review"
        finding.authoritative = False
        finding.executable_yaml_allowed = False
        if finding.confidence >= minimum_confidence:
            findings.append(finding)
        else:
            diagnostics.rejected_low_confidence_count += 1
    diagnostics.accepted_count = len(findings)
    return findings, diagnostics


def _count_raw_findings(payload: dict[str, Any]) -> int:
    raw = payload.get("findings")
    return len(raw) if isinstance(raw, list) else 0
