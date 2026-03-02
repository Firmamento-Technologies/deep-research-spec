# Settings endpoints.
# GET  /api/settings  — return current config
# PUT  /api/settings  — persist config (full impl STEP 12)

import os
from fastapi import APIRouter
from database.schemas import SettingsUpdate

router = APIRouter()


@router.get("/settings")
async def get_settings():
    return {
        "openrouter_key_configured": bool(os.getenv("OPENROUTER_API_KEY")),
        "model_assignments":         {},
        "default_preset":            "Balanced",
        "default_budget":            50.0,
        "default_style_profile":     "academic",
        "connectors": {
            "Perplexity Sonar": True,
            "Tavily":           False,
            "Brave Search":     False,
            "Web Scraper":      False,
        },
        "webhook_url":    "",
        "webhook_events": {},
    }


@router.put("/settings")
async def update_settings(body: SettingsUpdate):
    # Persists to PostgreSQL settings table and reloads env — STEP 12
    return {"status": "ok"}
