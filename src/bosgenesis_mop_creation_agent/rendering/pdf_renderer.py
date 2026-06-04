from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


PAGE_WIDTH = 612
PAGE_HEIGHT = 792
DEFAULT_TEMPLATE_PATH = Path("artifacts/human-mop/professional_mop_pdf_template.yaml")


@dataclass(frozen=True)
class PdfRenderMetadata:
    renderer: str = "phase7_professional_pdf_renderer"
    page_count: int = 0
    section_order: list[str] = field(default_factory=list)
    overflow_count: int = 0
    generated_from: str = "professional_mop_pdf_template"
    template_id: str = "bosgenesis_professional_mop_pdf"
    template_version: str = "1.0"

    def model_dump(self) -> dict[str, object]:
        return {
            "renderer": self.renderer,
            "page_count": self.page_count,
            "section_order": self.section_order,
            "overflow_count": self.overflow_count,
            "generated_from": self.generated_from,
            "template_id": self.template_id,
            "template_version": self.template_version,
        }


@dataclass(frozen=True)
class PdfRenderResult:
    path: str
    metadata: PdfRenderMetadata


@dataclass
class _Page:
    commands: list[str] = field(default_factory=list)


@dataclass
class _RenderState:
    template: dict[str, Any]
    pages: list[_Page] = field(default_factory=list)
    y: float = 0
    overflow_count: int = 0
    current_section: str = ""

    @property
    def page(self) -> _Page:
        return self.pages[-1]

    @property
    def margin_left(self) -> float:
        return float(self.template["page"].get("margin_left", 44))

    @property
    def margin_right(self) -> float:
        return float(self.template["page"].get("margin_right", 44))

    @property
    def margin_top(self) -> float:
        return float(self.template["page"].get("margin_top", 48))

    @property
    def margin_bottom(self) -> float:
        return float(self.template["page"].get("margin_bottom", 48))

    @property
    def content_width(self) -> float:
        return PAGE_WIDTH - self.margin_left - self.margin_right


def render_human_mop_pdf(
    markdown_content: str,
    output_path: Path,
    *,
    context: dict[str, Any] | None = None,
    template_path: Path = DEFAULT_TEMPLATE_PATH,
) -> PdfRenderResult:
    """Render a professional, template-driven MoP PDF.

    `markdown_content` remains accepted for compatibility and fallback text extraction,
    but the professional renderer primarily uses the resolved generation context.
    """

    template = _load_template(template_path)
    render_context = dict(context or {})
    if "mop_title" not in render_context:
        render_context["mop_title"] = _extract_markdown_title(markdown_content)
    render_context["markdown_section_order"] = _extract_markdown_sections(markdown_content)

    state = _RenderState(template=template)
    _render_cover(state, render_context)
    for section in template["sections"][1:]:
        _start_section_page(state, section["number"], section["title"])
        _dispatch_section(state, section, render_context)

    total_pages = len(state.pages)
    for page_number, page in enumerate(state.pages, 1):
        _render_footer(state, page, page_number, total_pages)

    output_path.write_bytes(_build_pdf(state.pages))
    return PdfRenderResult(
        path=str(output_path),
        metadata=PdfRenderMetadata(
            page_count=total_pages,
            section_order=[section["title"] for section in template["sections"]],
            overflow_count=state.overflow_count,
            template_id=str(template.get("template_id", "bosgenesis_professional_mop_pdf")),
            template_version=str(template.get("template_version", "1.0")),
        ),
    )


def _load_template(path: Path) -> dict[str, Any]:
    if path.exists():
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    else:
        data = {}
    data.setdefault("template_id", "bosgenesis_professional_mop_pdf")
    data.setdefault("template_version", "1.0")
    data.setdefault("page", {})
    data.setdefault("theme", {})
    data.setdefault(
        "sections",
        [
            {"number": 1, "title": "Title and Cover Page", "renderer": "cover"},
            {"number": 2, "title": "Executive Summary", "renderer": "executive_summary"},
        ],
    )
    theme = data["theme"]
    defaults = {
        "primary": "0.05 0.18 0.32",
        "secondary": "0.00 0.43 0.62",
        "accent": "0.00 0.63 0.72",
        "success": "0.00 0.48 0.33",
        "warning": "0.95 0.55 0.12",
        "danger": "0.72 0.12 0.18",
        "light": "0.94 0.97 0.98",
        "panel": "0.98 0.99 1.00",
        "border": "0.76 0.84 0.88",
        "text": "0.10 0.14 0.18",
        "muted": "0.39 0.45 0.50",
    }
    for key, value in defaults.items():
        theme.setdefault(key, value)
    return data


