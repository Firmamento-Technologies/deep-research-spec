"""FastAPI application entry point for DRS.

Provides:
- RESTful API for research pipeline orchestration
- SSE streaming for real-time updates
- Health checks and monitoring endpoints
- CORS, error handling, and request tracing
- OpenAPI documentation

Usage:
    # Development
    uvicorn main:app --reload --port 8000
    
    # Production
    uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
    
    # With Gunicorn
    gunicorn main:app --worker-class uvicorn.workers.UvicornWorker --workers 4

Spec: §10 API specification, §24 Deployment
"""

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api import runs, companion, metrics, settings, knowledge_spaces
from api.middleware import RequestIDMiddleware, TimingMiddleware
from database.connection import init_db
from services.redis_client import redis as redis_client
from src.services.run_manager import configure_run_manager
from services.sse_broker import get_broker
from src.llm.client import LLMError, BudgetExceededError
from config.settings import settings as app_settings

logger = logging.getLogger(__name__)

# Application start time for uptime calculation
START_TIME = time.time()


# ---------------------------------------------------------------------------
# Lifespan Management
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager.
    
    Startup:
    - Initialize database tables
    - Configure RunManager with checkpointer
    - Initialize SSEBroker singleton
    - Log startup info
    
    Shutdown:
    - Close Redis connection
    - Cleanup resources
    """
    logger.info("=" * 60)
    logger.info("Starting DRS API Server")
    logger.info("=" * 60)
    
    # Database initialization
    logger.info("Initializing database...")
    await init_db()
    logger.info("✅ Database initialized")
    
    # Configure RunManager
    logger.info("Configuring RunManager...")
    checkpointer_dsn = str(app_settings.database_url).replace(
        "postgresql+asyncpg://", "postgresql://"
    )
    configure_run_manager(checkpointer_dsn=checkpointer_dsn)
    logger.info("✅ RunManager configured")
    
    # Initialize SSEBroker
    logger.info("Initializing SSEBroker...")
    broker = get_broker()
    logger.info("✅ SSEBroker initialized")
    
    logger.info("=" * 60)
    logger.info("DRS API Server ready")
    logger.info(f"Documentation: http://localhost:8000/docs")
    logger.info("=" * 60)
    
    yield
    
    # Shutdown
    logger.info("Shutting down DRS API Server...")
    await redis_client.aclose()
    logger.info("✅ Shutdown complete")


# ---------------------------------------------------------------------------
# FastAPI Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Deep Research System API",
    description="AI-powered research document generation pipeline",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

# CORS
allowed_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://frontend:80",
]

# Add custom origins from env
if app_settings.allowed_origins:
    allowed_origins.extend(app_settings.allowed_origins.split(","))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom middleware
app.add_middleware(RequestIDMiddleware)
app.add_middleware(TimingMiddleware)

# ---------------------------------------------------------------------------
# Exception Handlers
# ---------------------------------------------------------------------------

@app.exception_handler(LLMError)
async def llm_error_handler(request: Request, exc: LLMError):
    """Handle LLM API errors."""
    logger.error(
        "[%s] LLM error: %s",
        request.state.request_id if hasattr(request.state, "request_id") else "?",
        exc,
    )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "detail": f"LLM service error: {str(exc)}",
            "request_id": getattr(request.state, "request_id", None),
        },
    )


@app.exception_handler(BudgetExceededError)
async def budget_exceeded_handler(request: Request, exc: BudgetExceededError):
    """Handle budget exceeded errors."""
    logger.warning(
        "[%s] Budget exceeded: spent=$%.4f, max=$%.4f",
        request.state.request_id if hasattr(request.state, "request_id") else "?",
        exc.spent,
        exc.max_budget,
    )
    return JSONResponse(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        content={
            "detail": str(exc),
            "spent": exc.spent,
            "max_budget": exc.max_budget,
            "request_id": getattr(request.state, "request_id", None),
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.exception(
        "[%s] Unhandled exception: %s",
        request.state.request_id if hasattr(request.state, "request_id") else "?",
        exc,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            "request_id": getattr(request.state, "request_id", None),
        },
    )


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(runs.router, tags=["Runs"])
app.include_router(companion.router, tags=["Companion"])
app.include_router(metrics.router, tags=["Metrics"])
app.include_router(settings.router, tags=["Settings"])
app.include_router(knowledge_spaces.router, tags=["Knowledge Spaces"])

# ---------------------------------------------------------------------------
# Health & Monitoring Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Health"])
def health_check():
    """Basic health check endpoint.
    
    Returns:
        {"status": "ok"}
    """
    return {"status": "ok"}


@app.get("/health/detailed", tags=["Health"])
async def detailed_health_check():
    """Detailed health check with service status.
    
    Checks:
    - Database connectivity
    - Redis connectivity
    - LLM API availability
    
    Returns:
        Status dict with service health and uptime.
    """
    services = {
        "database": "unknown",
        "redis": "unknown",
        "llm": "unknown",
    }
    
    # Check database
    try:
        from database.connection import get_db
        async for db in get_db():
            await db.execute("SELECT 1")
            services["database"] = "connected"
            break
    except Exception as exc:
        logger.error("Database health check failed: %s", exc)
        services["database"] = "error"
    
    # Check Redis
    try:
        await redis_client.ping()
        services["redis"] = "connected"
    except Exception as exc:
        logger.error("Redis health check failed: %s", exc)
        services["redis"] = "error"
    
    # Check LLM (just validate API key exists)
    try:
        from src.llm.client import get_llm_client
        client = await get_llm_client()
        if client.api_key:
            services["llm"] = "ok"
        else:
            services["llm"] = "no_api_key"
    except Exception as exc:
        logger.error("LLM health check failed: %s", exc)
        services["llm"] = "error"
    
    # Overall status
    all_healthy = all(s in ["connected", "ok"] for s in services.values())
    status = "healthy" if all_healthy else "degraded"
    
    return {
        "status": status,
        "services": services,
        "version": "1.0.0",
        "uptime_seconds": int(time.time() - START_TIME),
    }


@app.get("/version", tags=["Info"])
def version_info():
    """Get API version information."""
    return {
        "version": "1.0.0",
        "api_name": "Deep Research System",
        "uptime_seconds": int(time.time() - START_TIME),
    }


# ---------------------------------------------------------------------------
# Root Endpoint
# ---------------------------------------------------------------------------

@app.get("/", tags=["Info"])
def root():
    """Root endpoint with API information."""
    return {
        "name": "Deep Research System API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }
