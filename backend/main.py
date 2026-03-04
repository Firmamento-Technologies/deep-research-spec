from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import runs, companion, metrics, settings, knowledge_spaces
from database.connection import init_db
from services.redis_client import redis as redis_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: initialise DB tables. Shutdown: close Redis connection."""
    await init_db()
    yield
    await redis_client.aclose()


app = FastAPI(title="DRS API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "http://frontend:80"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(runs.router,             prefix="/api")
app.include_router(companion.router,        prefix="/api")
app.include_router(metrics.router,          prefix="/api")
app.include_router(settings.router,         prefix="/api")
app.include_router(knowledge_spaces.router, prefix="/api")  # Knowledge Spaces


@app.get("/health")
def health():
    return {"status": "ok"}
