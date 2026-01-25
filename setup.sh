#!/bin/bash
# Quick Start Script for Unix/macOS

echo -e "\033[36mDiffusion Fabric Designer - Quick Setup with UV\033[0m"
echo -e "\033[36m================================================\033[0m"
echo ""

# Check if UV is installed
if ! command -v uv &> /dev/null; then
    echo -e "\033[33mUV not found. Installing UV...\033[0m"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    
    # Source the cargo env to get UV in path
    source $HOME/.cargo/env
    
    echo -e "\033[32mUV installed successfully!\033[0m"
    echo ""
else
    echo -e "\033[32mUV is already installed\033[0m"
    uv --version
    echo ""
fi

# Install project with dependencies (creates venv automatically)
echo -e "\033[33mInstalling project and dependencies...\033[0m"
uv sync

echo -e "\033[33mInstalling development dependencies...\033[0m"
uv pip install -e ".[dev]"

echo ""
echo -e "\033[32mSetup complete!\033[0m"
echo ""
echo -e "\033[36mTo activate the virtual environment, run:\033[0m"
echo -e "\033[37m  source .venv/bin/activate\033[0m"
echo ""
echo -e "\033[36mTo start the API server, run:\033[0m"
echo -e "\033[37m  uv run python -m weaver.api.main\033[0m"
echo ""
