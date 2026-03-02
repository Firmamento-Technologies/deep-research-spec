from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import runs, companion, metrics, settings

app = FastAPI(title="DRS API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001", "http://frontend:80"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(runs.router, prefix="/api")
app.include_router(companion.router, prefix="/api")
app.include_router(metrics.router, prefix="/api")
app.include_router(settings.router, prefix="/api")

@app.get("/health")
def health(): return {"status": "ok"}
