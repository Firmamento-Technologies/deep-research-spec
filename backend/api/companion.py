# Companion chat endpoint.
# Spec: UI_BUILD_PLAN.md Section 6.
#
# POST /api/companion/chat
#   → calls OpenRouter with the companion system prompt
#   → returns { reply, chips?, action? }

from __future__ import annotations
import json
import logging
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from database.schemas import CompanionChatRequest, CompanionChatResponse, Chip
from database.connection import get_async_session
from database.models import Settings
from api.dependencies import require_user
from config.settings import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["companion"], dependencies=[Depends(require_user)])

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "companion_system.txt"
_SYSTEM_PROMPT: str = _PROMPT_PATH.read_text(encoding="utf-8")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
COMPANION_MODEL = "anthropic/claude-sonnet-4"
MAX_HISTORY = 10   # last N messages sent as context
MAX_USER_CONTEXT_CHARS = 2_000
REQUEST_TIMEOUT_S = 45.0
MAX_RETRIES = 2
VALID_ACTIONS = {"START_RUN", "SHOW_SECTION", "CANCEL_RUN"}


async def _get_api_key() -> str:
    """Read the OpenRouter API key, preferring the DB value over env var."""
    try:
        async with get_async_session() as session:
            result = await session.execute(select(Settings).limit(1))
            row = result.scalars().first()
            if row and row.api_keys:
                db_key = row.api_keys.get("openrouter", "")
                if db_key and not db_key.startswith("or-xxxx"):
                    return db_key
    except Exception:
        pass  # DB not available — fall through to env var

    return settings.openrouter_api_key


def _build_messages(body: CompanionChatRequest) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [{"role": "system", "content": _SYSTEM_PROMPT}]

    for msg in body.conversation_history[-MAX_HISTORY:]:
        oai_role = "user" if msg.role == "user" else "assistant"
        messages.append({"role": oai_role, "content": msg.content})

    user_content = body.message
    if body.current_run_state:
        ctx = json.dumps(body.current_run_state, default=str)[:MAX_USER_CONTEXT_CHARS]
        user_content += f"\n\n[STATO RUN ATTUALE]\n{ctx}"

    user_content += (
        "\n\nRispondi ESCLUSIVAMENTE con un JSON object con questa struttura:"
        ' {"reply": "<testo risposta>",'
        ' "chips": [{"label": "...", "value": "..."}] oppure null,'
        ' "action": {"type": "START_RUN", "params": {...}} oppure null}'
    )
    messages.append({"role": "user", "content": user_content})
    return messages


async def _call_openrouter(messages: list[dict[str, str]], api_key: str) -> str:
    payload = {
        "model": COMPANION_MODEL,
        "messages": messages,
        "response_format": {"type": "json_object"},
        "temperature": 0.7,
        "max_tokens": 1_024,
    }

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT_S) as client:
                resp = await client.post(
                    OPENROUTER_URL,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "http://localhost:3001",
                        "X-Title": "DRS Companion",
                    },
                    json=payload,
                )

            if resp.status_code == 200:
                data = resp.json()
                return str(data.get("choices", [{}])[0].get("message", {}).get("content", ""))

            if resp.status_code in (429, 500, 502, 503, 504) and attempt < MAX_RETRIES:
                continue

            raise HTTPException(status_code=502, detail=f"OpenRouter error: {resp.text[:300]}")

        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                continue
            raise HTTPException(status_code=502, detail="OpenRouter unreachable or timed out")
        except json.JSONDecodeError as exc:
            last_error = exc
            if attempt < MAX_RETRIES:
                continue
            raise HTTPException(status_code=502, detail="OpenRouter returned invalid JSON")

    raise HTTPException(status_code=502, detail=f"OpenRouter request failed: {last_error}")


def _sanitize_companion_payload(raw_content: str) -> CompanionChatResponse:
    try:
        parsed: dict[str, Any] = json.loads(raw_content)
    except json.JSONDecodeError:
        return CompanionChatResponse(reply=raw_content)

    reply = parsed.get("reply", raw_content)
    if not isinstance(reply, str) or not reply.strip():
        reply = "Ho ricevuto una risposta non valida dal modello. Riprova tra pochi secondi."

    chips_raw = parsed.get("chips")
    chips: list[Chip] | None = None
    if isinstance(chips_raw, list):
        safe_chips: list[Chip] = []
        for item in chips_raw[:5]:
            if isinstance(item, dict):
                label = item.get("label")
                value = item.get("value")
                if isinstance(label, str) and isinstance(value, str):
                    safe_chips.append(Chip(label=label[:80], value=value[:160]))
        chips = safe_chips or None

    action = parsed.get("action")
    safe_action = None
    if isinstance(action, dict):
        action_type = action.get("type")
        if isinstance(action_type, str) and action_type in VALID_ACTIONS:
            safe_action = action

    return CompanionChatResponse(reply=reply, chips=chips, action=safe_action)


@router.post("/companion/chat", response_model=CompanionChatResponse)
async def companion_chat(body: CompanionChatRequest) -> CompanionChatResponse:
    api_key = await _get_api_key()
    if not api_key or api_key.startswith("or-xxxx"):
        raise HTTPException(
            status_code=503,
            detail="OPENROUTER_API_KEY not configured. Go to Settings and enter a valid API key.",
        )

    messages = _build_messages(body)
    raw_content = await _call_openrouter(messages, api_key)

    response = _sanitize_companion_payload(raw_content)
    logger.info("Companion response ready (chips=%s, action=%s)", bool(response.chips), bool(response.action))
    return response
