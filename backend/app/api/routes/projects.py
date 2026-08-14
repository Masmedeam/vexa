from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from io import BytesIO
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, func, select

from app.api.deps import CurrentUser, SessionDep
from app.api.routes.test_scripts import TestCase, generate_cases_from_documents
from app.core.config import settings
from app.models import (
    DocumentVersion,
    DocumentVersionPublic,
    GeneratedTestCase,
    GeneratedTestCasePublic,
    GenerationFeedback,
    GenerationRun,
    Project,
    ProjectCreate,
    ProjectDocument,
    ProjectDocumentPublic,
    ProjectPublic,
    ProjectsPublic,
    ProjectUpdate,
    QualificationStep,
    QualificationStepPublic,
    QualificationStepUpdate,
    TestCaseRequirement,
    TestCaseReview,
    TestCaseReviewPublic,
    TestCaseReviewUpdate,
    TestCaseStep,
    TestCaseStepPublic,
    TestCaseStepUpdate,
    TestEvidence,
    TestExecution,
    TestExecutionPublic,
    TestExecutionUpdate,
    TestStepExecution,
    TestStepExecutionPublic,
    TestStepExecutionUpdate,
    TraceabilityCase,
    TraceabilityRequirement,
    UrsRequirement,
    VisualReference,
    VisualReferencePublic,
    VisualReferenceUpdate,
)

router = APIRouter(prefix="/projects", tags=["projects"])
STAGES = ("FAT", "SAT", "IQ", "OQ")
STEP_STATUSES = {"not_started", "in_progress", "blocked", "completed"}
DOCUMENT_TYPES = {"URS", "DESIGN_SPEC"}
REVIEW_STATUSES = {"pending", "approved", "rejected", "needs_changes"}
EXECUTION_STATUSES = {"not_started", "in_progress", "passed", "failed", "blocked"}
STEP_STATUSES = {"not_started", "in_progress", "completed", "blocked"}
STEP_EXECUTION_STATUSES = {"not_started", "in_progress", "passed", "failed", "blocked"}


class VisualSearchRequest(BaseModel):
    query: str
    case_id: uuid.UUID | None = None
    step_id: uuid.UUID | None = None


class VisualSearchResponse(BaseModel):
    query: str
    references: list[VisualReferencePublic]


async def _reachable_url(client: httpx.AsyncClient, value: str, image: bool = False) -> bool:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    try:
        response = await client.head(value)
        if response.status_code in {405, 403}:
            response = await client.get(value)
        if not 200 <= response.status_code < 400:
            return False
        return not image or response.headers.get("content-type", "").lower().startswith("image/")
    except httpx.HTTPError:
        return False


class ProjectGenerationResponse(BaseModel):
    step: QualificationStepPublic
    test_cases: list[TestCase]
    source: str
    run_id: uuid.UUID


class TestCaseSummary(BaseModel):
    case_id: uuid.UUID
    review_status: str | None = None
    completed_steps: int
    total_steps: int
    execution_status: str


class ProjectAnalytics(BaseModel):
    project_count: int
    active_stages: int
    completed_stages: int
    test_case_count: int
    reviewed_case_count: int
    passed_step_count: int
    total_step_count: int
    failed_step_count: int
    blocked_case_count: int


def _link_case_requirement(session: SessionDep, case: GeneratedTestCase, project_id: uuid.UUID) -> None:
    requirement_id = str(case.urs_id or case.payload.get("urs_id") or "UNMAPPED")
    requirement_text = str(case.payload.get("urs_text") or "Requirement text not provided in generation output")
    requirement = session.exec(select(UrsRequirement).where(UrsRequirement.project_id == project_id, UrsRequirement.requirement_id == requirement_id)).first()
    if not requirement:
        source = session.exec(select(ProjectDocument).where(ProjectDocument.project_id == project_id, ProjectDocument.document_type == "URS").order_by(col(ProjectDocument.created_at).desc())).first()
        requirement = UrsRequirement(project_id=project_id, document_id=source.id if source else None, requirement_id=requirement_id, requirement_text=requirement_text)
        session.add(requirement); session.flush()
    link = session.exec(select(TestCaseRequirement).where(TestCaseRequirement.generated_test_case_id == case.id, TestCaseRequirement.requirement_id == requirement.id)).first()
    if not link:
        session.add(TestCaseRequirement(generated_test_case_id=case.id, requirement_id=requirement.id))


def _project_or_404(session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID) -> Project:
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.owner_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return project


def _seed_steps(session: SessionDep, project_id: uuid.UUID) -> None:
    for order_index, stage in enumerate(STAGES, start=1):
        session.add(
            QualificationStep(
                project_id=project_id,
                stage=stage,
                order_index=order_index,
                status="in_progress" if order_index == 1 else "not_started",
            )
        )


