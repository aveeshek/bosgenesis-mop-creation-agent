from datetime import datetime, timezone

from bosgenesis_mop_creation_agent.config.settings import LlmSettings
from bosgenesis_mop_creation_agent.llm.bounded_reasoning import build_bounded_reasoning
from bosgenesis_mop_creation_agent.models.requests import GenerationMode, MoPGenerationRequest
from bosgenesis_mop_creation_agent.reconstruction.models import ReconstructionPlan
from bosgenesis_mop_creation_agent.rendering.artifact_writer import LocalArtifactWriter
from bosgenesis_mop_creation_agent.retrieval.models import (
    ComponentIdentity,
    ReferenceCitation,
    ReferenceLookupResult,
)


class _FakeChatModel:
    def __init__(self, content: str) -> None:
        self.content = content
        self.prompt = ""

    def invoke(self, prompt: str):
        self.prompt = prompt
        return type("Response", (), {"content": self.content, "additional_kwargs": {}})()


class _SequenceChatModel:
    def __init__(self, contents: list[str]) -> None:
        self.contents = contents
        self.prompts: list[str] = []

    def invoke(self, prompt: str):
        self.prompts.append(prompt)
        content = self.contents.pop(0)
        return type("Response", (), {"content": content, "additional_kwargs": {}})()


def test_phase10_bounded_reasoning_is_disabled_by_default() -> None:
    result = build_bounded_reasoning(
        settings=LlmSettings(),
        reconstruction=ReconstructionPlan(
            target_namespace="target",
            warnings=["raw_manifest:Deployment/api:source_spec_missing"],
        ),
        classification=None,
        correlation_id="test",
    )

    assert result.enabled is False
    assert result.attempted is False
    assert result.status == "disabled"


def test_phase10_bounded_reasoning_skips_when_deterministic_evidence_is_sufficient() -> None:
    result = build_bounded_reasoning(
        settings=LlmSettings(reasoning_enabled=True),
        reconstruction=ReconstructionPlan(target_namespace="target"),
        classification=None,
        correlation_id="test",
    )

    assert result.enabled is True
    assert result.attempted is False
    assert result.status == "deterministic_sufficient"
    assert result.diagnostics.parse_status == "not_attempted_deterministic_sufficient"


def test_phase10_bounded_reasoning_returns_advisory_findings_only() -> None:
    model = _FakeChatModel(
        """
        {
          "findings": [
            {
              "focus_area": "helm_chart_public_repo_suggestion",
              "target": "HelmRelease/example",
              "finding": "Chart reference is missing but a prior MoP used a public chart.",
              "recommendation": "Ask the operator to confirm whether the public chart still applies.",
              "confidence": 0.91,
              "rationale": "The evidence shows a missing chart reference and a matching prior citation.",
              "evidence_refs": ["artifact.json#reconstruction.warnings"],
              "qdrant_refs": ["ref-1"],
              "required_human_inputs": ["Confirm chart repository and version"],
              "label": "llm_suggestion_requires_human_review",
              "authoritative": true,
              "executable_yaml_allowed": true
            },
            {
              "focus_area": "missing_manifest_spec",
              "target": "Deployment/api",
              "finding": "Spec is absent.",
              "recommendation": "Guess the container image.",
              "confidence": 0.40,
              "rationale": "Weak evidence.",
              "evidence_refs": [],
              "qdrant_refs": [],
              "required_human_inputs": [],
              "label": "llm_suggestion_requires_human_review",
              "authoritative": false,
              "executable_yaml_allowed": false
            }
          ]
        }
        """
    )
    references = ReferenceLookupResult(
        enabled=True,
        status="references_found",
        references=[
            ReferenceCitation(
                reference_id="ref-1",
                qdrant_collection="mop_installation_notes",
                source_mop_id="prior",
                component_identity=ComponentIdentity(kind="HelmRelease", name="example"),
                score=0.94,
                excerpt="Previously used public chart example/example.",
            )
        ],
    )

    result = build_bounded_reasoning(
        settings=LlmSettings(reasoning_enabled=True, minimum_confidence=0.85),
        reconstruction=ReconstructionPlan(
            target_namespace="target",
            warnings=["helm_release:example:chart_reference_unknown_or_unproven"],
        ),
        classification=None,
        correlation_id="test",
        prior_references=references,
        chat_model=model,
    )

    assert result.status == "generated"
    assert len(result.findings) == 1
    finding = result.findings[0]
    assert finding.label == "llm_suggestion_requires_human_review"
    assert finding.authoritative is False
    assert finding.executable_yaml_allowed is False
    assert result.diagnostics.accepted_count == 1
    assert result.diagnostics.rejected_low_confidence_count == 1
    assert "Do not output executable YAML" in model.prompt
    assert "Prior Qdrant references are examples only" in model.prompt


