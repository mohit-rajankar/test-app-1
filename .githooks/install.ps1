# ==============================================================================
# Developer Activation Script for Git Central Hooks (PowerShell)
# ==============================================================================
# Usage:
#   .\.githooks\install.ps1
# ==============================================================================

$ErrorActionPreference = "Stop"

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "[SETUP] Configuring Local Git Hooks (Windows PowerShell)" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

# 1. Verify inside a Git repository
try {
    $repoRoot = (git rev-parse --show-toplevel 2>$null)
} catch {
    $repoRoot = $null
}

if (-not $repoRoot) {
    Write-Host "[ERROR] Current directory is not a Git repository." -ForegroundColor Red
    exit 1
}

Set-Location $repoRoot

# 2. Verify .githooks directory exists
if (-not (Test-Path -Path ".githooks" -PathType Container)) {
    Write-Host "[ERROR] '.githooks' directory not found in $repoRoot." -ForegroundColor Red
    Write-Host "        Ensure this repository has received synchronized hooks from central." -ForegroundColor Yellow
    exit 1
}

# 3. Configure core.hooksPath
git config core.hooksPath .githooks

# 4. Verify configuration
$activePath = (git config --get core.hooksPath)

if ($activePath -eq ".githooks") {
    Write-Host "[SUCCESS] Git hooks path configured to '.githooks'." -ForegroundColor Green
    Write-Host ""
    Write-Host "Active hooks in .githooks/:" -ForegroundColor Gray
    Get-ChildItem -Path ".githooks" -File | ForEach-Object {
        Write-Host "  - $($_.Name)" -ForegroundColor Gray
    }
    Write-Host ""
    Write-Host "Git for Windows will now execute hooks directly from .githooks." -ForegroundColor Green
    Write-Host "Note: Git hooks run via the sh interpreter bundled with Git for Windows." -ForegroundColor Gray
    Write-Host "=================================================================" -ForegroundColor Cyan
} else {
    Write-Host "[ERROR] Failed to set core.hooksPath. Current value: '$activePath'" -ForegroundColor Red
    exit 1
}
