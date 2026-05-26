# Kubernetes Deployment Specification

## Intent

`deploy/k8s/` will hold future kustomize-compatible deployment assets.

## Safety

Deployment assets must be namespace-scoped and must not include cluster-scoped RBAC.