@router.get("/", response_model=ProjectsPublic)
def read_projects(session: SessionDep, current_user: CurrentUser) -> Any:
    statement = select(Project).where(Project.owner_id == current_user.id).order_by(col(Project.created_at).desc())
    projects = session.exec(statement).all()
    return ProjectsPublic(data=[ProjectPublic.model_validate(item) for item in projects], count=len(projects))


@router.post("/", response_model=ProjectPublic)
def create_project(*, session: SessionDep, current_user: CurrentUser, project_in: ProjectCreate) -> Project:
    project = Project.model_validate(project_in, update={"owner_id": current_user.id})
    session.add(project)
    session.flush()
    _seed_steps(session, project.id)
    session.commit()
    session.refresh(project)
    return project


@router.get("/analytics", response_model=ProjectAnalytics)
def read_project_analytics(session: SessionDep, current_user: CurrentUser) -> ProjectAnalytics:
    projects = session.exec(select(Project).where(Project.owner_id == current_user.id)).all()
    project_ids = [item.id for item in projects]
    steps = session.exec(select(QualificationStep).where(QualificationStep.project_id.in_(project_ids))).all() if project_ids else []
    cases = session.exec(select(GeneratedTestCase).join(QualificationStep).where(QualificationStep.project_id.in_(project_ids))).all() if project_ids else []
    case_ids = [item.id for item in cases]
    protocol_steps = session.exec(select(TestCaseStep).where(TestCaseStep.generated_test_case_id.in_(case_ids))).all() if case_ids else []
    reviewed_case_ids = {item.generated_test_case_id for item in session.exec(select(TestCaseReview).where(TestCaseReview.generated_test_case_id.in_(case_ids))).all()} if case_ids else set()
    return ProjectAnalytics(
        project_count=len(projects), active_stages=sum(item.status == "in_progress" for item in steps), completed_stages=sum(item.status == "completed" for item in steps),
        test_case_count=len(cases), reviewed_case_count=len(reviewed_case_ids), passed_step_count=sum(item.status == "completed" for item in protocol_steps),
        total_step_count=len(protocol_steps), failed_step_count=sum(item.status == "blocked" for item in protocol_steps), blocked_case_count=len({item.generated_test_case_id for item in protocol_steps if item.status == "blocked"}),
    )


@router.get("/{project_id}/traceability", response_model=list[TraceabilityRequirement])
def read_traceability(session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID) -> list[TraceabilityRequirement]:
    _project_or_404(session, current_user, project_id)
    requirements = session.exec(select(UrsRequirement).where(UrsRequirement.project_id == project_id).order_by(UrsRequirement.requirement_id)).all()
    result = []
    for requirement in requirements:
        links = session.exec(select(TestCaseRequirement).where(TestCaseRequirement.requirement_id == requirement.id)).all()
        linked_cases = []
        for link in links:
            case = session.get(GeneratedTestCase, link.generated_test_case_id)
            if not case:
                continue
            stage = session.get(QualificationStep, case.step_id)
            protocol_steps = session.exec(select(TestCaseStep).where(TestCaseStep.generated_test_case_id == case.id)).all()
            reviews = session.exec(select(TestCaseReview).where(TestCaseReview.generated_test_case_id == case.id).order_by(col(TestCaseReview.created_at).desc())).all()
            completed = sum(item.status == "completed" for item in protocol_steps)
            execution_status = "failed" if any(item.status == "blocked" for item in protocol_steps) else "passed" if protocol_steps and completed == len(protocol_steps) else "in_progress" if any(item.status == "in_progress" for item in protocol_steps) else "not_started"
            linked_cases.append(TraceabilityCase(id=case.id, test_case_id=case.test_case_id, title=case.title, stage=stage.stage if stage else "—", step_count=len(protocol_steps), completed_steps=completed, execution_status=execution_status, review_status=reviews[0].status if reviews else None))
        result.append(TraceabilityRequirement(id=requirement.id, requirement_id=requirement.requirement_id, requirement_text=requirement.requirement_text, source_location=requirement.source_location, cases=linked_cases))
    return result


@router.get("/{project_id}/visuals", response_model=list[VisualReferencePublic])
def read_visuals(session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID, case_id: uuid.UUID | None = None, step_id: uuid.UUID | None = None) -> list[VisualReference]:
    _project_or_404(session, current_user, project_id)
    statement = select(VisualReference).where(VisualReference.project_id == project_id).order_by(col(VisualReference.created_at).desc())
    if case_id:
        statement = statement.where(VisualReference.generated_test_case_id == case_id)
    if step_id:
        statement = statement.where(VisualReference.test_case_step_id == step_id)
    return list(session.exec(statement).all())


