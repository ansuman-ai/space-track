#!/usr/bin/env bash
# ==============================================================================
# Spaceborne Rapid Disaster Assessment Platform - One-Click Setup Script
# ==============================================================================
set -e

echo "=== Spaceborne Disaster Platform Setup ==="
echo "Operating System: $(uname -s) $(uname -m)"
echo "System Python: $(python3 --version 2>&1)"

# Check Python version (3.11+ required)
python3 -c '
import sys
if sys.version_info < (3, 11):
    sys.exit("Error: Python 3.11+ is required (found %d.%d.%d)" % sys.version_info[:3])
'

# 1. Create virtual environment (.venv)
echo -e "\n[1/4] Setting up Python virtual environment (.venv)..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
    echo "✓ Virtual environment created at .venv"
else
    echo "✓ Existing virtual environment found at .venv"
fi

VENV_PYTHON=".venv/bin/python3"
VENV_PIP=".venv/bin/pip"

# 2. Install python dependencies into virtual environment
echo -e "\n[2/4] Installing Python dependencies from requirements.txt into .venv..."
$VENV_PIP install -r requirements.txt

# 3. Compile C-accelerated HAND shared library
echo -e "\n[3/4] Compiling C-accelerated HAND module (libhand_fast.so)..."
if command -v gcc >/dev/null 2>&1; then
    gcc -O3 -shared -fPIC src/l1_preprocessing/hand_c.c -o src/l1_preprocessing/libhand_fast.so
    echo "✓ C extension compiled successfully at src/l1_preprocessing/libhand_fast.so"
else
    echo "⚠ gcc not found; pipeline will automatically use vectorized pure-Python fallback."
fi

# 4. Verify C library & Python fallback inside virtual environment
echo -e "\n[4/4] Verifying HAND acceleration & Python fallback equivalence in .venv..."
PYTHONPATH=. $VENV_PYTHON -c '
import os
import src.l1_preprocessing.hand as h

lib = h._get_hand_lib()
if lib:
    print("✓ C-accelerated HAND module loaded successfully.")
else:
    print("⚠ Using pure Python fallback.")

os.environ["HAND_DISABLE_C"] = "1"
h._LIB_HAND = None
assert h._get_hand_lib() is None
print("✓ Pure Python fallback verified.")
'

# 5. Check .env
if [ ! -f .env ] && [ -f .env.example ]; then
    echo -e "\nTip: No .env detected. You can copy .env.example to .env to add Copilot API keys:"
    echo "  cp .env.example .env"
fi

echo -e "\n=== Setup complete! Platform is ready. ==="
echo "To activate the virtual environment:"
echo "  source .venv/bin/activate"
echo ""
echo "To launch the Interactive Dashboard:"
echo "  source .venv/bin/activate && python3 -m uvicorn src.dashboard.app:app --host 127.0.0.1 --port 8000"
echo ""
echo "To verify existing runs and deliverables:"
echo "  source .venv/bin/activate && python3 scripts/check_dashboard_data.py"

