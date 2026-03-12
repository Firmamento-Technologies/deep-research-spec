#!/usr/bin/env python3
"""DRS — Deep Research System — Cross-Platform Quick Setup.

Usage:
    python setup_drs.py                  # Full setup (venv + deps + docker + verify)
    python setup_drs.py --skip-docker    # Skip Docker services
    python setup_drs.py --skip-venv      # Skip venv creation (use current env)
    python setup_drs.py --verify-only    # Only run verification checks
"""
from __future__ import annotations

import argparse
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Colors (ANSI, disabled on Windows without VT support)
# ---------------------------------------------------------------------------
if sys.stdout.isatty() and (os.name != "nt" or os.environ.get("WT_SESSION")):
    GREEN, CYAN, YELLOW, RED, BOLD, NC = (
        "\033[32m", "\033[36m", "\033[33m", "\033[31m", "\033[1m", "\033[0m",
    )
else:
    GREEN = CYAN = YELLOW = RED = BOLD = NC = ""


def info(msg: str) -> None:
    print(f"{CYAN}[INFO]{NC}  {msg}")


def ok(msg: str) -> None:
    print(f"{GREEN}[ OK ]{NC}  {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}[WARN]{NC}  {msg}")


def fail(msg: str) -> None:
    print(f"{RED}[FAIL]{NC}  {msg}", file=sys.stderr)
    sys.exit(1)


ROOT = Path(__file__).resolve().parent
IS_WIN = platform.system() == "Windows"
VENV_DIR = ROOT / "venv"
VENV_PYTHON = VENV_DIR / ("Scripts" if IS_WIN else "bin") / "python"
VENV_PIP = VENV_DIR / ("Scripts" if IS_WIN else "bin") / "pip"


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

def check_python() -> None:
    """Verify Python >= 3.11."""
    v = sys.version_info
    if (v.major, v.minor) < (3, 11):
        fail(f"Python 3.11+ required, got {v.major}.{v.minor}.{v.micro}")
    ok(f"Python {v.major}.{v.minor}.{v.micro}")


def check_docker() -> bool:
    """Check if Docker + Compose are available. Returns False if missing."""
    docker = shutil.which("docker")
    if not docker:
        warn("Docker not found — skipping container services")
        return False
    try:
        ver = subprocess.check_output(
            ["docker", "--version"], text=True, stderr=subprocess.DEVNULL
        ).strip()
        ok(f"Docker: {ver}")
    except Exception:
        warn("Docker found but not responding — is Docker Desktop running?")
        return False

    try:
        subprocess.check_output(
            ["docker", "compose", "version"], text=True, stderr=subprocess.DEVNULL
        )
        ok("Docker Compose v2 available")
    except Exception:
        warn("Docker Compose v2 not found — run 'docker compose' manually")
        return False

    return True


def create_venv() -> None:
    """Create virtual environment if it doesn't exist."""
    if VENV_DIR.exists() and VENV_PYTHON.exists():
        ok(f"Venv already exists at {VENV_DIR}")
        return
    info(f"Creating venv at {VENV_DIR} ...")
    subprocess.check_call([sys.executable, "-m", "venv", str(VENV_DIR)])
    ok("Venv created")


def install_deps() -> None:
    """Install all dependencies in the correct order to avoid conflicts."""
    pip = str(VENV_PIP)

    info("Upgrading pip ...")
    subprocess.check_call(
        [pip, "install", "--upgrade", "pip"],
        stdout=subprocess.DEVNULL,
    )

    # 1) Install backend deps (the primary, more constrained set)
    info("Installing backend dependencies ...")
    subprocess.check_call(
        [pip, "install", "-r", str(ROOT / "backend" / "requirements.txt")],
    )
    ok("Backend dependencies installed")

    # 2) Install root-level extras (test tools, linters) that aren't in backend
    info("Installing test & dev tools ...")
    subprocess.check_call(
        [pip, "install",
         "pytest>=8.0", "pytest-asyncio>=0.23.0", "pytest-timeout>=2.3.0",
         "pytest-cov>=5.0", "ruff>=0.7.0", "mypy>=1.11",
         "types-PyYAML>=6.0", "types-redis>=4.6"],
        stdout=subprocess.DEVNULL,
    )
    ok("Test & dev tools installed")


