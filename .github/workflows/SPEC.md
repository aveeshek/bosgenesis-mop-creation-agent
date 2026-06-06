# GitHub Workflows Specification

## Intent

`workflows/` contains CI workflow definitions for linting and testing the agent.

## Required validation gates

- Install the Python package with development dependencies.
- Run Ruff checks.
- Run pytest with branch coverage.
- Generate JUnit XML test reports.
- Generate coverage XML and HTML reports.
- Upload validation reports as CI artifacts.

## Report outputs

CI must produce the same report paths used by local validation:

- `reports/pytest/test-results.xml`
- `reports/coverage/coverage.xml`
- `reports/coverage/html`
