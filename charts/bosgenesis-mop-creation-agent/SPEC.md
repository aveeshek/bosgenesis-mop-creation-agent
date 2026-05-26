# Agent Helm Chart Specification

## Intent

This future chart will deploy `bosgenesis-mop-creation-agent` into the `bosgenesis` namespace.

## Future resources

- Deployment.
- Service.
- ConfigMap.
- Secret reference.
- Ingress.
- ServiceAccount.
- NetworkPolicy.

## Safety

The chart must not request cluster-admin privileges or cluster-scoped resources.

