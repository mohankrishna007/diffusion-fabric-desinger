#!/bin/bash
# Bash script to launch Weaver AI Streamlit UI

echo "🧵 Starting Weaver AI Streamlit UI..."
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR"

# Path to streamlit app
APP_PATH="$PROJECT_ROOT/src/weaver/ui/streamlit_app.py"

# Check if app file exists
if [ ! -f "$APP_PATH" ]; then
    echo "❌ Streamlit app not found at: $APP_PATH"
    exit 1
fi

echo "✅ App found at: $APP_PATH"

# Check if uv is available
USE_UV=false
if command -v uv &> /dev/null; then
    UV_VERSION=$(uv --version 2>&1)
    echo "✅ Found UV: $UV_VERSION"
    USE_UV=true
fi

if [ "$USE_UV" = false ]; then
    # Fallback to direct streamlit
    if ! command -v streamlit &> /dev/null; then
        echo "❌ Neither UV nor Streamlit found!"
        echo "Install with: uv sync  OR  pip install streamlit>=1.30.0"
        exit 1
    fi
    
    STREAMLIT_VERSION=$(streamlit --version 2>&1)
    echo "✅ Found Streamlit: $STREAMLIT_VERSION"
fi

echo ""
echo "🚀 Launching Streamlit UI..."
echo "   The browser will open automatically at http://localhost:8501"
echo "   Press Ctrl+C to stop the server"
echo ""

# Launch Streamlit with uv or directly
if [ "$USE_UV" = true ]; then
    uv run streamlit run "$APP_PATH" \
        --server.port 8501 \
        --server.address localhost \
        --browser.gatherUsageStats false \
        --theme.primaryColor "#2E86AB" \
        --theme.backgroundColor "#FFFFFF" \
        --theme.secondaryBackgroundColor "#F0F2F6"
else
    streamlit run "$APP_PATH" \
        --server.port 8501 \
        --server.address localhost \
        --browser.gatherUsageStats false \
        --theme.primaryColor "#2E86AB" \
        --theme.backgroundColor "#FFFFFF" \
        --theme.secondaryBackgroundColor "#F0F2F6"
fi
