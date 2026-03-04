#!/bin/bash
# =============================================================================
# DRS Health Check Script
#
# Verifies all services are healthy.
# Exit code 0 = all healthy, 1 = one or more failed
# =============================================================================

set -euo pipefail

BACKEND_URL=${BACKEND_URL:-http://localhost:8000}
FRONTEND_URL=${FRONTEND_URL:-http://localhost:3001}
RETRIES=${RETRIES:-5}
DELAY=${DELAY:-2}

# ── Colors ───────────────────────────────────────────────────────────────────
GREEN='\033[32m'
RED='\033[31m'
RESET='\033[0m'

check_service() {
    local name=$1
    local url=$2
    
    echo -n "Checking ${name}... "
    
    for i in $(seq 1 "$RETRIES"); do
        if curl -sf "$url" >/dev/null 2>&1; then
            echo -e "${GREEN}✓${RESET}"
            return 0
        fi
        sleep "$DELAY"
    done
    
    echo -e "${RED}✗${RESET}"
    return 1
}

check_postgres() {
    echo -n "Checking PostgreSQL... "
    if docker-compose exec -T postgres pg_isready -U drs -d drs >/dev/null 2>&1; then
        echo -e "${GREEN}✓${RESET}"
        return 0
    else
        echo -e "${RED}✗${RESET}"
        return 1
    fi
}

check_redis() {
    echo -n "Checking Redis... "
    if docker-compose exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; then
        echo -e "${GREEN}✓${RESET}"
        return 0
    else
        echo -e "${RED}✗${RESET}"
        return 1
    fi
}

# ── Run checks ───────────────────────────────────────────────────────────────

echo "Running health checks..."
echo ""

FAILED=0

check_postgres || FAILED=$((FAILED + 1))
check_redis || FAILED=$((FAILED + 1))
check_service "Backend" "${BACKEND_URL}/health" || FAILED=$((FAILED + 1))
check_service "Frontend" "${FRONTEND_URL}" || FAILED=$((FAILED + 1))

echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}All services healthy ✓${RESET}"
    exit 0
else
    echo -e "${RED}${FAILED} service(s) unhealthy ✗${RESET}"
    exit 1
fi
