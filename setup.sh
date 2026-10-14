#!/usr/bin/env bash
# ==============================================================================
# Spaceborne Rapid Disaster Assessment Platform - One-Click Setup Script
# ==============================================================================
set -e

echo "=== Spaceborne Disaster Platform Setup ==="
echo "Operating System: $(uname -s) $(uname -m)"
echo "Python Version: $(python3 --version 2>&1)"

# 1. Install python dependencies
echo -e "\n[1/3] Installing Python dependencies from requirements.txt..."
python3 -m pip install -r requirements.txt

# 2. Compile C-accelerated HAND shared library
echo -e "\n[2/3] Compiling C-accelerated HAND module (libhand_fast.so)..."
if command -v gcc >/dev/null 2>&1; then
    gcc -O3 -shared -fPIC src/l1_preprocessing/hand_c.c -o src/l1_preprocessing/libhand_fast.so
    echo "✓ C extension compiled successfully at src/l1_preprocessing/libhand_fast.so"
else
    echo "⚠ gcc not found; pipeline will automatically use vectorized pure-Python fallback."
fi

# 3. Verify C library & Python fallback
echo -e "\n[3/3] Verifying HAND acceleration & Python fallback equivalence..."
PYTHONPATH=. python3 -c '
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

# 4. Check .env
if [ ! -f .env ] && [ -f .env.example ]; then
    echo -e "\nTip: No .env detected. You can copy .env.example to .env to add Copilot API keys:"
    echo "  cp .env.example .env"
fi

echo -e "\n=== Setup complete! Platform is ready. ==="
echo "To launch the Interactive Dashboard:"
echo "  python3 -m uvicorn src.dashboard.app:app --host 127.0.0.1 --port 8000"
echo "To verify existing runs and deliverables:"
echo "  python3 scripts/check_dashboard_data.py"
