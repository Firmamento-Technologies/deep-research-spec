#!/usr/bin/env bash
# =============================================================================
# DRS — Deep Research System — One-Click Installer
# Usage: ./install.sh [--skip-build] [--no-start] [--help]
# =============================================================================
set -euo pipefail

# ---- Colors & Helpers --------------------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

info()  { printf "${CYAN}[INFO]${NC}  %s\n" "$*"; }
ok()    { printf "${GREEN}[OK]${NC}    %s\n" "$*"; }
warn()  { printf "${YELLOW}[WARN]${NC}  %s\n" "$*"; }
fail()  { printf "${RED}[ERROR]${NC} %s\n" "$*" >&2; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

SKIP_BUILD=false
NO_START=false

# ---- CLI Args ----------------------------------------------------------------
usage() {
    cat <<EOF
${BOLD}DRS — Deep Research System Installer${NC}

Usage: ./install.sh [OPTIONS]

Options:
  --skip-build   Skip Docker image build (use existing images)
  --no-start     Configure environment only, don't start services
  --help         Show this help message

Prerequisites (installed automatically if missing):
  - Docker >= 24.0
  - Docker Compose v2 (docker compose plugin)
  - Git, Make

What this script does:
  1. Checks and installs prerequisites
  2. Creates .env from template with secure random passwords
  3. Prompts for LLM API keys
  4. Builds Docker images and starts all 7 services
  5. Waits for health checks and prints access URLs
EOF
    exit 0
}

for arg in "$@"; do
    case "$arg" in
        --skip-build) SKIP_BUILD=true ;;
        --no-start)   NO_START=true ;;
        --help|-h)    usage ;;
        *) warn "Unknown option: $arg" ;;
    esac
done

# ---- OS Detection ------------------------------------------------------------
detect_os() {
    if [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
        PKG="brew"
    elif [[ -f /etc/debian_version ]]; then
        OS="debian"
        PKG="apt"
    elif [[ -f /etc/redhat-release ]] || [[ -f /etc/fedora-release ]]; then
        OS="rhel"
        PKG="dnf"
    else
        OS="unknown"
        PKG="unknown"
    fi
    info "Detected OS: $OS (package manager: $PKG)"
}

# ---- Prerequisites -----------------------------------------------------------
check_command() { command -v "$1" &>/dev/null; }

install_docker() {
    if check_command docker; then
        local ver
        ver=$(docker version --format '{{.Server.Version}}' 2>/dev/null || echo "0")
        local major="${ver%%.*}"
        if [[ "$major" -ge 24 ]]; then
            ok "Docker $ver already installed"
            return 0
        else
            warn "Docker $ver found but >= 24.0 required"
        fi
    fi

    info "Installing Docker..."
    case "$PKG" in
        apt)
            sudo apt-get update -qq
            sudo apt-get install -y -qq ca-certificates curl gnupg lsb-release
            sudo install -m 0755 -d /etc/apt/keyrings
            curl -fsSL https://download.docker.com/linux/$(. /etc/os-release && echo "$ID")/gpg | \
                sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg 2>/dev/null
            sudo chmod a+r /etc/apt/keyrings/docker.gpg
            echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
                https://download.docker.com/linux/$(. /etc/os-release && echo "$ID") \
                $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
            sudo apt-get update -qq
            sudo apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
            ;;
        dnf)
            sudo dnf install -y -q dnf-plugins-core
            sudo dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo 2>/dev/null || \
                sudo dnf config-manager --add-repo https://download.docker.com/linux/rhel/docker-ce.repo 2>/dev/null
            sudo dnf install -y -q docker-ce docker-ce-cli containerd.io docker-compose-plugin
            ;;
        brew)
            brew install --cask docker
            warn "Please open Docker Desktop to complete installation, then re-run this script."
            exit 0
            ;;
        *)
            fail "Cannot auto-install Docker on this OS. Please install Docker >= 24.0 manually: https://docs.docker.com/engine/install/"
            ;;
    esac

    sudo systemctl enable --now docker 2>/dev/null || true
    # Add current user to docker group (takes effect on next login)
    sudo usermod -aG docker "$USER" 2>/dev/null || true
    ok "Docker installed"
}

