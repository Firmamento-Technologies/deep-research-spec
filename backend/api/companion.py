# Companion chat endpoint.
# Spec: UI_BUILD_PLAN.md Section 6.
#
# POST /api/companion/chat
#   → calls OpenRouter with the companion system prompt
#   → returns { reply, chips?, action? }

from __future__ import annotations
import json
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException

from database.schemas import CompanionChatRequest, CompanionChatResponse
from config.settings import settings

router = APIRouter()

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "companion_system.txt"
_SYSTEM_PROMPT: str = _PROMPT_PATH.read_text(encoding="utf-8")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
COMPANION_MODEL = "anthropic/claude-sonnet-4-6"
MAX_HISTORY = 10   # last N messages sent as context


@router.post("/companion/chat", response_model=CompanionChatResponse)
async def companion_chat(body: CompanionChatRequest) -> CompanionChatResponse:
    if not settings.openrouter_api_key:
        raise HTTPException(status_code=503, detail="OPENROUTER_API_KEY not configured")

    # Build message list
    messages: list[dict] = [{"role": "system", "content": _SYSTEM_PROMPT}]

    for msg in body.conversation_history[-MAX_HISTORY:]:
        oai_role = "user" if msg.role == "user" else "assistant"
        messages.append({"role": oai_role, "content": msg.content})

    # Append current user message + optional run state context
    user_content = body.message
    if body.current_run_state:
        ctx = json.dumps(body.current_run_state, default=str)[:2_000]
        user_content += f"\n\n[STATO RUN ATTUALE]\n{ctx}"

    # Instruct model to reply with a JSON object
    user_content += (
        "\n\nRispondi ESCLUSIVAMENTE con un JSON object con questa struttura:"
        ' {"reply": "<testo risposta>",'
        ' "chips": [{"label": "...", "value": "..."}] oppure null,'
        ' "action": {"type": "START_RUN", "params": {...}} oppure null}'
    )
    messages.append({"role": "user", "content": user_content})

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "Content-Type":  "application/json",
                "HTTP-Referer":  "http://localhost:3001",
                "X-Title":       "DRS Companion",
            },
            json={
                "model":           COMPANION_MODEL,
                "messages":        messages,
                "response_format": {"type": "json_object"},
                "temperature":     0.7,
                "max_tokens":      1_024,
            },
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"OpenRouter error: {resp.text[:300]}")

    raw_content: str = resp.json()["choices"][0]["message"]["content"]

    try:
        parsed = json.loads(raw_content)
        return CompanionChatResponse(
            reply  = parsed.get("reply", raw_content),
            chips  = parsed.get("chips"),
            action = parsed.get("action"),
        )
    except json.JSONDecodeError:
        # Fallback: return the raw text as reply
        return CompanionChatResponse(reply=raw_content)
