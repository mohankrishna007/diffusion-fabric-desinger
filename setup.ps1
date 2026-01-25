# Quick Start Script for Windows PowerShell

Write-Host "Diffusion Fabric Designer - Quick Setup with UV" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""

# Check if UV is installed
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "UV not found. Installing UV..." -ForegroundColor Yellow
    powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
    
    # Refresh PATH
    $env:PATH = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    
    Write-Host "UV installed successfully!" -ForegroundColor Green
    Write-Host ""
} else {
    Write-Host "UV is already installed" -ForegroundColor Green
    uv --version
    Write-Host ""
}

# Install project with dependencies (creates venv automatically)
Write-Host "Installing project and dependencies..." -ForegroundColor Yellow
uv sync

Write-Host "Installing development dependencies..." -ForegroundColor Yellow
uv pip install -e ".[dev]"

Write-Host ""
Write-Host "Setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "To activate the virtual environment, run:" -ForegroundColor Cyan
Write-Host "  .venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host ""
Write-Host "To start the API server, run:" -ForegroundColor Cyan
Write-Host "  uv run python -m weaver.api.main" -ForegroundColor White
Write-Host ""