def _render_cover(state: _RenderState, context: dict[str, Any]) -> None:
    state.pages.append(_Page())
    theme = state.template["theme"]
    _rect(state.page, 0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=theme["primary"])
    _rect(state.page, 0, 0, PAGE_WIDTH, 155, fill=theme["secondary"])
    _rect(state.page, 0, 155, PAGE_WIDTH, 12, fill=theme["accent"])
    _circle(state.page, 530, 700, 78, fill="0.08 0.27 0.43")
    _circle(state.page, 475, 662, 42, fill="0.00 0.63 0.72")

    _text(state.page, 56, 675, "BOS GENESIS", "F2", 16, color="1 1 1")
    _text(state.page, 56, 635, "Method of Procedure", "F2", 34, color="1 1 1")
    _text(state.page, 58, 607, _value(context, "mop_title"), "F1", 14, color="0.86 0.95 1")
    _text(state.page, 58, 560, "Namespace recreation package", "F2", 13, color="1 1 1")
    _text(
        state.page,
        58,
        540,
        f"{_value(context, 'source_namespace')}  ->  {_value(context, 'target_namespace')}",
        "F1",
        12,
        color="0.84 0.94 0.98",
    )

    cards = [
        ("Helm Releases", _value(context, "helm_release_count", "0"), theme["accent"]),
        ("Raw K8s", _value(context, "raw_k8s_resource_count", "0"), theme["success"]),
        ("Excluded", _value(context, "excluded_resource_count", "0"), theme["warning"]),
        ("Warnings", _value(context, "warning_count", "0"), theme["danger"]),
    ]
    x = 58
    for label, value, color in cards:
        _metric_card(state.page, x, 420, 112, 70, label, value, color)
        x += 122

    _cover_detail(state.page, 58, 315, "MOP ID", _value(context, "mop_id"))
    _cover_detail(state.page, 58, 286, "RUN ID", _value(context, "run_id"))
    _cover_detail(state.page, 58, 257, "CORRELATION ID", _value(context, "correlation_id"))
    _cover_detail(state.page, 58, 228, "GENERATED", _value(context, "generated_at"))
    _cover_detail(state.page, 58, 199, "MODE", _value(context, "generation_mode"))

    _text(state.page, 58, 92, "Human review required before execution", "F2", 12, color="1 1 1")
    _text(
        state.page,
        58,
        72,
        "No secret values or production data are copied by this document.",
        "F1",
        9.5,
        color="0.88 0.95 0.98",
    )


def _start_section_page(state: _RenderState, number: int, title: str) -> None:
    state.pages.append(_Page())
    state.current_section = title
    theme = state.template["theme"]
    _rect(state.page, 0, PAGE_HEIGHT - 86, PAGE_WIDTH, 86, fill=theme["primary"])
    _rect(state.page, 0, PAGE_HEIGHT - 91, PAGE_WIDTH, 5, fill=theme["accent"])
    _text(state.page, state.margin_left, PAGE_HEIGHT - 38, f"{number:02d}", "F2", 22, color=theme["accent"])
    _text(state.page, state.margin_left + 48, PAGE_HEIGHT - 35, title, "F2", 16, color="1 1 1")
    state.y = PAGE_HEIGHT - 118


def _dispatch_section(state: _RenderState, section: dict[str, Any], context: dict[str, Any]) -> None:
    renderer = section.get("renderer")
    if renderer == "executive_summary":
        _section_executive_summary(state, context)
    elif renderer == "analytical_summary":
        _section_analytical_summary(state, context)
    elif renderer == "document_quality":
        _section_document_quality(state, context)
    elif renderer == "scope_controls":
        _section_scope_controls(state, context)
    elif renderer == "platform_inventory":
        _section_platform_inventory(state, context)
    elif renderer == "topology_view":
        _section_topology_view(state, context)
    elif renderer == "dependency_map":
        _section_dependency_map(state, context)
    elif renderer == "operator_plan":
        _section_operator_plan(state, context)
    elif renderer == "command_patterns":
        _section_command_patterns(state, context)
    elif renderer == "controls":
        _section_controls(state, context)
    elif renderer == "validation_matrix":
        _section_validation_matrix(state, context)
    elif renderer == "appendix_resources":
        _section_appendix_resources(state, context)
    else:
        _paragraph(state, "Section renderer is not configured for this template entry.")


def _section_executive_summary(state: _RenderState, context: dict[str, Any]) -> None:
    _lead(
        state,
        "This MoP recreates the platform footprint of a single Kubernetes namespace using "
        "observed snapshot, governed MCP enrichment, deterministic reconstruction, and "
        "advisory-only reasoning where gaps remain.",
    )
    _two_column_cards(
        state,
        [
            ("Change Objective", _value(context, "change_reason")),
            ("Operating Mode", f"{_value(context, 'generation_mode')} / namespace-only / public repositories"),
            ("Target Namespace", _value(context, "target_namespace")),
            ("Human Approval", "Required before any mutating command is executed."),
        ],
    )
    _subheading(state, "Key Warnings")
    _bullets(state, _split_summary(_value(context, "warning_summary", "No warnings recorded."), limit=6))