@router.post("/{project_id}/visuals/search", response_model=VisualSearchResponse)
async def search_visuals(*, session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID, request: VisualSearchRequest) -> VisualSearchResponse:
    _project_or_404(session, current_user, project_id)
    if not settings.OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="Visual search is not configured")
    case = session.get(GeneratedTestCase, request.case_id) if request.case_id else None
    case_step = session.get(QualificationStep, case.step_id) if case else None
    if request.case_id and (not case or not case_step or case_step.project_id != project_id):
        raise HTTPException(status_code=404, detail="Test case not found")
    if request.step_id:
        protocol_step = session.get(TestCaseStep, request.step_id)
        if not protocol_step:
            raise HTTPException(status_code=404, detail="Protocol step not found")
        if case and protocol_step.generated_test_case_id != case.id:
            raise HTTPException(status_code=400, detail="Step does not belong to case")
    prompt = f"""Find up to 3 authoritative, educational visual references or tutorial pages for this GxP qualification test case. Search the web and use only URLs returned by search results. Prefer official manufacturer documentation, standards organizations, universities, or Wikimedia Commons. The result must help an operator understand the equipment, interface, or procedure described below.

Test case: {case.title if case else 'Qualification protocol'}
Protocol context:
{request.query}

Return only JSON with a references array. Each item must contain title, source_url, image_url (null if no directly reachable image exists), snippet, and publisher. Use a tutorial/documentation page as source_url when it is more useful than an image. Never invent or guess URLs. Visuals guide the operator only and are never acceptance evidence."""
    from openai import APIStatusError, AsyncOpenAI
    try:
        response = await AsyncOpenAI(api_key=settings.OPENAI_API_KEY).responses.create(model=settings.OPENAI_MODEL, tools=[{"type": "web_search"}], input=prompt)
        raw = response.output_text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        data = json.loads(raw)
    except (APIStatusError, json.JSONDecodeError, ValueError) as error:
        raise HTTPException(status_code=502, detail="Visual search did not return valid references") from error
    stored: list[VisualReference] = []
    async with httpx.AsyncClient(follow_redirects=True, timeout=5) as client:
        for item in data.get("references", [])[:6]:
            source_url = str(item.get("source_url", ""))
            if not await _reachable_url(client, source_url):
                continue
            image_url = item.get("image_url")
            if image_url and not await _reachable_url(client, str(image_url), image=True):
                image_url = None
            record = VisualReference(project_id=project_id, generated_test_case_id=request.case_id, test_case_step_id=request.step_id, query=request.query, title=str(item.get("title", "Visual reference"))[:500], source_url=source_url, image_url=str(image_url)[:2000] if image_url else None, snippet=str(item.get("snippet", ""))[:4000], publisher=str(item.get("publisher", ""))[:255])
            session.add(record)
            stored.append(record)
    session.commit()
    for item in stored:
        session.refresh(item)
    return VisualSearchResponse(query=request.query, references=[VisualReferencePublic.model_validate(item) for item in stored])


@router.patch("/{project_id}/visuals/{visual_id}", response_model=VisualReferencePublic)
def update_visual(*, session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID, visual_id: uuid.UUID, visual_in: VisualReferenceUpdate) -> VisualReference:
    _project_or_404(session, current_user, project_id)
    visual = session.get(VisualReference, visual_id)
    if not visual or visual.project_id != project_id:
        raise HTTPException(status_code=404, detail="Visual reference not found")
    visual.sqlmodel_update(visual_in.model_dump(exclude_unset=True))
    visual.updated_at = datetime.now(UTC)
    session.add(visual)
    session.commit()
    session.refresh(visual)
    return visual


@router.get("/{project_id}", response_model=ProjectPublic)
def read_project(session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID) -> Project:
    return _project_or_404(session, current_user, project_id)


@router.patch("/{project_id}", response_model=ProjectPublic)
def update_project(*, session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID, project_in: ProjectUpdate) -> Project:
    project = _project_or_404(session, current_user, project_id)
    project.sqlmodel_update(project_in.model_dump(exclude_unset=True))
    project.updated_at = datetime.now(UTC)
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


@router.delete("/{project_id}")
def delete_project(session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID) -> dict[str, str]:
    project = _project_or_404(session, current_user, project_id)
    session.delete(project)
    session.commit()
    return {"message": "Project deleted successfully"}


