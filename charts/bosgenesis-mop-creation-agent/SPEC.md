# Agent Helm Chart Specification

## Intent

This chart deploys `bosgenesis-mop-creation-agent` into the configured namespace, normally `bosgenesis`.

## Resources

- Deployment.
- Service.
- ConfigMap.
- Secret reference.
- Ingress.
- ServiceAccount.
- NetworkPolicy.

## Safety

The chart must not request cluster-admin privileges or cluster-scoped resources.