def _section_analytical_summary(state: _RenderState, context: dict[str, Any]) -> None:
    theme = state.template["theme"]
    cards = [
        ("Helm Releases", _value(context, "helm_release_count", "0"), theme["accent"]),
        ("Raw Kubernetes", _value(context, "raw_k8s_resource_count", "0"), theme["success"]),
        ("Application Targets", _value(context, "application_target_count", "0"), theme["secondary"]),
        ("Excluded", _value(context, "excluded_resource_count", "0"), theme["warning"]),
    ]
    _metric_grid(state, cards)
    _subheading(state, "Analytical Lens")
    _table(
        state,
        ["Dimension", "Observed Value", "Interpretation"],
        [
            ["Source snapshot", _value(context, "source_snapshot_id_or_timestamp"), "Primary inventory anchor."],
            ["Qdrant references", _value(context, "qdrant_reference_count", "0"), _value(context, "qdrant_lookup_status")],
            ["Warnings", _value(context, "warning_count", "0"), "Requires operator review before execution."],
            ["Target namespace", _value(context, "target_namespace"), "All commands are rewritten to this namespace."],
        ],
    )


def _section_document_quality(state: _RenderState, context: dict[str, Any]) -> None:
    _paragraph(
        state,
        "Document quality is assessed from required section coverage, evidence traceability, "
        "secret exclusion, advisory reasoning labels, and command safety controls.",
    )
    _table(
        state,
        ["Quality Gate", "Status", "Evidence"],
        [
            ["Required sections", "Present", "Template-driven professional section order."],
            ["Secret handling", "Controlled", "Secret values are placeholders and not copied."],
            ["LLM authority", "Advisory only", _value(context, "inference_labels_and_rationale", "No advisory output.")[:90]],
            ["Dry-run posture", "Required", "Command patterns include dry-run before mutation."],
            ["Rollback", "Documented", "Rollback controls and namespace cleanup guidance are included."],
        ],
    )


def _section_scope_controls(state: _RenderState, context: dict[str, Any]) -> None:
    _two_column_cards(
        state,
        [
            ("Scope", "Single namespace, namespace-only resources, Kubernetes and Helm based."),
            ("Source Evidence", _value(context, "evidence_references", "Snapshot and MCP evidence.")),
            ("Controls", "No cluster-admin scope, no Secret value copy, no production data migration."),
            ("Public Repositories", "Helm/chart references must be public or manually confirmed."),
        ],
    )
    _subheading(state, "Human Inputs")
    _code_block(state, _value(context, "required_human_inputs_yaml", "  []"))


def _section_platform_inventory(state: _RenderState, context: dict[str, Any]) -> None:
    _paragraph(state, "The platform engineer lens summarizes what will be recreated and what is intentionally excluded.")
    _table(
        state,
        ["Inventory Class", "Count", "Notes"],
        [
            ["Helm-managed releases", _value(context, "helm_release_count", "0"), _value(context, "helm_release_summary")],
            ["Raw Kubernetes resources", _value(context, "raw_k8s_resource_count", "0"), _value(context, "raw_k8s_summary")],
            ["Application metadata", _value(context, "application_target_count", "0"), _value(context, "application_summary")],
            ["Excluded resources", _value(context, "excluded_resource_count", "0"), _value(context, "excluded_summary")],
        ],
    )


def _section_topology_view(state: _RenderState, context: dict[str, Any]) -> None:
    _diagram_flow(
        state,
        [
            f"Source namespace\\n{_value(context, 'source_namespace')}",
            "Snapshot + MCP\\nEvidence",
            "Classifier +\\nNormalizer",
            f"Target namespace\\n{_value(context, 'target_namespace')}",
        ],
    )
    _subheading(state, "Topology Notes")
    _bullets(
        state,
        [
            "Helm-managed resources are recreated through Helm command patterns when chart evidence is available.",
            "Raw Kubernetes resources are normalized, namespace-rewritten, and applied with dry-run first.",
            "Runtime artifacts such as Pods and Events are not recreated as desired state.",
        ],
    )


def _section_dependency_map(state: _RenderState, context: dict[str, Any]) -> None:
    _phase_map(
        state,
        [
            "Verify Access",
            "Target Namespace",
            "Secret Placeholders",
            "ConfigMaps / PVCs",
            "Helm Releases",
            "Raw Kubernetes",
            "Ingress",
            "Validation",
        ],
    )
    _paragraph(
        state,
        "This ordering keeps namespace creation and sensitive manual inputs ahead of workload mutation, "
        "then validates after ingress and service-level resources are present.",
    )


