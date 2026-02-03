#!/bin/bash
# Sabhya AI v0.4.0 - Fedora 43 + Python 3.13 Setup Script
# Fixes numpy build issue and installs all dependencies

set -e  # Exit on error

echo "════════════════════════════════════════════════════════════════"
echo "  🛡️  Sabhya AI v0.4.0 - Dependency Setup (Fedora 43 + Py3.13)"
echo "════════════════════════════════════════════════════════════════"

# Change to backend directory
cd /mnt/fedora-partition/llm-saas-venture/backend/llm-api

# Activate venv if not already active
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo "[1/6] Activating virtual environment..."
    source venv_v0.4.0/bin/activate
else
    echo "[1/6] Virtual environment already active: $VIRTUAL_ENV"
fi

# Upgrade pip and install build tools
echo "[2/6] Upgrading pip and build tools..."
pip install --upgrade pip setuptools wheel

# Install numpy first (uses pre-built wheels for Python 3.13)
echo "[3/6] Installing numpy (pre-built wheel for Python 3.13)..."
pip install 'numpy>=2.0'

# Install remaining dependencies
echo "[4/6] Installing remaining dependencies..."
pip install -r requirements.txt --no-build-isolation

# Verify critical imports
echo "[5/6] Verifying critical imports..."
python -c "
import numpy; print(f'  ✓ numpy {numpy.__version__}')
import fastapi; print(f'  ✓ fastapi {fastapi.__version__}')
import pydantic; print(f'  ✓ pydantic {pydantic.__version__}')
import sqlalchemy; print(f'  ✓ sqlalchemy {sqlalchemy.__version__}')
import structlog; print(f'  ✓ structlog')
print('  ✓ Core dependencies OK')
"

# Verify v0.4.0 security imports
echo "[6/6] Verifying v0.4.0 security imports..."
python -c "
try:
    from app.services.pii_detection import pii_service
    print('  ✓ PII Detection Service')
except ImportError as e:
    print(f'  ⚠ PII Detection: {e}')

try:
    from app.auth.security import get_current_user, Roles
    print('  ✓ JWT Authentication')
except ImportError as e:
    print(f'  ⚠ JWT Auth: {e}')

try:
    from app.services.audit import audit_service
    print('  ✓ Audit Service')
except ImportError as e:
    print(f'  ⚠ Audit: {e}')
"

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  ✅ Setup Complete!"
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "Next steps:"
echo "  1. Copy .env.example to .env and configure"
echo "  2. Start the server: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
echo "  3. Test: curl http://localhost:8000/health/live"
echo ""