@router.get("/{project_id}/documents", response_model=list[ProjectDocumentPublic])
def read_documents(session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID) -> list[ProjectDocument]:
    _project_or_404(session, current_user, project_id)
    statement = select(ProjectDocument).where(ProjectDocument.project_id == project_id).order_by(col(ProjectDocument.created_at).desc())
    return list(session.exec(statement).all())


@router.post("/{project_id}/documents", response_model=list[ProjectDocumentPublic])
async def upload_documents(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    project_id: uuid.UUID,
    document_type: str = Form(...),
    files: list[UploadFile] = File(...),
) -> list[ProjectDocument]:
    _project_or_404(session, current_user, project_id)
    normalized_type = document_type.upper()
    if normalized_type not in DOCUMENT_TYPES:
        raise HTTPException(status_code=422, detail="document_type must be URS or DESIGN_SPEC")
    documents = []
    for upload in files:
        content = await upload.read()
        if not content:
            raise HTTPException(status_code=422, detail=f"{upload.filename or 'Document'} is empty")
        document = ProjectDocument(
            project_id=project_id,
            document_type=normalized_type,
            filename=upload.filename or "unnamed document",
            media_type=upload.content_type,
            size_bytes=len(content),
            content=content,
        )
        session.add(document)
        documents.append(document)
    session.commit()
    for document in documents:
        session.refresh(document)
    return documents


@router.put("/{project_id}/documents/{document_id}", response_model=ProjectDocumentPublic)
async def replace_document(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    project_id: uuid.UUID,
    document_id: uuid.UUID,
    file: UploadFile = File(...),
    document_type: str | None = Form(None),
) -> ProjectDocument:
    _project_or_404(session, current_user, project_id)
    document = session.get(ProjectDocument, document_id)
    if not document or document.project_id != project_id:
        raise HTTPException(status_code=404, detail="Document not found")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="Document is empty")
    if document_type and document_type.upper() not in DOCUMENT_TYPES:
        raise HTTPException(status_code=422, detail="document_type must be URS or DESIGN_SPEC")
    session.add(DocumentVersion(document_id=document.id, version=document.version, filename=document.filename, media_type=document.media_type, size_bytes=document.size_bytes, content=document.content))
    document.filename = file.filename or document.filename
    document.media_type = file.content_type
    document.size_bytes = len(content)
    document.content = content
    document.version += 1
    document.updated_at = datetime.now(UTC)
    if document_type:
        document.document_type = document_type.upper()
    session.add(document)
    session.commit()
    session.refresh(document)
    return document


@router.get("/{project_id}/documents/{document_id}/versions", response_model=list[DocumentVersionPublic])
def read_document_versions(session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID, document_id: uuid.UUID) -> list[DocumentVersion]:
    _project_or_404(session, current_user, project_id)
    document = session.get(ProjectDocument, document_id)
    if not document or document.project_id != project_id:
        raise HTTPException(status_code=404, detail="Document not found")
    return list(session.exec(select(DocumentVersion).where(DocumentVersion.document_id == document_id).order_by(col(DocumentVersion.version).desc())).all())


@router.get("/{project_id}/documents/{document_id}/versions/{version}/download")
def download_document_version(session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID, document_id: uuid.UUID, version: int) -> Response:
    _project_or_404(session, current_user, project_id)
    snapshot = session.exec(select(DocumentVersion).where(DocumentVersion.document_id == document_id, DocumentVersion.version == version)).first()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Document version not found")
    return Response(content=snapshot.content, media_type=snapshot.media_type or "application/octet-stream", headers={"Content-Disposition": f'attachment; filename="{snapshot.filename}"'})


@router.post("/{project_id}/executions/{execution_id}/evidence")
async def upload_evidence(*, session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID, execution_id: uuid.UUID, evidence_type: str = Form(...), file: UploadFile = File(...)) -> dict:
    _project_or_404(session, current_user, project_id)
    execution = session.get(TestExecution, execution_id)
    if not execution:
        raise HTTPException(status_code=404, detail="Execution not found")
    case = session.get(GeneratedTestCase, execution.generated_test_case_id)
    step = session.get(QualificationStep, case.step_id) if case else None
    if not case or not step or step.project_id != project_id:
        raise HTTPException(status_code=404, detail="Execution not found")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="Evidence file is empty")
    item = TestEvidence(execution_id=execution_id, evidence_type=evidence_type, filename=file.filename or "evidence", media_type=file.content_type, size_bytes=len(content), content=content)
    session.add(item); session.commit(); session.refresh(item)
    return {"id": str(item.id), "execution_id": str(item.execution_id), "evidence_type": item.evidence_type, "filename": item.filename, "size_bytes": item.size_bytes, "created_at": item.created_at}