def _section_operator_plan(state: _RenderState, context: dict[str, Any]) -> None:
    _table(
        state,
        ["Phase", "Operator Action", "Approval"],
        [
            ["1", "Verify artifact bundle and target context.", "No mutation."],
            ["2", "Prepare target namespace.", "Approval required if namespace is created."],
            ["3", "Create required secret placeholders from approved sources.", "Mandatory human input."],
            ["4", "Run dry-runs for Helm and raw Kubernetes resources.", "Review output."],
            ["5", "Apply/install after dry-runs pass.", "Human approval required."],
            ["6", "Run validation and go/no-go checks.", "Record evidence."],
        ],
    )


def _section_command_patterns(state: _RenderState, context: dict[str, Any]) -> None:
    steps = _execution_steps_from_plan(_value(context, "machine_execution_plan_yaml", ""))
    if not steps:
        _paragraph(
            state,
            "No executable command steps were generated. Review the installation notes and "
            "artifact manifest before attempting namespace recreation.",
        )
        return

    _paragraph(
        state,
        "Execute these commands in order. Commands marked as mutating require explicit human "
        "approval after the corresponding dry-run or context check succeeds.",
    )
    for index, step in enumerate(steps, start=1):
        _render_execution_step(state, index, step)


def _section_controls(state: _RenderState, context: dict[str, Any]) -> None:
    _table(
        state,
        ["Checkpoint", "Expected Result", "Action if Failed"],
        [
            ["Artifact bundle", "All required files exist.", "STOP and regenerate."],
            ["Secret placeholders", "Approved values supplied manually.", "STOP and resolve inputs."],
            ["Helm dry-runs", "No template/render errors.", "Fix chart or values."],
            ["Kubectl dry-runs", "Server accepts manifests.", "Fix generated YAML."],
            ["Workload health", "Replicas ready and endpoints populated.", "Rollback or investigate."],
        ],
    )
    _subheading(state, "Rollback Triggers")
    _bullets(state, _split_summary(_value(context, "rollback_trigger_conditions_yaml"), limit=5))


def _section_validation_matrix(state: _RenderState, context: dict[str, Any]) -> None:
    _table(
        state,
        ["Evidence Source", "Status", "Reference"],
        [
            ["Kubernetes MCP", _value(context, "k8s_mcp_status"), "Namespace resource snapshot and detail enrichment."],
            ["Helm MCP", _value(context, "helm_mcp_status"), "Release list, values, manifests, status, and history."],
            ["Data ingestion", _value(context, "data_ingestion_status"), "Latest stored ETL snapshot selection."],
            ["Qdrant prior references", _value(context, "qdrant_lookup_status"), f"count={_value(context, 'qdrant_reference_count')}"],
        ],
    )
    _subheading(state, "Copy-Paste Validation Steps")
    validation_steps = _validation_steps_from_plan(_value(context, "machine_execution_plan_yaml", ""))
    if not validation_steps:
        validation_steps = [
            {
                "title": "Validate recreated namespace resources",
                "commands": [{"kind": "check", "command": _value(context, "validation_commands_yaml")}],
                "expected_outcomes": [_value(context, "validation_expected_outcomes_yaml")],
            }
        ]
    for index, step in enumerate(validation_steps, start=1):
        _render_validation_step(state, index, step)


def _section_appendix_resources(state: _RenderState, context: dict[str, Any]) -> None:
    snapshot = context.get("professional_resource_snapshot") or {}
    helm_releases = snapshot.get("helm_releases") or []
    resources_by_kind = snapshot.get("resources_by_kind") or {}
    excluded = snapshot.get("excluded_resources") or []

    _subheading(state, f"Helm Releases ({len(helm_releases)})")
    _resource_table(
        state,
        ["Release", "Namespace", "Chart", "Status"],
        [
            [
                release.get("release_name", ""),
                release.get("namespace", ""),
                _join_non_empty(
                    release.get("chart_name", ""),
                    release.get("chart_version", ""),
                    separator=":",
                ),
                release.get("status", ""),
            ]
            for release in helm_releases
        ],
    )

    preferred_order = [
        "Deployment",
        "StatefulSet",
        "DaemonSet",
        "Service",
        "Ingress",
        "ConfigMap",
        "PersistentVolumeClaim",
        "Job",
        "CronJob",
        "Pod",
    ]
    remaining_kinds = sorted(kind for kind in resources_by_kind if kind not in preferred_order)
    for kind in [*preferred_order, *remaining_kinds]:
        rows = resources_by_kind.get(kind) or []
        if not rows:
            continue
        _subheading(state, f"{kind} Resources ({len(rows)})")
        _resource_table(
            state,
            ["Name", "Namespace", "Status", "Classification"],
            [
                [
                    row.get("name", ""),
                    row.get("namespace", ""),
                    row.get("status", ""),
                    row.get("category", ""),
                ]
                for row in rows
            ],
        )

    _subheading(state, f"Excluded Resources ({len(excluded)})")
    _resource_table(
        state,
        ["Kind", "Name", "Namespace", "Reason"],
        [
            [
                row.get("kind", ""),
                row.get("name", ""),
                row.get("namespace", ""),
                row.get("reason", ""),
            ]
            for row in excluded
        ],
    )