def test_phase10_bounded_reasoning_invalid_output_does_not_fail_generation() -> None:
    result = build_bounded_reasoning(
        settings=LlmSettings(reasoning_enabled=True),
        reconstruction=ReconstructionPlan(
            target_namespace="target",
            warnings=["raw_manifest:Deployment/api:source_spec_missing"],
        ),
        classification=None,
        correlation_id="test",
        chat_model=_FakeChatModel("review this manually"),
    )

    assert result.status == "invalid_structured_output"
    assert result.findings == []
    assert result.warnings == ["llm_reasoning_invalid_structured_output"]
    assert result.diagnostics.retry_attempted is True


def test_phase10_bounded_reasoning_repairs_json_fences_and_trailing_commas() -> None:
    result = build_bounded_reasoning(
        settings=LlmSettings(reasoning_enabled=True, minimum_confidence=0.85),
        reconstruction=ReconstructionPlan(
            target_namespace="target",
            warnings=["raw_manifest:Deployment/api:source_spec_missing"],
        ),
        classification=None,
        correlation_id="test",
        chat_model=_FakeChatModel(
            """
            ```json
            {
              "findings": [
                {
                  "focus_area": "missing_manifest_spec",
                  "target": "Deployment/api",
                  "finding": "Spec is absent.",
                  "recommendation": "Ask a human to provide the missing manifest spec.",
                  "confidence": 0.91,
                  "rationale": "The warning indicates source spec is missing.",
                  "evidence_refs": ["artifact.json#reconstruction.warnings"],
                  "qdrant_refs": [],
                  "required_human_inputs": ["missing Deployment/api spec"],
                  "label": "llm_suggestion_requires_human_review",
                  "authoritative": false,
                  "executable_yaml_allowed": false,
                },
              ],
            }
            ```
            """
        ),
    )

    assert result.status == "generated"
    assert result.diagnostics.parse_status == "valid_json_repaired"
    assert result.diagnostics.retry_attempted is False
    assert len(result.findings) == 1
    assert result.findings[0].authoritative is False


def test_phase10_bounded_reasoning_retries_once_after_invalid_json() -> None:
    model = _SequenceChatModel(
        [
            "review this manually",
            '{"findings": []}',
        ]
    )

    result = build_bounded_reasoning(
        settings=LlmSettings(reasoning_enabled=True, minimum_confidence=0.85),
        reconstruction=ReconstructionPlan(
            target_namespace="target",
            warnings=["raw_manifest:Deployment/api:source_spec_missing"],
        ),
        classification=None,
        correlation_id="test",
        chat_model=model,
    )

    assert result.status == "no_high_confidence_findings"
    assert result.warnings == []
    assert result.diagnostics.parse_status == "valid_json"
    assert result.diagnostics.retry_attempted is True
    assert len(model.prompts) == 2
    assert "Your last output was invalid JSON" in model.prompts[1]


def test_phase10_artifact_manifest_includes_bounded_reasoning(tmp_path) -> None:
    writer = LocalArtifactWriter(
        storage_path=str(tmp_path),
        llm_settings=LlmSettings(reasoning_enabled=True),
    )

    result = writer.write(
        mop_id="mop-1",
        run_id="run-1",
        correlation_id="corr-1",
        source_namespace="bosgenesis",
        request=MoPGenerationRequest(
            target_namespace="mirror",
            mode=GenerationMode.PLATFORM_ONLY,
        ),
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        warnings=[],
    )

    artifact_json = (tmp_path / "mop-1" / "artifact.json").read_text(encoding="utf-8")
    notes = result.installation_notes_content

    assert '"bounded_llm_reasoning"' in artifact_json
    assert "bounded_llm_reasoning_status" in notes
    assert "llm_output_authoritative: false" in notes
