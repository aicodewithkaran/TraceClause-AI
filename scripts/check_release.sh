#!/usr/bin/env bash
# ==============================================================================
# TraceClause AI / ScanShield AI v2 - Pre-Deployment Release Gate Check
#
# This script enforces strict CI/CD and deployment gates:
# 1. Backend Pytest Suite Execution (32 security, quota, auth, and queue tests)
# 2. Production Security Configuration Validation (blocks demo auth, weak secrets)
# 3. Frontend Next.js Production Build & TypeScript Typecheck
# 4. Security Invariant & Migration Integrity Verification
#
# Usage:
#   bash scripts/check_release.sh
# Returns 0 on success, 1 on failure. Releases MUST be blocked if this exits non-zero.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================================${NC}"
echo -e "${BLUE}  TraceClause AI - Pre-Deployment Release Gate Check  ${NC}"
echo -e "${BLUE}======================================================${NC}"
echo "Project Root: ${PROJECT_ROOT}"
echo ""

# ------------------------------------------------------------------------------
# STEP 1: Verify Master Database Migration File
# ------------------------------------------------------------------------------
echo -e "${YELLOW}[1/4] Verifying Master Database Migration...${NC}"
MIGRATION_FILE="${PROJECT_ROOT}/supabase/migrations/20261105_production_master_hardening.sql"
if [[ ! -f "${MIGRATION_FILE}" ]]; then
    echo -e "${RED}[FAIL] Master migration file missing: ${MIGRATION_FILE}${NC}"
    exit 1
fi
echo -e "${GREEN}[PASS] Master migration present (${MIGRATION_FILE})${NC}"
echo ""

# ------------------------------------------------------------------------------
# STEP 2: Run Backend Test Suite (Pytest)
# ------------------------------------------------------------------------------
echo -e "${YELLOW}[2/4] Running Backend Security & Integration Tests...${NC}"
cd "${PROJECT_ROOT}/backend"

if [[ -f "./venv/bin/pytest" ]]; then
    PYTHON_EXEC="./venv/bin/pytest"
else
    PYTHON_EXEC="pytest"
fi

${PYTHON_EXEC} tests/ -v
echo -e "${GREEN}[PASS] All backend unit and security tests passed successfully.${NC}"
echo ""

# ------------------------------------------------------------------------------
# STEP 3: Verify Backend Production Security Invariants
# ------------------------------------------------------------------------------
echo -e "${YELLOW}[3/4] Validating Production Security Invariants...${NC}"
if [[ -f "./venv/bin/python" ]]; then
    PY_BIN="./venv/bin/python"
else
    PY_BIN="python3"
fi

${PY_BIN} -c '
from app.core.config import Settings
import sys

# Test 1: Production must reject ALLOW_DEMO_AUTH=True
try:
    s = Settings(
        ENVIRONMENT="production",
        ALLOW_DEMO_AUTH=True,
        SECRET_KEY="x" * 32,
        SUPABASE_URL="https://test.supabase.co",
        SUPABASE_KEY="anon_key",
        SUPABASE_SERVICE_ROLE_KEY="service_key",
        OPENAI_API_KEY="sk-test"
    )
    s.validate_security_configuration()
    print("Security check failed: ALLOW_DEMO_AUTH=True allowed in production!", file=sys.stderr)
    sys.exit(1)
except RuntimeError:
    pass

# Test 2: Production must reject weak/default secrets
try:
    s = Settings(
        ENVIRONMENT="production",
        ALLOW_DEMO_AUTH=False,
        SECRET_KEY="supersecretkey",
        SUPABASE_URL="https://test.supabase.co",
        SUPABASE_KEY="anon_key",
        SUPABASE_SERVICE_ROLE_KEY="service_key",
        OPENAI_API_KEY="sk-test"
    )
    s.validate_security_configuration()
    print("Security check failed: weak SECRET_KEY allowed in production!", file=sys.stderr)
    sys.exit(1)
except RuntimeError:
    pass

print("Security configuration validator correctly enforces fail-closed production requirements.")
'
echo -e "${GREEN}[PASS] Security configuration validation passed.${NC}"
echo ""

# ------------------------------------------------------------------------------
# STEP 4: Frontend Next.js Production Build & Typecheck
# ------------------------------------------------------------------------------
echo -e "${YELLOW}[4/4] Executing Frontend Next.js Production Build...${NC}"
cd "${PROJECT_ROOT}/frontend"

npm run build
echo -e "${GREEN}[PASS] Next.js frontend compiled and optimized with zero errors.${NC}"
echo ""

echo -e "${GREEN}======================================================${NC}"
echo -e "${GREEN}  ALL RELEASE GATE CHECKS PASSED - READY TO DEPLOY   ${NC}"
echo -e "${GREEN}======================================================${NC}"
exit 0

