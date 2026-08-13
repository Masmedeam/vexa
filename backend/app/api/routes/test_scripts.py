from __future__ import annotations

from io import BytesIO
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.api.deps import CurrentUser
from app.core.config import settings

router = APIRouter(prefix="/test-scripts", tags=["test-scripts"])


class TestStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_number: int = Field(ge=1)
    action: str = Field(min_length=10)
    expected_result: str = Field(min_length=10)
    evidence_required: Literal[
        "None",
        "Screenshot",
        "Photograph",
        "Printout",
        "Data Sheet Attachment",
        "Calibration Certificate",
        "Signed Record",
    ]


class TestCase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_case_id: str = Field(pattern=r"^TC-(FAT|SAT|IQ|OQ)-[0-9]{3}$")
    urs_id: str = Field(min_length=1)
    urs_text: str = Field(min_length=1)
    qualification_stage: Literal["FAT", "SAT", "IQ", "OQ"]
    stage_rationale: str = Field(min_length=20)
    title: str = Field(min_length=5, max_length=120)
    objective: str = Field(min_length=20)
    requirement_type: Literal["Business", "Quality", "Safety", "Regulatory"]
    risk_level: Literal["Low", "Medium", "High"]
    regulatory_reference: str | None
    prerequisites: list[str] = Field(min_length=1)
    test_steps: list[TestStep] = Field(min_length=2, max_length=12)
    acceptance_criteria: str = Field(min_length=20)
    quality_flags: list[
        Literal[
            "ambiguous",
            "compound",
            "unverifiable",
            "missing_limit",
            "missing_condition",
            "out_of_scope",
        ]
    ]
    discrepancy_classification_hint: str | None
    notes: str | None

    @model_validator(mode="after")
    def stage_matches_test_case_id(self) -> "TestCase":
        id_stage = self.test_case_id.split("-")[1]
        if id_stage != self.qualification_stage:
            raise ValueError("test_case_id stage must match qualification_stage")
        return self


class GeneratorOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    test_cases: list[TestCase] = Field(min_length=1)


class TestScriptResponse(BaseModel):
    title: str
    test_cases: list[TestCase]
    source: str
    notes: list[str]


SYSTEM_PROMPT = """You are a computerised systems validation engineer creating draft
qualification protocols for GxP manufacturing equipment and its software.

Use the URS as the source of requirements. Use the supplied functional, hardware, and software
design specifications only to define how a requirement can be tested and which approved design
reference supports it. Preserve every URS requirement ID and provide full traceability. Do not
invent numeric limits, tolerances, part numbers, drawings, SOPs, instruments, or test results.
When a required detail is absent, use <to be defined> or <per approved document> and list the
gap in the requirement-quality notes.

Create one or more test cases for each testable URS requirement. Never merge separate URS
requirements. Split a requirement into more than one test only when it genuinely spans distinct
qualification stages, such as verifying a site utility is installed (IQ) and verifying the
system response to its loss (OQ).

Assign exactly one stage to every test case:
- FAT: supplier-site verification before shipment. Use for as-built configuration, component
  count, closed-system design, and personnel-safety functions.
- SAT: customer-site re-verification after transport or reassembly, especially safety functions
  or connections that shipping could disturb.
- IQ: installed state at the customer site. Use for drawings, labels, certificates, materials,
  calibration, utilities, equipment ratings, and as-built configuration.
- OQ: functional performance across a range, over time, under load, or under fault. Use for
  setpoint control, alarms, interlocks, access control, audit trails, electronic signatures,
  backup/restore, and loss-of-utility response.

Apply this decision order before writing a test:
1. A document, certificate, label, count, rating, or as-built attribute is IQ, unless it must
   be confirmed before shipment, in which case it is FAT.
2. Behaviour over a range, under a fault, or over time is OQ.
3. Personnel safety functions, including E-stops, interlocks, and guarding, are FAT and must
   be repeated as SAT after transport and reassembly.
4. A site-supplied utility is IQ for supply and connection, then OQ for response to its loss.
5. Audit trails, electronic signatures, access control, record retention, and backup/restore
   are OQ and require a relevant Part 11 reference when supported by the design.
Do not classify a supplier-site component count, design-build attribute, closed-system integrity,
or safety function as IQ or OQ merely because it can also be observed during operation.
PQ is outside this draft. If a requirement needs real product or a production campaign, create
the most suitable OQ test and state the PQ dependency in the notes.

For each test case, provide a concise stage rationale, risk level, requirement type,
prerequisites, and an objective acceptance criterion. For Part 11 controls,
include the relevant 21 CFR Part 11 clause when the supplied design information supports it.

Write steps as executable protocol steps. Each step has one operator action and one objectively
verifiable expected result. Keep stated limits and units exactly as written. Avoid vague results
such as "operates correctly". Split a step when either the action or the expected result contains
multiple independently verifiable checks. Include 3 to 8 steps where practical, order them
safely, and end by restoring the system to a safe state. When a GxP record is changed or
created, include a step to verify its audit trail, event log, or batch record.

For every step, specify exactly one evidence type from: None, Screenshot, Photograph, Printout,
Data Sheet Attachment, Calibration Certificate, Signed Record. Use evidence only where a
reviewer needs it to reconstruct the result.

The stage segment in test_case_id must exactly match qualification_stage. For example, an OQ
case must use an ID such as TC-OQ-001, never TC-IQ-001 or TC-FAT-001.

Assess each URS requirement and list applicable quality flags: ambiguous, compound,
unverifiable, missing_limit, missing_condition, out_of_scope. Still create the best possible
draft test for flagged requirements; do not silently resolve the ambiguity.

Return only a JSON object matching the supplied schema. Do not return Markdown, code fences,
or commentary. The object must contain one or more test_cases. This is a draft protocol for
human review and must never state that a test has passed or that a system is compliant."""


