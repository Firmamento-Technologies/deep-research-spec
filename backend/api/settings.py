from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from database.connection import get_db
from database.models import Settings
from pydantic import BaseModel, ConfigDict
from typing import Dict, Any
import json
import os

router = APIRouter()


# ------------------------------------------------------------------ #
# Pydantic model for Settings
# ------------------------------------------------------------------ #
class SettingsPayload(BaseModel):
    model_config = ConfigDict(protected_namespaces=())
    
    api_keys: Dict[str, str]
    model_assignments: Dict[str, str]
    default_config: Dict[str, Any]
    connectors: Dict[str, bool]
    webhooks: Dict[str, Any]


# ------------------------------------------------------------------ #
# GET /api/settings
# ------------------------------------------------------------------ #
@router.get("/settings")
async def get_settings(db: AsyncSession = Depends(get_db)):
    """
    Returns current settings. If no record exists, returns defaults.
    """
    result = await db.execute(select(Settings).limit(1))
    row = result.scalars().first()

    if not row:
        # Return defaults
        return _default_settings()

    return {
        "api_keys": row.api_keys or {},
        "model_assignments": row.model_assignments or {},
        "default_config": row.default_config or {},
        "connectors": row.connectors or {},
        "webhooks": row.webhooks or {},
    }


# ------------------------------------------------------------------ #
# PUT /api/settings
# ------------------------------------------------------------------ #
@router.put("/settings")
async def update_settings(
    payload: SettingsPayload,
    db: AsyncSession = Depends(get_db),
):
    """
    Saves settings to PostgreSQL and updates .env file for API keys.
    """
    # Upsert to Settings table
    result = await db.execute(select(Settings).limit(1))
    row = result.scalars().first()

    if row:
        # Update existing
        await db.execute(
            update(Settings)
            .where(Settings.id == row.id)
            .values(
                api_keys=payload.api_keys,
                model_assignments=payload.model_assignments,
                default_config=payload.default_config,
                connectors=payload.connectors,
                webhooks=payload.webhooks,
            )
        )
    else:
        # Insert new
        new_settings = Settings(
            api_keys=payload.api_keys,
            model_assignments=payload.model_assignments,
            default_config=payload.default_config,
            connectors=payload.connectors,
            webhooks=payload.webhooks,
        )
        db.add(new_settings)

    await db.commit()

    # Update .env file for OpenRouter API key (optional)
    if "openrouter" in payload.api_keys:
        _update_env_file("OPENROUTER_API_KEY", payload.api_keys["openrouter"])

    return {"status": "ok", "message": "Settings saved successfully"}


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #
def _default_settings() -> dict:
    return {
        "api_keys": {
            "openrouter": os.getenv("OPENROUTER_API_KEY", ""),
        },
        "model_assignments": {
            "planner": "google/gemini-2.5-pro",
            "researcher": "perplexity/sonar-pro",
            "source_synth": "anthropic/claude-sonnet-4",
            "writer_a": "anthropic/claude-opus-4-5",
            "writer_b": "anthropic/claude-opus-4-5",
            "writer_c": "anthropic/claude-opus-4-5",
            "writer_single": "anthropic/claude-opus-4-5",
            "fusor": "openai/o3",
            "post_draft_analyzer": "google/gemini-2.5-pro",
            "researcher_targeted": "perplexity/sonar-pro",
            "style_fixer": "anthropic/claude-sonnet-4",
            "r1": "openai/o3",
            "r2": "openai/o3-mini",
            "r3": "openai/o3-mini",
            "f1": "google/gemini-2.5-pro",
            "f2": "google/gemini-2.5-pro",
            "f3": "google/gemini-2.5-pro",
            "s1": "anthropic/claude-sonnet-4",
            "s2": "anthropic/claude-haiku-3",
            "s3": "anthropic/claude-haiku-3",
            "context_compressor": "qwen/qwen3-7b",
            "coherence_guard": "google/gemini-2.5-pro",
            "reflector": "openai/o3",
            "span_editor": "anthropic/claude-sonnet-4",
        },
        "default_config": {
            "preset": "Balanced",
            "max_budget": 50.0,
            "style_profile": "academic",
        },
        "connectors": {
            "perplexity": True,
            "tavily": False,
            "brave": False,
            "scraper": True,
        },
        "webhooks": {
            "url": "",
            "events": [],
        },
    }


def _update_env_file(key: str, value: str):
    """
    Updates a single key in .env file.
    If key does not exist, appends it.
    WARNING: This is a naive implementation.
    For production, use a proper .env library (e.g. python-dotenv).
    """
    env_path = ".env"
    if not os.path.exists(env_path):
        with open(env_path, "w") as f:
            f.write(f"{key}={value}\n")
        return

    with open(env_path, "r") as f:
        lines = f.readlines()

    found = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f"{key}={value}\n"
            found = True
            break

    if not found:
        lines.append(f"{key}={value}\n")

    with open(env_path, "w") as f:
        f.writelines(lines)
