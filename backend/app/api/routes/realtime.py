from __future__ import annotations

import hashlib
import json
import uuid

import httpx
from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
from app.models import GeneratedTestCase, Project, QualificationStep, TestCaseStep

router = APIRouter(prefix="/realtime", tags=["realtime"])


class RealtimeContext(BaseModel):
    project_id: str
    stage: str
    steps: list[dict]


class RealtimeRequest(BaseModel):
    sdp: str
    project_id: uuid.UUID


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
async def create_realtime_session(session: SessionDep, request: Request, current_user: CurrentUser, voice_context: str | None = Header(None, alias="X-Voice-Context")) -> PlainTextResponse:
    if not settings.OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="Realtime voice is not configured")
    request_body = await request.body()
    if request.headers.get("content-type", "").startswith("application/json"):
        try:
            payload = RealtimeRequest.model_validate_json(request_body)
        except ValueError as error:
            raise HTTPException(status_code=422, detail="Invalid realtime session request") from error
        sdp = payload.sdp
        project_id = payload.project_id
    else:
        sdp = request_body.decode("utf-8")
        if not voice_context:
            raise HTTPException(status_code=422, detail="Realtime session requires voice context")
        try:
            legacy_context = RealtimeContext.model_validate_json(voice_context)
            project_id = uuid.UUID(legacy_context.project_id)
        except (ValueError, TypeError) as error:
            raise HTTPException(status_code=422, detail="Invalid voice context") from error

    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    active_step = session.exec(
        select(QualificationStep)
        .where(QualificationStep.project_id == project_id, QualificationStep.status == "in_progress")
        .order_by(QualificationStep.order_index)
    ).first()
    if not active_step:
        raise HTTPException(status_code=409, detail="There is no active qualification stage")
    cases = session.exec(select(GeneratedTestCase).where(GeneratedTestCase.step_id == active_step.id)).all()
    case_ids = [case.id for case in cases]
    protocol_steps = session.exec(select(TestCaseStep).where(TestCaseStep.generated_test_case_id.in_(case_ids))).all() if case_ids else []
    case_by_id = {case.id: case for case in cases}
    context = RealtimeContext(
        project_id=str(project_id),
        stage=active_step.stage,
        steps=[
            {
                "id": str(item.id),
                "step_number": item.step_number,
                "status": item.status,
                "action": item.action,
                "case_id": str(case_by_id[item.generated_test_case_id].id),
                "case_title": case_by_id[item.generated_test_case_id].title,
            }
            for item in protocol_steps
        ],
    )
    step_lines = "\n".join(f"- case {item.get('case_id')} / step {item.get('id')}: step {item.get('step_number')}, {item.get('status')}: {item.get('action')}" for item in context.steps)
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
                files={"sdp": (None, sdp, "application/sdp"), "session": (None, json.dumps(session), "application/json")},
            )
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail="Unable to create realtime voice session") from error
    if not response.is_success:
        error_body: dict = {}
        try:
            parsed = response.json()
            if isinstance(parsed, dict):
                error_body = parsed.get("error", parsed)
        except ValueError:
            pass
        error_code = error_body.get("code")
        if response.status_code in {401, 403} or error_code in {"model_not_found", "model_not_available"}:
            detail = (
                f"Realtime model '{settings.OPENAI_REALTIME_MODEL}' is not available to this OpenAI project. "
                "Enable Realtime access or set OPENAI_REALTIME_MODEL to an enabled Realtime model."
            )
        elif response.status_code == 429 and error_code in {"insufficient_quota", "credit_balance_exhausted"}:
            detail = "OpenAI Realtime is unavailable because this project has no remaining API credits."
        else:
            detail = f"OpenAI rejected the realtime voice session ({response.status_code})."
        raise HTTPException(status_code=502, detail=detail)
    return PlainTextResponse(response.text, media_type="application/sdp")