def setup_env() -> None:
    """Copy .env.example to .env if it doesn't exist."""
    env_file = ROOT / ".env"
    example = ROOT / ".env.example"
    if env_file.exists():
        ok(".env already exists")
        return
    if not example.exists():
        warn(".env.example not found — skipping .env setup")
        return
    shutil.copy2(example, env_file)
    ok(".env created from template — edit it to add your API keys")


def start_docker() -> None:
    """Start infrastructure services (postgres, redis, minio)."""
    info("Starting Docker services (postgres, redis, minio) ...")
    subprocess.check_call(
        ["docker", "compose", "up", "-d", "postgres", "redis", "minio"],
        cwd=str(ROOT),
    )

    # Wait for health
    info("Waiting for services to become healthy ...")
    for svc in ["drs-postgres", "drs-redis", "drs-minio"]:
        try:
            for _ in range(24):  # 24 * 5s = 120s max
                result = subprocess.check_output(
                    ["docker", "inspect", "--format",
                     "{{.State.Health.Status}}", svc],
                    text=True, stderr=subprocess.DEVNULL,
                ).strip()
                if result == "healthy":
                    ok(f"{svc} is healthy")
                    break
                import time
                time.sleep(5)
            else:
                warn(f"{svc} did not become healthy within 120s")
        except Exception:
            warn(f"Could not check health for {svc}")


def verify() -> None:
    """Run smoke test and unit tests."""
    py = str(VENV_PYTHON)

    info("Running smoke test (config loader import) ...")
    try:
        subprocess.check_call(
            [py, "-c",
             "import sys; sys.path.insert(0,'.'); "
             "from src.config.loader import config; "
             "print('Config loader:', type(config).__name__)"],
            cwd=str(ROOT),
        )
        ok("Smoke test passed")
    except subprocess.CalledProcessError:
        warn("Smoke test failed — check src/config/loader.py")

    info("Running unit tests ...")
    result = subprocess.run(
        [py, "-m", "pytest", "tests/unit/", "-q", "--timeout=30", "--tb=short"],
        cwd=str(ROOT),
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )
    if result.returncode == 0:
        ok("All unit tests passed")
    else:
        warn(f"Some unit tests failed (exit code {result.returncode})")


def print_summary(docker_ok: bool) -> None:
    print(f"\n{BOLD}{GREEN}{'=' * 56}{NC}")
    print(f"{BOLD}{GREEN}  DRS — Setup Complete{NC}")
    print(f"{BOLD}{GREEN}{'=' * 56}{NC}\n")

    if IS_WIN:
        print(f"  Activate venv:   {BOLD}venv\\Scripts\\activate{NC}")
    else:
        print(f"  Activate venv:   {BOLD}source venv/bin/activate{NC}")

    print(f"  Run unit tests:  {BOLD}python -m pytest tests/unit/ -q{NC}")
    print(f"  Run all tests:   {BOLD}python -m pytest tests/ -q{NC}")
    print(f"  Start backend:   {BOLD}cd backend && uvicorn main:app --port 8000{NC}")

    if docker_ok:
        print(f"\n  {BOLD}Docker services:{NC}")
        print(f"    PostgreSQL     localhost:5432")
        print(f"    Redis          localhost:6379")
        print(f"    MinIO Console  http://localhost:9001")

    print(f"\n  {YELLOW}Edit .env to add your LLM API keys before running the pipeline.{NC}\n")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="DRS Quick Setup")
    parser.add_argument("--skip-docker", action="store_true", help="Skip Docker services")
    parser.add_argument("--skip-venv", action="store_true", help="Use current Python env")
    parser.add_argument("--verify-only", action="store_true", help="Only run verification")
    args = parser.parse_args()

    print(f"\n{BOLD}{CYAN}DRS — Deep Research System — Quick Setup{NC}\n")

    check_python()

    if args.verify_only:
        verify()
        return

    docker_ok = False
    if not args.skip_docker:
        docker_ok = check_docker()

    if not args.skip_venv:
        create_venv()

    install_deps()
    setup_env()

    if docker_ok and not args.skip_docker:
        start_docker()

    verify()
    print_summary(docker_ok)


if __name__ == "__main__":
    main()
