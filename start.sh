#!/bin/bash
# start.sh
# Hiring Cafe Pipeline Launcher (Linux/Mac)

set -e

echo "================================================"
echo "   Hiring Cafe Pipeline Launcher (Bash)         "
echo "================================================"

ROOT=$(pwd)
VENV_PATH="$ROOT/venv/bin/python"
SCRIPT_PATH="$ROOT/hiring_cafe_scheduler.py"

# 1. Check for .env file
if [ ! -f ".env" ]; then
    echo "❌ ERROR: .env file not found. Please create it first."
    exit 1
fi

# 2. Check for virtual environment
if [ -f "$VENV_PATH" ]; then
    echo "✅ Virtual environment found. Using $VENV_PATH"
    PYTHON="$VENV_PATH"
else
    echo "⚠️  Virtual environment not found at $VENV_PATH. Using system python."
    PYTHON="python3"
fi

# 3. Run the scheduler with --force
echo "🚀 Launching Hiring Cafe Pipeline..."
$PYTHON "$SCRIPT_PATH" --force

echo "================================================"
echo "   Pipeline Finished                            "
echo "================================================"