def _execution_steps_from_plan(value: str) -> list[dict[str, Any]]:
    try:
        parsed = yaml.safe_load(value) or {}
    except yaml.YAMLError:
        return []
    plan = parsed.get("machine_execution_plan") if isinstance(parsed, dict) else {}
    phases = plan.get("phases") if isinstance(plan, dict) else []
    if not isinstance(phases, list):
        return []
    steps: list[dict[str, Any]] = []
    for phase in phases:
        if not isinstance(phase, dict):
            continue
        phase_id = str(phase.get("phase_id") or "")
        for step in phase.get("steps") or []:
            if not isinstance(step, dict):
                continue
            commands = step.get("commands") or []
            if not commands:
                continue
            normalized_commands = []
            for command in commands:
                if isinstance(command, dict) and command.get("command"):
                    normalized_commands.append(
                        {
                            "kind": str(command.get("kind") or "command"),
                            "command": str(command.get("command")),
                        }
                    )
                elif isinstance(command, str):
                    normalized_commands.append({"kind": "command", "command": command})
            if normalized_commands:
                steps.append({**step, "phase_id": step.get("phase_id") or phase_id, "commands": normalized_commands})
    return steps


def _validation_steps_from_plan(value: str) -> list[dict[str, Any]]:
    return [
        step
        for step in _execution_steps_from_plan(value)
        if str(step.get("phase_id") or "").lower() == "validate"
        or str(step.get("type") or "").lower() == "validation"
    ]


def _render_execution_step(state: _RenderState, index: int, step: dict[str, Any]) -> None:
    title = str(step.get("title") or step.get("step_id") or "Execution step")
    phase_id = str(step.get("phase_id") or "unknown_phase")
    step_id = str(step.get("step_id") or f"step-{index}")
    _subheading(state, f"{index}. {title}")
    _table(
        state,
        ["Phase", "Step ID", "Mutates", "Approval"],
        [
            [
                phase_id,
                step_id,
                _bool_label(step.get("mutates_target")),
                _bool_label(step.get("requires_human_approval")),
            ]
        ],
    )
    for command_index, command in enumerate(step.get("commands") or [], start=1):
        _paragraph(state, f"Command {command_index} - {command.get('kind', 'command')}", size=8.4)
        _code_block(state, str(command.get("command") or ""), max_lines=None)
    expected = step.get("expected_outcomes") or []
    if expected:
        _paragraph(state, "Expected outcome:", size=8.4)
        _bullets(state, [str(item) for item in expected])


def _render_validation_step(state: _RenderState, index: int, step: dict[str, Any]) -> None:
    title = str(step.get("title") or step.get("step_id") or "Validation step")
    _subheading(state, f"{index}. {title}")
    for command_index, command in enumerate(step.get("commands") or [], start=1):
        _paragraph(state, f"Command {command_index} - {command.get('kind', 'check')}", size=8.4)
        _code_block(state, str(command.get("command") or ""), max_lines=None)
    expected = [str(item) for item in step.get("expected_outcomes") or [] if str(item).strip()]
    if expected:
        _paragraph(state, "Expected result:", size=8.4)
        _bullets(state, expected)


def _resource_table(state: _RenderState, headers: list[str], rows: list[list[str]]) -> None:
    if not rows:
        _paragraph(state, "None observed.")
        return
    _table(state, headers, rows)


def _lead(state: _RenderState, text: str) -> None:
    _paragraph(state, text, size=11, color=state.template["theme"]["text"], leading=5)


def _subheading(state: _RenderState, title: str) -> None:
    _ensure_space(state, 28)
    state.y -= 8
    _text(state.page, state.margin_left, state.y, title, "F2", 11.5, color=state.template["theme"]["primary"])
    state.y -= 18


def _paragraph(
    state: _RenderState,
    text: str,
    *,
    size: float = 9.2,
    color: str | None = None,
    leading: float = 4,
) -> None:
    color = color or state.template["theme"]["text"]
    text = _clean(_strip_markdown(text))
    lines = _wrap(text, _chars_per_line(state.content_width, size, "F1"))
    for line in lines:
        _ensure_space(state, size + leading)
        _text(state.page, state.margin_left, state.y, line, "F1", size, color=color)
        state.y -= size + leading


