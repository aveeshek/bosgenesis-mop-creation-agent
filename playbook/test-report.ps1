param(
    [string]$ReportDir = "reports"
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $RepoRoot

$PytestDir = Join-Path $ReportDir "pytest"
$CoverageDir = Join-Path $ReportDir "coverage"
$CoverageHtmlDir = Join-Path $CoverageDir "html"

New-Item -ItemType Directory -Force -Path $PytestDir | Out-Null
New-Item -ItemType Directory -Force -Path $CoverageHtmlDir | Out-Null

python -m ruff check src tests
python -m pytest `
    --junitxml="$PytestDir/test-results.xml" `
    --cov=bosgenesis_mop_creation_agent `
    --cov-branch `
    --cov-report=term-missing `
    --cov-report="xml:$CoverageDir/coverage.xml" `
    --cov-report="html:$CoverageHtmlDir"

Write-Host ""
Write-Host "Validation reports generated:"
Write-Host "- $PytestDir/test-results.xml"
Write-Host "- $CoverageDir/coverage.xml"
Write-Host "- $CoverageHtmlDir/index.html"