@router.get("/{project_id}/documents/{document_id}/download")
def download_document(session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID, document_id: uuid.UUID) -> Response:
    _project_or_404(session, current_user, project_id)
    document = session.get(ProjectDocument, document_id)
    if not document or document.project_id != project_id:
        raise HTTPException(status_code=404, detail="Document not found")
    return Response(content=document.content, media_type=document.media_type or "application/octet-stream", headers={"Content-Disposition": f'attachment; filename="{document.filename}"'})


@router.delete("/{project_id}/documents/{document_id}")
def delete_document(session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID, document_id: uuid.UUID) -> dict[str, str]:
    _project_or_404(session, current_user, project_id)
    document = session.get(ProjectDocument, document_id)
    if not document or document.project_id != project_id:
        raise HTTPException(status_code=404, detail="Document not found")
    session.delete(document)
    session.commit()
    return {"message": "Document deleted successfully"}


@router.get("/{project_id}/steps", response_model=list[QualificationStepPublic])
def read_steps(session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID) -> list[QualificationStep]:
    _project_or_404(session, current_user, project_id)
    statement = select(QualificationStep).where(QualificationStep.project_id == project_id).order_by(QualificationStep.order_index)
    return list(session.exec(statement).all())


@router.patch("/{project_id}/steps/{step_id}", response_model=QualificationStepPublic)
def update_step(
    *, session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID, step_id: uuid.UUID, step_in: QualificationStepUpdate
) -> QualificationStep:
    _project_or_404(session, current_user, project_id)
    if step_in.status not in STEP_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(STEP_STATUSES)}")
    step = session.get(QualificationStep, step_id)
    if not step or step.project_id != project_id:
        raise HTTPException(status_code=404, detail="Qualification step not found")
    previous = session.exec(select(QualificationStep).where(QualificationStep.project_id == project_id, QualificationStep.order_index < step.order_index).order_by(QualificationStep.order_index.desc())).first()
    if previous and previous.status != "completed" and step_in.status in {"in_progress", "completed"}:
        raise HTTPException(status_code=409, detail=f"Complete {previous.stage} before continuing")
    if step_in.status == "completed":
        generated_case = session.exec(select(GeneratedTestCase).where(GeneratedTestCase.step_id == step.id)).first()
        if not generated_case:
            raise HTTPException(status_code=409, detail=f"Generate and review {step.stage} test cases before completing this stage")
    step.status = step_in.status
    step.updated_at = datetime.now(UTC)
    if step_in.status == "completed":
        next_step = session.exec(select(QualificationStep).where(QualificationStep.project_id == project_id, QualificationStep.order_index == step.order_index + 1)).first()
        if next_step and next_step.status == "not_started":
            next_step.status = "in_progress"
            next_step.updated_at = datetime.now(UTC)
            session.add(next_step)
    session.add(step)
    session.commit()
    session.refresh(step)
    return step


@router.get("/{project_id}/test-cases", response_model=list[GeneratedTestCasePublic])
def read_test_cases(session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID) -> list[GeneratedTestCase]:
    _project_or_404(session, current_user, project_id)
    statement = select(GeneratedTestCase).join(QualificationStep).where(QualificationStep.project_id == project_id).order_by(col(GeneratedTestCase.created_at).desc())
    return list(session.exec(statement).all())


@router.get("/{project_id}/test-case-summaries", response_model=list[TestCaseSummary])
def read_test_case_summaries(session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID) -> list[TestCaseSummary]:
    _project_or_404(session, current_user, project_id)
    cases = session.exec(select(GeneratedTestCase).join(QualificationStep).where(QualificationStep.project_id == project_id)).all()
    summaries = []
    for case in cases:
        step_records = session.exec(select(TestCaseStep).where(TestCaseStep.generated_test_case_id == case.id)).all()
        reviews = session.exec(select(TestCaseReview).where(TestCaseReview.generated_test_case_id == case.id).order_by(col(TestCaseReview.created_at).desc())).all()
        if not step_records:
            total_steps = len(case.payload.get("test_steps", []))
            completed_steps = 0
            execution_status = "not_started"
        else:
            total_steps = len(step_records)
            completed_steps = sum(item.status == "completed" for item in step_records)
            execution_status = "failed" if any(item.status == "blocked" for item in step_records) else "passed" if completed_steps == total_steps and total_steps else "in_progress" if any(item.status == "in_progress" for item in step_records) else "not_started"
        summaries.append(TestCaseSummary(case_id=case.id, review_status=reviews[0].status if reviews else None, completed_steps=completed_steps, total_steps=total_steps, execution_status=execution_status))
    return summaries


