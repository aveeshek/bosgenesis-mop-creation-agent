# Request Samples Specification

## Intent

`samples/requests/` stores JSON request bodies for MoP generation APIs.

## Required samples

- Platform-only generation request.
- Application-mode release-candidate smoke-test request.

## Safety

Request samples must not include credentials, kubeconfig paths, secret values, or
production target namespaces.