def _bullets(state: _RenderState, items: list[str]) -> None:
    for item in items:
        for idx, line in enumerate(_wrap(_clean(_strip_markdown(item)), _chars_per_line(state.content_width - 18, 9, "F1"))):
            _ensure_space(state, 14)
            prefix = "- " if idx == 0 else "  "
            _text(state.page, state.margin_left + 8, state.y, prefix + line, "F1", 9, color=state.template["theme"]["text"])
            state.y -= 13


def _two_column_cards(state: _RenderState, cards: list[tuple[str, str]]) -> None:
    col_w = (state.content_width - 14) / 2
    x_values = [state.margin_left, state.margin_left + col_w + 14]
    y_start = state.y
    max_bottom = y_start
    for index, (title, body) in enumerate(cards):
        if index and index % 2 == 0:
            state.y = max_bottom - 14
            y_start = state.y
        x = x_values[index % 2]
        height = 82
        _ensure_space(state, height + 10)
        _card_box(state.page, x, y_start - height, col_w, height, state.template)
        _text(state.page, x + 12, y_start - 20, title, "F2", 9.5, color=state.template["theme"]["primary"])
        wrapped = _wrap(_clean(_strip_markdown(body)), _chars_per_line(col_w - 24, 8.1, "F1"))[:4]
        y = y_start - 38
        for line in wrapped:
            _text(state.page, x + 12, y, line, "F1", 8.1, color=state.template["theme"]["text"])
            y -= 11
        max_bottom = min(max_bottom, y_start - height)
    state.y = max_bottom - 10


def _metric_grid(state: _RenderState, cards: list[tuple[str, str, str]]) -> None:
    x = state.margin_left
    width = (state.content_width - 27) / 4
    _ensure_space(state, 84)
    for label, value, color in cards:
        _metric_card(state.page, x, state.y - 70, width, 64, label, value, color)
        x += width + 9
    state.y -= 88


def _metric_card(page: _Page, x: float, y: float, width: float, height: float, label: str, value: str, color: str) -> None:
    _rect(page, x, y, width, height, fill="1 1 1", stroke="0.78 0.86 0.90")
    _rect(page, x, y + height - 8, width, 8, fill=color)
    _text(page, x + 10, y + height - 27, str(value), "F2", 18, color=color)
    _text(page, x + 10, y + 14, _clean(label), "F1", 8.2, color="0.36 0.43 0.48")


def _table(state: _RenderState, headers: list[str], rows: list[list[str]]) -> None:
    col_width = state.content_width / len(headers)
    row_h = 24
    x = state.margin_left

    def draw_header() -> float:
        _ensure_space(state, row_h * 2)
        header_y = state.y
        _rect(
            state.page,
            x,
            header_y - row_h,
            state.content_width,
            row_h,
            fill=state.template["theme"]["secondary"],
        )
        for i, header in enumerate(headers):
            _text(state.page, x + i * col_width + 6, header_y - 16, _clean(header), "F2", 8.2, color="1 1 1")
        return header_y - row_h

    y = draw_header()
    for row_index, row in enumerate(rows):
        fill = "0.98 0.99 1" if row_index % 2 == 0 else "0.94 0.97 0.98"
        max_lines = max(len(_wrap(_clean(_strip_markdown(cell)), _chars_per_line(col_width - 12, 7.3, "F1"))) for cell in row)
        height = max(row_h, max_lines * 10 + 10)
        if y - height < state.margin_bottom:
            _start_continuation_page(state)
            y = draw_header()
        _rect(state.page, x, y - height, state.content_width, height, fill=fill, stroke=state.template["theme"]["border"])
        for i, cell in enumerate(row):
            lines = _wrap(_clean(_strip_markdown(cell)), _chars_per_line(col_width - 12, 7.3, "F1"))[:5]
            cell_y = y - 14
            for line in lines:
                _text(state.page, x + i * col_width + 6, cell_y, line, "F1", 7.3, color=state.template["theme"]["text"])
                cell_y -= 9
        y -= height
    state.y = y - 12


