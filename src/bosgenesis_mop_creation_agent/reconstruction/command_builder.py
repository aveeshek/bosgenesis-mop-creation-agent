from __future__ import annotations

from bosgenesis_mop_creation_agent.reconstruction.models import HelmReleasePlan, RawManifestPlan


def build_raw_plan(
    *,
    kind: str,
    name: str,
    target_namespace: str,
    file_path: str,
    relative_path: str,
    evidence_ref: str,
    warnings: list[str],
) -> RawManifestPlan:
    dry_run = f"kubectl apply -f {relative_path} -n {target_namespace} --dry-run=server -o yaml"
    apply = f"kubectl apply -f {relative_path} -n {target_namespace}"
    validate = f"kubectl get {kind.lower()} {name} -n {target_namespace} -o wide"
    rollback = f"kubectl delete -f {relative_path} -n {target_namespace} --ignore-not-found"
    return RawManifestPlan(
        kind=kind,
        name=name,
        namespace=target_namespace,
        file_path=file_path,
        relative_path=relative_path,
        dry_run_command=dry_run,
        apply_command=apply,
        validation_command=validate,
        rollback_command=rollback,
        evidence_ref=evidence_ref,
        warnings=warnings,
    )


def build_helm_plan(
    *,
    release_name: str,
    chart_ref: str,
    chart_version: str | None = None,
    chart_source: str = "observed",
    repo_name: str | None = None,
    repo_url: str | None = None,
    credential_secret_ref: str | None = None,
    target_namespace: str,
    values_file_path: str,
    values_relative_path: str,
    evidence_ref: str,
    warnings: list[str],
) -> HelmReleasePlan:
    version_args = f" --version {chart_version}" if chart_version else ""
    dry_run = (
        f"helm upgrade --install {release_name} {chart_ref} "
        f"--namespace {target_namespace} --create-namespace{version_args} "
        f"-f {values_relative_path} --dry-run"
    )
    install = (
        f"helm upgrade --install {release_name} {chart_ref} "
        f"--namespace {target_namespace} --create-namespace{version_args} "
        f"-f {values_relative_path} --atomic --timeout 10m"
    )
    validate = f"helm status {release_name} -n {target_namespace}"
    rollback = f"helm uninstall {release_name} -n {target_namespace} --ignore-not-found"
    return HelmReleasePlan(
        release_name=release_name,
        chart_ref=chart_ref,
        chart_version=chart_version,
        chart_source=chart_source,
        repo_name=repo_name,
        repo_url=repo_url,
        credential_secret_ref=credential_secret_ref,
        values_file_path=values_file_path,
        values_relative_path=values_relative_path,
        dry_run_command=dry_run,
        install_command=install,
        validation_command=validate,
        rollback_command=rollback,
        evidence_ref=evidence_ref,
        warnings=warnings,
    )
