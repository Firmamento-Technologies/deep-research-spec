from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter()


class CompanionMessage(BaseModel):
    role: str  # user | companion
    content: str


class CompanionChatRequest(BaseModel):
    message: str
    conversation_history: List[CompanionMessage] = []
    current_run_state: Optional[dict] = None


@router.post("/companion/chat")
async def companion_chat(body: CompanionChatRequest):
    # TODO: STEP 6 — call LLM (settings.companion_model) with companion_system.txt prompt
    # Parse response JSON: {reply, chips, action}
    # If action.type == START_RUN: call RunManager.start_run(action.params)
    return {
        "reply": "Ciao! Dimmi l'argomento che vuoi approfondire e quante parole vuoi.",
        "chips": None,
        "action": None,
    }