def _demo_test_cases() -> list[TestCase]:
    return [
        TestCase(
            test_case_id="TC-OQ-001",
            urs_id="URS-TBD",
            urs_text="The supplied URS requirement must be reviewed before execution.",
            qualification_stage="OQ",
            stage_rationale="The draft demonstrates a system behaviour that requires functional verification.",
            title="Review the primary system requirement",
            objective="Confirm the implemented function can be evaluated against the approved requirement.",
            requirement_type="Business",
            risk_level="Medium",
            prerequisites=["Approved URS and design specification are available."],
            test_steps=[
                TestStep(
                    step_number=1,
                    action="Review the approved URS requirement.",
                    expected_result="The requirement is available for review.",
                    evidence_required="Signed Record",
                ),
                TestStep(
                    step_number=2,
                    action="Record the requirement details for follow-up.",
                    expected_result="The unresolved requirement is recorded for human review.",
                    evidence_required="Signed Record",
                ),
            ],
            acceptance_criteria="The requirement is reviewed and any missing test detail is recorded.",
            quality_flags=["unverifiable", "missing_limit"],
            notes="Demo output only; no document content was analyzed.",
        )
    ]


async def _read_upload(upload: UploadFile) -> tuple[str, bytes]:
    return upload.filename or "unnamed document", await upload.read()


async def generate_cases_from_documents(
    documents: list[tuple[str, bytes, str]], brief: str = "", stage: str | None = None
) -> tuple[list[TestCase], str]:
    if not settings.OPENAI_API_KEY:
        return _demo_test_cases(), "demo"

    from openai import APIStatusError, AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    uploaded_files = []
    for filename, content, document_type in documents:
        uploaded = await client.files.create(file=(filename, BytesIO(content)), purpose="user_data")
        uploaded_files.append((uploaded.id, filename, document_type))
    stage_instruction = (
        f"Generate test cases only for the {stage} qualification stage. Do not create cases for any other stage.\n"
        if stage
        else ""
    )
    input_content = [{"type": "input_file", "file_id": file_id} for file_id, _filename, _document_type in uploaded_files]
    input_content.append({"type": "input_text", "text": f"{stage_instruction}Additional user brief: {brief or 'None'}"})
    try:
        response = await client.responses.create(
            model=settings.OPENAI_MODEL,
            instructions=SYSTEM_PROMPT,
            input=[{"role": "user", "content": input_content}],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "urs_test_cases",
                    "schema": GeneratorOutput.model_json_schema(),
                    "strict": True,
                }
            },
        )
    except APIStatusError as error:
        raise HTTPException(status_code=502, detail="OpenAI could not generate the test cases.") from error
    try:
        generated = GeneratorOutput.model_validate_json(response.output_text)
    except (ValidationError, ValueError) as error:
        raise HTTPException(status_code=502, detail="OpenAI returned test cases that did not match the required schema.") from error
    return generated.test_cases, settings.OPENAI_MODEL


@router.post("/generate", response_model=TestScriptResponse)
async def generate_test_script(
    current_user: CurrentUser,
    urs: UploadFile = File(...),
    design_spec: UploadFile = File(...),
    brief: str = Form(""),
) -> TestScriptResponse:
    urs_name, urs_bytes = await _read_upload(urs)
    design_name, design_bytes = await _read_upload(design_spec)

    test_cases, source = await generate_cases_from_documents(
        [(urs_name, urs_bytes, "URS"), (design_name, design_bytes, "DESIGN_SPEC")], brief
    )
    return TestScriptResponse(
        title="Draft test cases",
        test_cases=test_cases,
        source=source,
        notes=["Review every requirement, limit, and acceptance criterion before approval."],
    )