check_compose() {
    if docker compose version &>/dev/null; then
        ok "Docker Compose $(docker compose version --short) available"
    else
        fail "Docker Compose v2 plugin not found. Install it: https://docs.docker.com/compose/install/"
    fi
}

check_prerequisites() {
    info "Checking prerequisites..."

    install_docker
    check_compose

    for cmd in git make; do
        if check_command "$cmd"; then
            ok "$cmd found"
        else
            info "Installing $cmd..."
            case "$PKG" in
                apt)  sudo apt-get install -y -qq "$cmd" ;;
                dnf)  sudo dnf install -y -q "$cmd" ;;
                brew) brew install "$cmd" ;;
                *)    fail "Please install $cmd manually" ;;
            esac
            ok "$cmd installed"
        fi
    done
}

# ---- Environment Setup -------------------------------------------------------
generate_password() {
    # 24-char alphanumeric password
    tr -dc 'A-Za-z0-9' </dev/urandom | head -c 24 2>/dev/null || \
        openssl rand -base64 18
}

setup_env() {
    if [[ ! -f .env.example ]]; then
        fail ".env.example not found. Are you in the DRS project root?"
    fi

    if [[ -f .env ]]; then
        warn ".env already exists"
        read -rp "  Overwrite with fresh config? [y/N] " answer
        if [[ ! "$answer" =~ ^[Yy]$ ]]; then
            ok "Keeping existing .env"
            return 0
        fi
    fi

    info "Setting up .env configuration..."
    cp .env.example .env

    # Generate secure random passwords
    local pg_pass minio_pass grafana_pass
    pg_pass="$(generate_password)"
    minio_pass="$(generate_password)"
    grafana_pass="$(generate_password)"

    # Replace default passwords in .env
    sed -i.bak "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$pg_pass|" .env
    sed -i.bak "s|^MINIO_ROOT_PASSWORD=.*|MINIO_ROOT_PASSWORD=$minio_pass|" .env
    sed -i.bak "s|^GRAFANA_PASSWORD=.*|GRAFANA_PASSWORD=$grafana_pass|" .env
    rm -f .env.bak

    ok "Generated secure passwords for PostgreSQL, MinIO, Grafana"

    # Prompt for API keys
    echo ""
    printf "${BOLD}LLM API Key Configuration${NC}\n"
    echo "At least one API key is required for DRS to function."
    echo "Press Enter to skip any key you don't have."
    echo ""

    read -rp "  OpenRouter API Key (recommended): " openrouter_key
    if [[ -n "$openrouter_key" ]]; then
        sed -i.bak "s|^OPENROUTER_API_KEY=.*|OPENROUTER_API_KEY=$openrouter_key|" .env
        rm -f .env.bak
        ok "OpenRouter API key set"
    fi

    read -rp "  Anthropic API Key (optional): " anthropic_key
    if [[ -n "$anthropic_key" ]]; then
        sed -i.bak "s|^ANTHROPIC_API_KEY=.*|ANTHROPIC_API_KEY=$anthropic_key|" .env
        rm -f .env.bak
        ok "Anthropic API key set"
    fi

    read -rp "  OpenAI API Key (optional): " openai_key
    if [[ -n "$openai_key" ]]; then
        sed -i.bak "s|^OPENAI_API_KEY=.*|OPENAI_API_KEY=$openai_key|" .env
        rm -f .env.bak
        ok "OpenAI API key set"
    fi

    # Validate at least one key is set
    if [[ -z "$openrouter_key" && -z "$anthropic_key" && -z "$openai_key" ]]; then
        warn "No API keys provided. DRS will not be able to run LLM queries."
        warn "Edit .env later to add your keys."
    fi

    echo ""
    ok ".env configured successfully"
}

