from __future__ import annotations

from dataclasses import dataclass

from bosgenesis_mop_creation_agent.classification.models import ClassificationSummary
from bosgenesis_mop_creation_agent.reconstruction.models import ReconstructionPlan


HELM_RECONSTRUCTION_REQUIRED_KINDS = {
    "CronJob",
    "DaemonSet",
    "Deployment",
    "Ingress",
    "Job",
    "Service",
    "StatefulSet",
}


@dataclass(frozen=True)
class ReconstructionQualityError(RuntimeError):
    code: str
    details: list[str]

    def __str__(self) -> str:
        detail_text = ";".join(self.details)
        return f"{self.code}:{detail_text}" if detail_text else self.code


def assert_executable_reconstruction_complete(
    *,
    classification: ClassificationSummary | None,
    reconstruction: ReconstructionPlan,
) -> None:
    """Fail closed when executable clone evidence is incomplete."""
    if classification is None:
        return

    details: list[str] = []
    helm_release_names = {
        plan.source_release_name or plan.release_name
        for plan in reconstruction.helm_releases
    }
    helm_workloads = [
        item
        for item in classification.helm_managed
        if item.resource.kind in HELM_RECONSTRUCTION_REQUIRED_KINDS
    ]
    for item in helm_workloads:
        release_name = item.helm_release_name
        resource_ref = f"{item.resource.kind}/{item.resource.name}"
        if not release_name:
            details.append(f"{resource_ref}:helm_release_name_missing")
        elif release_name not in helm_release_names:
            details.append(f"{resource_ref}:helm_release_plan_missing:{release_name}")

    for plan in reconstruction.helm_releases:
        release_ref = plan.source_release_name or plan.release_name
        if plan.chart_ref.startswith("<"):
            details.append(f"HelmRelease/{release_ref}:chart_ref_missing")
        if plan.chart_source == "private" and not plan.repo_url and not plan.chart_ref.startswith("oci://"):
            details.append(f"HelmRelease/{release_ref}:private_repo_url_required")
        if plan.warnings:
            for warning in plan.warnings:
                if "chart_ref_missing" in warning or "private_repo_url_required" in warning:
                    details.append(f"HelmRelease/{release_ref}:{warning}")

    if details:
        raise ReconstructionQualityError(
            code="INCOMPLETE_HELM_WORKLOAD_RECONSTRUCTION",
            details=details,
        )