@router.get("/{project_id}/test-cases/{case_id}", response_model=GeneratedTestCasePublic)
def read_test_case(session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID, case_id: uuid.UUID) -> GeneratedTestCase:
    return _case_or_404(session, current_user, project_id, case_id)


@router.get("/{project_id}/test-cases/{case_id}/steps", response_model=list[TestCaseStepPublic])
def read_case_steps(session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID, case_id: uuid.UUID) -> list[TestCaseStep]:
    case = _case_or_404(session, current_user, project_id, case_id)
    records = list(session.exec(select(TestCaseStep).where(TestCaseStep.generated_test_case_id == case_id).order_by(TestCaseStep.step_number)).all())
    if not records:
        for item in case.payload.get("test_steps", []):
            session.add(TestCaseStep(generated_test_case_id=case_id, step_number=item["step_number"], action=item["action"], expected_result=item["expected_result"], evidence_required=item["evidence_required"]))
        session.commit()
        records = list(session.exec(select(TestCaseStep).where(TestCaseStep.generated_test_case_id == case_id).order_by(TestCaseStep.step_number)).all())
    return records


@router.patch("/{project_id}/test-cases/{case_id}/steps/{step_id}", response_model=TestCaseStepPublic)
def update_case_step(*, session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID, case_id: uuid.UUID, step_id: uuid.UUID, step_in: TestCaseStepUpdate) -> TestCaseStep:
    _case_or_404(session, current_user, project_id, case_id)
    if step_in.status not in STEP_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(STEP_STATUSES)}")
    step = session.get(TestCaseStep, step_id)
    if not step or step.generated_test_case_id != case_id:
        raise HTTPException(status_code=404, detail="Test step not found")
    step.status = step_in.status; step.observed_result = step_in.observed_result; step.updated_at = datetime.now(UTC)
    session.add(step); session.commit(); session.refresh(step)
    return step


def _case_step_or_404(session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID, case_id: uuid.UUID, step_id: uuid.UUID) -> TestCaseStep:
    _case_or_404(session, current_user, project_id, case_id)
    step = session.get(TestCaseStep, step_id)
    if not step or step.generated_test_case_id != case_id:
        raise HTTPException(status_code=404, detail="Test step not found")
    return step


@router.get("/{project_id}/test-cases/{case_id}/steps/{step_id}/executions", response_model=list[TestStepExecutionPublic])
def read_step_executions(session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID, case_id: uuid.UUID, step_id: uuid.UUID) -> list[TestStepExecution]:
    _case_step_or_404(session, current_user, project_id, case_id, step_id)
    return list(session.exec(select(TestStepExecution).where(TestStepExecution.test_case_step_id == step_id).order_by(col(TestStepExecution.created_at).desc())).all())


@router.post("/{project_id}/test-cases/{case_id}/steps/{step_id}/executions", response_model=TestStepExecutionPublic)
def create_step_execution(*, session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID, case_id: uuid.UUID, step_id: uuid.UUID) -> TestStepExecution:
    step = _case_step_or_404(session, current_user, project_id, case_id, step_id)
    existing = session.exec(select(TestStepExecution).where(TestStepExecution.test_case_step_id == step.id, TestStepExecution.status.in_(["not_started", "in_progress"]))).first()
    if existing:
        return existing
    execution = TestStepExecution(test_case_step_id=step.id, executor_id=current_user.id, status="in_progress", started_at=datetime.now(UTC))
    step.status = "in_progress"; step.updated_at = datetime.now(UTC)
    session.add(execution); session.add(step); session.commit(); session.refresh(execution)
    return execution


@router.patch("/{project_id}/test-cases/{case_id}/steps/{step_id}/executions/{execution_id}", response_model=TestStepExecutionPublic)
def update_step_execution(*, session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID, case_id: uuid.UUID, step_id: uuid.UUID, execution_id: uuid.UUID, execution_in: TestStepExecutionUpdate) -> TestStepExecution:
    step = _case_step_or_404(session, current_user, project_id, case_id, step_id)
    if execution_in.status not in STEP_EXECUTION_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(STEP_EXECUTION_STATUSES)}")
    execution = session.get(TestStepExecution, execution_id)
    if not execution or execution.test_case_step_id != step.id:
        raise HTTPException(status_code=404, detail="Step execution not found")
    now = datetime.now(UTC)
    execution.status = execution_in.status; execution.observed_result = execution_in.observed_result; execution.deviation_reference = execution_in.deviation_reference; execution.updated_at = now
    if execution_in.status in {"passed", "failed"}:
        execution.completed_at = now
        step.status = "completed" if execution_in.status == "passed" else "blocked"
    elif execution_in.status == "blocked":
        step.status = "blocked"
    else:
        step.status = "in_progress"
    step.updated_at = now
    session.add(execution); session.add(step); session.commit(); session.refresh(execution)
    return execution


