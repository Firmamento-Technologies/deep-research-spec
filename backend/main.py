"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app

from api.runs import router as runs_router
from api.knowledge_spaces import router as spaces_router
from api.companion import router as companion_router
from api.metrics import router as metrics_router
from api.exports import router as exports_router
from api.auth import router as auth_router
from api.middleware import RequestIDMiddleware, TimingMiddleware
from database.connection import init_db, close_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    await init_db()
    yield
    # Shutdown
    await close_db()


app = FastAPI(
    title="Deep Research System",
    description="AI-powered research document generation with multi-user authentication",
    version="1.0.0",
    lifespan=lifespan,
)

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(TimingMiddleware)

# Routers
app.include_router(auth_router)  # Authentication (public)
app.include_router(runs_router)  # Protected
app.include_router(spaces_router)  # Protected
app.include_router(companion_router)  # Protected
app.include_router(metrics_router)  # Protected
app.include_router(exports_router)  # Protected

# Prometheus metrics
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.get("/health/detailed")
async def health_detailed():
    return {
        "status": "healthy",
        "database": "connected",
        "redis": "connected",
    }
