from __future__ import annotations

import hashlib
import json

import httpx
from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from app.api.deps import CurrentUser
from app.core.config import settings

router = APIRouter(prefix="/realtime", tags=["realtime"])


class RealtimeContext(BaseModel):
    project_id: str
    stage: str
    steps: list[dict]


def _tool(name: str, description: str, properties: dict, required: list[str]) -> dict:
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": {"type": "object", "properties": properties, "required": required, "additionalProperties": False},
    }


def _tools() -> list[dict]:
    return [
        _tool("start_step", "Start a protocol step before recording its result.", {"case_id": {"type": "string"}, "step_id": {"type": "string"}}, ["case_id", "step_id"]),
        _tool("record_step_result", "Record a completed protocol step as passed or failed. Ask for observed details when absent.", {"case_id": {"type": "string"}, "step_id": {"type": "string"}, "status": {"type": "string", "enum": ["passed", "failed"]}, "observed_result": {"type": "string"}, "deviation_reference": {"type": ["string", "null"]}}, ["case_id", "step_id", "status", "observed_result"]),
        _tool("review_case", "Add or update the formal review state for a test case.", {"case_id": {"type": "string"}, "status": {"type": "string", "enum": ["approved", "needs_changes", "rejected"]}, "comment": {"type": ["string", "null"]}}, ["case_id", "status"]),
        _tool("complete_stage", "Complete the active qualification stage after its generated cases and required protocol work are ready.", {"step_id": {"type": "string"}}, ["step_id"]),
        _tool("search_step_visuals", "Find visual references that can help explain a protocol step. This only searches and saves references; it never changes execution status.", {"case_id": {"type": "string"}, "step_id": {"type": "string"}, "query": {"type": "string"}}, ["case_id", "step_id", "query"]),
    ]


@router.post("/session")
async def create_realtime_session(request: Request, current_user: CurrentUser, voice_context: str = Header(..., alias="X-Voice-Context")) -> str:
    if not settings.OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="Realtime voice is not configured")
    try:
        context = RealtimeContext.model_validate_json(voice_context)
    except ValueError as error:
        raise HTTPException(status_code=422, detail="Invalid voice context") from error
    step_lines = "\n".join(f"- {item.get('id')}: step {item.get('step_number')}, {item.get('status')}: {item.get('action')}" for item in context.steps)
    instructions = f"""You are Vexa's qualification workflow assistant. Help the user understand and execute the active qualification stage.\n
Active stage: {context.stage}, project {context.project_id}. Each step line includes its test-case ID so always select the correct case before mutating it.\n
Protocol steps and cases:\n{step_lines}\n
Rules:\n- Be concise and calm. Never claim regulatory compliance or that a test passed unless the user explicitly reports the observed result and you record it through a function.\n- Explain that review approves the generated protocol, while execution records what happened during a step.\n- Before record_step_result, confirm the step and ask for an observed result if needed.\n- Use function calls for mutations; do not tell the user an action happened until the function result confirms it.\n- Do not invent limits, evidence, observations, or deviations.\n- Search visuals only for educational guidance and mention the source; visuals are not acceptance evidence.\n"""
    session = {"type": "realtime", "model": settings.OPENAI_REALTIME_MODEL, "instructions": instructions, "audio": {"output": {"voice": settings.OPENAI_REALTIME_VOICE}}, "tools": _tools()}
    safety_id = hashlib.sha256(str(current_user.id).encode()).hexdigest()
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                "https://api.openai.com/v1/realtime/calls",
                headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}", "OpenAI-Safety-Identifier": safety_id},
                files={"sdp": (None, (await request.body()).decode("utf-8"), "application/sdp"), "session": (None, json.dumps(session), "application/json")},
            )
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail="Unable to create realtime voice session") from error
    if not response.is_success:
        raise HTTPException(status_code=502, detail=f"OpenAI rejected the realtime voice session ({response.status_code})")
    return response.text
