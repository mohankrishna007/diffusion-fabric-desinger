#!/usr/bin/env pwsh
# PowerShell script to launch Weaver AI Streamlit UI

Write-Host "🧵 Starting Weaver AI Streamlit UI..." -ForegroundColor Cyan
Write-Host ""

# Get script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = $scriptDir

# Path to streamlit app
$appPath = Join-Path $projectRoot "src\ui\streamlit_app.py"

# Check if app file exists
if (-not (Test-Path $appPath)) {
    Write-Host "❌ Streamlit app not found at: $appPath" -ForegroundColor Red
    exit 1
}

Write-Host "✅ App found at: $appPath" -ForegroundColor Green

# Check if uv is available
$useUv = $false
try {
    $uvVersion = & uv --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ Found UV: $uvVersion" -ForegroundColor Green
        $useUv = $true
    }
} catch {
    # uv not found, try streamlit directly
}

if (-not $useUv) {
    # Fallback to direct streamlit
    try {
        $streamlitVersion = & streamlit --version 2>&1
        Write-Host "✅ Found Streamlit: $streamlitVersion" -ForegroundColor Green
    } catch {
        Write-Host "❌ Neither UV nor Streamlit found!" -ForegroundColor Red
        Write-Host "Install with: uv sync  OR  pip install streamlit>=1.30.0" -ForegroundColor Yellow
        exit 1
    }
}

Write-Host ""
Write-Host "🚀 Launching Streamlit UI..." -ForegroundColor Cyan
Write-Host "   The browser will open automatically at http://localhost:8501" -ForegroundColor Gray
Write-Host "   Press Ctrl+C to stop the server" -ForegroundColor Gray
Write-Host ""

# Launch Streamlit with uv or directly
if ($useUv) {
    & uv run streamlit run $appPath `
        --server.port 8501 `
        --server.address localhost `
        --browser.gatherUsageStats false `
        --theme.primaryColor "#2E86AB" `
        --theme.backgroundColor "#FFFFFF" `
        --theme.secondaryBackgroundColor "#F0F2F6"
} else {
    & streamlit run $appPath `
        --server.port 8501 `
        --server.address localhost `
        --browser.gatherUsageStats false `
        --theme.primaryColor "#2E86AB" `
        --theme.backgroundColor "#FFFFFF" `
        --theme.secondaryBackgroundColor "#F0F2F6"
}
