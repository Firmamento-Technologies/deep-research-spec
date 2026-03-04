from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import runs, companion, metrics, settings, spaces
from database.connection import init_db
from services.redis_client import redis as redis_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: initialise DB + spaces data dir. Shutdown: close Redis."""
    await init_db()
    # Crea DATA_DIR se non esiste (idempotente)
    from services.space_service import DATA_DIR
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    yield
    await redis_client.aclose()


app = FastAPI(title="DRS API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "http://frontend:80"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(runs.router,      prefix="/api")
app.include_router(companion.router, prefix="/api")
app.include_router(metrics.router,   prefix="/api")
app.include_router(settings.router,  prefix="/api")
app.include_router(spaces.router,    prefix="/api")


@app.get("/health")
def health():
    return {"status": "ok"}