# ---- Build & Start -----------------------------------------------------------
build_and_start() {
    if [[ "$SKIP_BUILD" == true ]]; then
        info "Skipping build (--skip-build)"
    else
        info "Building Docker images (this may take a few minutes on first run)..."
        DOCKER_BUILDKIT=1 docker compose build --parallel 2>&1 | tail -5
        ok "Docker images built"
    fi

    if [[ "$NO_START" == true ]]; then
        ok "Environment configured. Run 'docker compose up -d' when ready."
        return 0
    fi

    info "Starting DRS services..."
    docker compose up -d
    ok "Containers started"
}

# ---- Health Check ------------------------------------------------------------
wait_for_services() {
    local max_wait=120
    local elapsed=0
    local interval=5

    info "Waiting for services to become healthy (timeout: ${max_wait}s)..."

    local services=("drs-postgres" "drs-redis" "drs-minio" "drs-backend" "drs-frontend")

    for svc in "${services[@]}"; do
        printf "  Waiting for %-16s " "$svc..."
        while [[ $elapsed -lt $max_wait ]]; do
            local health
            health=$(docker inspect --format='{{.State.Health.Status}}' "$svc" 2>/dev/null || echo "missing")
            if [[ "$health" == "healthy" ]]; then
                printf "${GREEN}healthy${NC}\n"
                break
            fi
            sleep "$interval"
            elapsed=$((elapsed + interval))
        done
        if [[ $elapsed -ge $max_wait ]]; then
            printf "${RED}timeout${NC}\n"
            warn "$svc did not become healthy within ${max_wait}s"
            warn "Check logs: docker compose logs $svc"
        fi
    done
}

# ---- Summary -----------------------------------------------------------------
print_summary() {
    # Read Grafana password from .env
    local grafana_pass
    grafana_pass=$(grep '^GRAFANA_PASSWORD=' .env 2>/dev/null | cut -d= -f2 || echo "admin")

    echo ""
    printf "${BOLD}${GREEN}============================================================${NC}\n"
    printf "${BOLD}${GREEN}  DRS — Deep Research System — Installation Complete!${NC}\n"
    printf "${BOLD}${GREEN}============================================================${NC}\n"
    echo ""
    printf "${BOLD}Access URLs:${NC}\n"
    echo "  Frontend        http://localhost:3001"
    echo "  API Docs        http://localhost:8000/docs"
    echo "  API Health      http://localhost:8000/health"
    echo "  MinIO Console   http://localhost:9001"
    echo "  Grafana         http://localhost:3002  (admin / $grafana_pass)"
    echo "  Prometheus      http://localhost:9091"
    echo ""
    printf "${BOLD}Useful commands:${NC}\n"
    echo "  make logs          View all service logs"
    echo "  make ps            Show container status"
    echo "  make down          Stop all services"
    echo "  make restart       Restart all services"
    echo "  make test          Run all tests"
    echo "  make seed-db       Load sample data"
    echo ""
    printf "${BOLD}Configuration:${NC}\n"
    echo "  Edit .env to update API keys or settings"
    echo "  Then run: make restart"
    echo ""
}

# ---- Main --------------------------------------------------------------------
main() {
    echo ""
    printf "${BOLD}${CYAN}╔══════════════════════════════════════════════════╗${NC}\n"
    printf "${BOLD}${CYAN}║    DRS — Deep Research System — Installer       ║${NC}\n"
    printf "${BOLD}${CYAN}╚══════════════════════════════════════════════════╝${NC}\n"
    echo ""

    detect_os
    check_prerequisites
    echo ""
    setup_env
    echo ""
    build_and_start

    if [[ "$NO_START" == false ]]; then
        wait_for_services
        print_summary
    fi
}

main "$@"