@router.post("/{project_id}/test-cases/{case_id}/steps/{step_id}/executions/{execution_id}/evidence")
async def upload_step_evidence(*, session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID, case_id: uuid.UUID, step_id: uuid.UUID, execution_id: uuid.UUID, evidence_type: str = Form(...), file: UploadFile = File(...)) -> dict:
    _case_step_or_404(session, current_user, project_id, case_id, step_id)
    execution = session.get(TestStepExecution, execution_id)
    if not execution or execution.test_case_step_id != step_id:
        raise HTTPException(status_code=404, detail="Step execution not found")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=422, detail="Evidence file is empty")
    item = TestEvidence(execution_id=None, step_execution_id=execution.id, evidence_type=evidence_type, filename=file.filename or "evidence", media_type=file.content_type, size_bytes=len(content), content=content)
    session.add(item); session.commit(); session.refresh(item)
    return {"id": str(item.id), "step_execution_id": str(item.step_execution_id), "evidence_type": item.evidence_type, "filename": item.filename, "size_bytes": item.size_bytes, "created_at": item.created_at}


def _case_or_404(session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID, case_id: uuid.UUID) -> GeneratedTestCase:
    _project_or_404(session, current_user, project_id)
    case = session.get(GeneratedTestCase, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Test case not found")
    step = session.get(QualificationStep, case.step_id)
    if not step or step.project_id != project_id:
        raise HTTPException(status_code=404, detail="Test case not found")
    return case


@router.get("/{project_id}/test-cases/{case_id}/reviews", response_model=list[TestCaseReviewPublic])
def read_reviews(session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID, case_id: uuid.UUID) -> list[TestCaseReview]:
    _case_or_404(session, current_user, project_id, case_id)
    return list(session.exec(select(TestCaseReview).where(TestCaseReview.generated_test_case_id == case_id).order_by(col(TestCaseReview.created_at).desc())).all())


@router.post("/{project_id}/test-cases/{case_id}/reviews", response_model=TestCaseReviewPublic)
def create_review(*, session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID, case_id: uuid.UUID, review_in: TestCaseReviewUpdate) -> TestCaseReview:
    _case_or_404(session, current_user, project_id, case_id)
    if review_in.status not in REVIEW_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(REVIEW_STATUSES)}")
    review = TestCaseReview.model_validate(review_in, update={"generated_test_case_id": case_id, "reviewer_id": current_user.id, "reviewed_at": datetime.now(UTC) if review_in.status != "pending" else None})
    session.add(review); session.commit(); session.refresh(review)
    return review


@router.patch("/{project_id}/test-cases/{case_id}/reviews/{review_id}", response_model=TestCaseReviewPublic)
def update_review(*, session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID, case_id: uuid.UUID, review_id: uuid.UUID, review_in: TestCaseReviewUpdate) -> TestCaseReview:
    _case_or_404(session, current_user, project_id, case_id)
    if review_in.status not in REVIEW_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(REVIEW_STATUSES)}")
    review = session.get(TestCaseReview, review_id)
    if not review or review.generated_test_case_id != case_id:
        raise HTTPException(status_code=404, detail="Review not found")
    review.status = review_in.status; review.comment = review_in.comment; review.updated_at = datetime.now(UTC)
    review.reviewed_at = datetime.now(UTC) if review.status != "pending" else None
    session.add(review); session.commit(); session.refresh(review)
    return review


@router.get("/{project_id}/test-cases/{case_id}/executions", response_model=list[TestExecutionPublic])
def read_executions(session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID, case_id: uuid.UUID) -> list[TestExecution]:
    _case_or_404(session, current_user, project_id, case_id)
    return list(session.exec(select(TestExecution).where(TestExecution.generated_test_case_id == case_id).order_by(col(TestExecution.created_at).desc())).all())


@router.post("/{project_id}/test-cases/{case_id}/executions", response_model=TestExecutionPublic)
def create_execution(*, session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID, case_id: uuid.UUID) -> TestExecution:
    _case_or_404(session, current_user, project_id, case_id)
    execution = TestExecution(generated_test_case_id=case_id, executor_id=current_user.id)
    session.add(execution); session.commit(); session.refresh(execution)
    return execution