def _diagram_flow(state: _RenderState, labels: list[str]) -> None:
    _ensure_space(state, 120)
    y = state.y - 58
    box_w = (state.content_width - 54) / 4
    x = state.margin_left
    for index, label in enumerate(labels):
        _rect(state.page, x, y, box_w, 58, fill="0.93 0.98 0.99", stroke=state.template["theme"]["accent"])
        for line_index, line in enumerate(label.split("\\n")):
            _text(state.page, x + 10, y + 35 - line_index * 13, line, "F2" if line_index == 0 else "F1", 8.5, color=state.template["theme"]["primary"])
        if index < len(labels) - 1:
            _line(state.page, x + box_w + 4, y + 29, x + box_w + 17, y + 29, width=1.2, color=state.template["theme"]["secondary"])
            _text(state.page, x + box_w + 18, y + 25, ">", "F2", 10, color=state.template["theme"]["secondary"])
        x += box_w + 18
    state.y = y - 24


def _phase_map(state: _RenderState, phases: list[str]) -> None:
    _ensure_space(state, 210)
    x = state.margin_left
    y = state.y - 42
    box_w = 118
    box_h = 42
    for index, phase in enumerate(phases):
        row = index // 4
        col = index % 4
        bx = x + col * (box_w + 14)
        by = y - row * 72
        _rect(state.page, bx, by, box_w, box_h, fill="0.96 0.98 1", stroke=state.template["theme"]["secondary"])
        _text(state.page, bx + 8, by + 24, f"{index + 1}. {phase}", "F2", 7.6, color=state.template["theme"]["primary"])
        if col < 3 and index < len(phases) - 1:
            _line(state.page, bx + box_w + 2, by + 21, bx + box_w + 12, by + 21, width=1, color=state.template["theme"]["secondary"])
    state.y = y - 142


def _code_block(state: _RenderState, value: str, *, max_lines: int | None = 18) -> None:
    text = str(value or "[]")
    lines = (_truncate_lines(text, max_lines).splitlines() if max_lines else text.splitlines()) or ["[]"]
    for raw in lines:
        for line in _wrap(_clean_code(raw), _chars_per_line(state.content_width - 18, 7.2, "F3")):
            _ensure_space(state, 13)
            _rect(state.page, state.margin_left, state.y - 3, state.content_width, 12, fill="0.96 0.96 0.94")
            _text(state.page, state.margin_left + 7, state.y, line, "F3", 7.2, color="0.12 0.16 0.18", clean=False)
            state.y -= 12
    state.y -= 4


def _ensure_space(state: _RenderState, needed: float) -> None:
    if state.y - needed >= state.margin_bottom:
        return
    _start_continuation_page(state)


def _start_continuation_page(state: _RenderState) -> None:
    state.pages.append(_Page())
    theme = state.template["theme"]
    _rect(state.page, 0, PAGE_HEIGHT - 44, PAGE_WIDTH, 44, fill=theme["primary"])
    _rect(state.page, 0, PAGE_HEIGHT - 48, PAGE_WIDTH, 4, fill=theme["accent"])
    _text(state.page, state.margin_left, PAGE_HEIGHT - 27, state.current_section or "BOS Genesis MoP", "F2", 11, color="1 1 1")
    state.y = PAGE_HEIGHT - 72


def _render_footer(state: _RenderState, page: _Page, page_number: int, total_pages: int) -> None:
    theme = state.template["theme"]
    _line(page, state.margin_left, 36, PAGE_WIDTH - state.margin_right, 36, width=0.4, color=theme["border"])
    _text(page, state.margin_left, 22, "BOS Genesis MoP Creation Agent", "F1", 7.2, color=theme["muted"])
    _text(page, PAGE_WIDTH - state.margin_right - 68, 22, f"Page {page_number} of {total_pages}", "F1", 7.2, color=theme["muted"])


def _build_pdf(pages: list[_Page]) -> bytes:
    page_count = len(pages)
    page_object_numbers = [6 + index * 2 for index in range(page_count)]
    content_object_numbers = [page_object + 1 for page_object in page_object_numbers]
    kids = " ".join(f"{number} 0 R" for number in page_object_numbers)
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {page_count} >>".encode("ascii"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>",
    ]
    for page, content_obj in zip(pages, content_object_numbers):
        stream = "\n".join(page.commands).encode("ascii", errors="ignore")
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_WIDTH} {PAGE_HEIGHT}] "
                f"/Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R >> >> "
                f"/Contents {content_obj} 0 R >>"
            ).encode("ascii")
        )
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"\nendstream")
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode("ascii"))
        output.extend(obj)
        output.extend(b"\nendobj\n")
    xref_offset = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.extend(
        (
            "trailer\n"
            f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            "startxref\n"
            f"{xref_offset}\n"
            "%%EOF\n"
        ).encode("ascii")
    )
    return bytes(output)


def _card_box(page: _Page, x: float, y: float, width: float, height: float, template: dict[str, Any]) -> None:
    _rect(page, x + 2, y - 2, width, height, fill="0.86 0.90 0.92")
    _rect(page, x, y, width, height, fill=template["theme"]["panel"], stroke=template["theme"]["border"])


