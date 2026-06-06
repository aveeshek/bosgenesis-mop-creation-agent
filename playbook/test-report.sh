#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

REPORT_DIR="${REPORT_DIR:-reports}"
PYTEST_DIR="${REPORT_DIR}/pytest"
COVERAGE_DIR="${REPORT_DIR}/coverage"

mkdir -p "${PYTEST_DIR}" "${COVERAGE_DIR}/html"

python -m ruff check src tests
python -m pytest \
  --junitxml="${PYTEST_DIR}/test-results.xml" \
  --cov=bosgenesis_mop_creation_agent \
  --cov-branch \
  --cov-report=term-missing \
  --cov-report=xml:"${COVERAGE_DIR}/coverage.xml" \
  --cov-report=html:"${COVERAGE_DIR}/html"

echo
echo "Validation reports generated:"
echo "- ${PYTEST_DIR}/test-results.xml"
echo "- ${COVERAGE_DIR}/coverage.xml"
echo "- ${COVERAGE_DIR}/html/index.html"