@router.patch("/{project_id}/test-cases/{case_id}/executions/{execution_id}", response_model=TestExecutionPublic)
def update_execution(*, session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID, case_id: uuid.UUID, execution_id: uuid.UUID, execution_in: TestExecutionUpdate) -> TestExecution:
    _case_or_404(session, current_user, project_id, case_id)
    if execution_in.status not in EXECUTION_STATUSES:
        raise HTTPException(status_code=422, detail=f"status must be one of {sorted(EXECUTION_STATUSES)}")
    execution = session.get(TestExecution, execution_id)
    if not execution or execution.generated_test_case_id != case_id:
        raise HTTPException(status_code=404, detail="Execution not found")
    execution.status = execution_in.status; execution.observed_result = execution_in.observed_result; execution.deviation_reference = execution_in.deviation_reference; execution.updated_at = datetime.now(UTC)
    execution.executed_at = datetime.now(UTC) if execution.status in {"passed", "failed"} else execution.executed_at
    session.add(execution); session.commit(); session.refresh(execution)
    return execution


@router.get("/{project_id}/feedback", response_model=list[dict])
def read_feedback(session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID) -> list[dict]:
    _project_or_404(session, current_user, project_id)
    return [item.model_dump() for item in session.exec(select(GenerationFeedback).where(GenerationFeedback.project_id == project_id).order_by(col(GenerationFeedback.created_at).desc())).all()]


@router.post("/{project_id}/feedback", response_model=dict)
def create_feedback(*, session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID, feedback_type: str = Form("general"), content: str = Form(...), step_id: uuid.UUID | None = Form(None), generation_run_id: uuid.UUID | None = Form(None)) -> dict:
    _project_or_404(session, current_user, project_id)
    feedback = GenerationFeedback(project_id=project_id, author_id=current_user.id, feedback_type=feedback_type, content=content, step_id=step_id, generation_run_id=generation_run_id)
    session.add(feedback); session.commit(); session.refresh(feedback)
    return feedback.model_dump()


@router.post("/{project_id}/generate", response_model=ProjectGenerationResponse)
async def generate_project_step(
    *, session: SessionDep, current_user: CurrentUser, project_id: uuid.UUID, brief: str = Form("")
) -> ProjectGenerationResponse:
    project = _project_or_404(session, current_user, project_id)
    # Generation performs a long external request. Lock the project row for the
    # duration so a concurrent delete cannot invalidate the rows we persist after
    # OpenAI returns.
    project = session.exec(select(Project).where(Project.id == project.id).with_for_update()).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    step = session.exec(
        select(QualificationStep)
        .where(QualificationStep.project_id == project.id, QualificationStep.status == "in_progress")
        .order_by(QualificationStep.order_index)
    ).first()
    if not step:
        raise HTTPException(status_code=409, detail="There is no qualification step ready for generation")
    documents = session.exec(select(ProjectDocument).where(ProjectDocument.project_id == project.id)).all()
    urs_documents = [document for document in documents if document.document_type == "URS"]
    design_documents = [document for document in documents if document.document_type == "DESIGN_SPEC"]
    if not urs_documents or not design_documents:
        missing = []
        if not urs_documents:
            missing.append("URS")
        if not design_documents:
            missing.append("design specification")
        raise HTTPException(status_code=409, detail=f"Upload at least one { ' and '.join(missing) } first")
    source_documents = [
        (document.filename, document.content, document.document_type)
        for document in [*urs_documents, *design_documents]
    ]
    test_cases, source = await generate_cases_from_documents(source_documents, brief, step.stage)
    try:
        run = GenerationRun(project_id=project.id, step_id=step.id, status="completed", model=source)
        session.add(run)
        session.flush()
        stored_cases = [
            GeneratedTestCase(
                step_id=step.id,
                test_case_id=test_case.test_case_id,
                urs_id=test_case.urs_id,
                title=test_case.title,
                payload=test_case.model_dump(mode="json"),
            )
            for test_case in test_cases
        ]
        for stored_case in stored_cases:
            session.add(stored_case)
        session.flush()
        for stored_case, test_case in zip(stored_cases, test_cases):
            _link_case_requirement(session, stored_case, project.id)
            for item in test_case.test_steps:
                session.add(TestCaseStep(
                    generated_test_case_id=stored_case.id,
                    step_number=item.step_number,
                    action=item.action,
                    expected_result=item.expected_result,
                    evidence_required=item.evidence_required,
                ))
        session.commit()
    except IntegrityError as error:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="The project changed while test cases were being generated. Refresh the workflow and try again.",
        ) from error
    session.refresh(run)
    return ProjectGenerationResponse(
        step=QualificationStepPublic.model_validate(step),
        test_cases=test_cases,
        source=source,
        run_id=run.id,
    )