def _cover_detail(page: _Page, x: float, y: float, label: str, value: str) -> None:
    _text(page, x, y + 11, label, "F2", 7.5, color="0.50 0.82 0.92")
    _text(page, x, y, _clean(value)[:88], "F1", 8.6, color="1 1 1")


def _rect(page: _Page, x: float, y: float, width: float, height: float, *, fill: str, stroke: str | None = None) -> None:
    if stroke:
        page.commands.append(f"q {fill} rg {stroke} RG {x:.2f} {y:.2f} {width:.2f} {height:.2f} re B Q")
    else:
        page.commands.append(f"q {fill} rg {x:.2f} {y:.2f} {width:.2f} {height:.2f} re f Q")


def _circle(page: _Page, cx: float, cy: float, radius: float, *, fill: str) -> None:
    # Bezier approximation for decorative circles.
    c = radius * 0.55228475
    cmds = [
        f"q {fill} rg",
        f"{cx + radius:.2f} {cy:.2f} m",
        f"{cx + radius:.2f} {cy + c:.2f} {cx + c:.2f} {cy + radius:.2f} {cx:.2f} {cy + radius:.2f} c",
        f"{cx - c:.2f} {cy + radius:.2f} {cx - radius:.2f} {cy + c:.2f} {cx - radius:.2f} {cy:.2f} c",
        f"{cx - radius:.2f} {cy - c:.2f} {cx - c:.2f} {cy - radius:.2f} {cx:.2f} {cy - radius:.2f} c",
        f"{cx + c:.2f} {cy - radius:.2f} {cx + radius:.2f} {cy - c:.2f} {cx + radius:.2f} {cy:.2f} c",
        "f Q",
    ]
    page.commands.append(" ".join(cmds))


def _line(page: _Page, x1: float, y1: float, x2: float, y2: float, *, width: float = 1, color: str = "0 0 0") -> None:
    page.commands.append(f"q {color} RG {width:.2f} w {x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S Q")


def _text(
    page: _Page,
    x: float,
    y: float,
    value: str,
    font: str,
    size: float,
    *,
    color: str,
    clean: bool = True,
) -> None:
    text = _clean(value) if clean else _clean_code(value)
    page.commands.append(f"BT {color} rg /{font} {size:.2f} Tf {x:.2f} {y:.2f} Td ({_escape(text)}) Tj ET")


def _wrap(text: str, chars: int) -> list[str]:
    return textwrap.wrap(text, max(chars, 10), break_long_words=True, break_on_hyphens=False) or [""]


def _chars_per_line(width: float, size: float, font: str) -> int:
    factor = 0.55 if font != "F3" else 0.61
    return max(8, int(width / (size * factor)))


def _clean(value: Any) -> str:
    text = str(value or "")
    for source, target in {
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
        "\u00a0": " ",
        "&": "and",
    }.items():
        text = text.replace(source, target)
    return text.encode("ascii", errors="ignore").decode("ascii")


def _clean_code(value: Any) -> str:
    text = str(value or "")
    for source, target in {
        "\u2013": "-",
        "\u2014": "-",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
        "\u00a0": " ",
    }.items():
        text = text.replace(source, target)
    return text.encode("ascii", errors="ignore").decode("ascii")


def _strip_markdown(value: str) -> str:
    return value.replace("`", "").replace("**", "").replace("__", "")


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _value(context: dict[str, Any], key: str, default: str = "TBD") -> str:
    value = context.get(key)
    if value is None or value == "":
        return default
    return str(value)


def _split_summary(value: str, *, limit: int) -> list[str]:
    items = [item.strip(" -\n") for item in re.split(r";|\n", value) if item.strip(" -\n")]
    return items[:limit] or ["None recorded."]


def _truncate_lines(value: str, limit: int) -> str:
    lines = str(value or "[]").splitlines()
    if len(lines) <= limit:
        return "\n".join(lines)
    return "\n".join([*lines[:limit], f"... truncated {len(lines) - limit} additional lines ..."])


def _first_yaml_item(value: str) -> str:
    text = str(value or "  []")
    if text.strip() == "[]":
        return text
    lines = text.splitlines()
    if len(lines) <= 16:
        return text
    return "\n".join(lines[:16] + ["..."])


def _join_non_empty(*values: Any, separator: str = " ") -> str:
    return separator.join(str(value) for value in values if value not in (None, ""))


def _bool_label(value: Any) -> str:
    return "yes" if bool(value) else "no"


def _extract_markdown_title(markdown_content: str) -> str:
    for line in markdown_content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return "BOS Genesis Method of Procedure"


def _extract_markdown_sections(markdown_content: str) -> list[str]:
    return [line[3:].strip() for line in markdown_content.splitlines() if line.startswith("## ")]
