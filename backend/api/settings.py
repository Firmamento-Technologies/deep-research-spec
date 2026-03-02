from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Dict

router = APIRouter()


class SettingsUpdate(BaseModel):
    openrouter_api_key: Optional[str] = None
    model_assignments: Optional[Dict[str, str]] = None
    default_preset: Optional[str] = None
    default_budget: Optional[float] = None
    connectors: Optional[Dict[str, bool]] = None
    webhook_url: Optional[str] = None


@router.get("/settings")
async def get_settings():
    # TODO: STEP 12 — read from PostgreSQL app_settings table
    return {}


@router.put("/settings")
async def update_settings(body: SettingsUpdate):
    # TODO: STEP 12 — upsert to PostgreSQL app_settings + reload config
    return {"updated": True}
