import uuid
from datetime import UTC, datetime

from pydantic import EmailStr
from sqlalchemy import Column, DateTime, JSON, LargeBinary
from sqlmodel import Field, Relationship, SQLModel


def get_datetime_utc() -> datetime:
    return datetime.now(UTC)


# Shared properties
class UserBase(SQLModel):
    email: EmailStr = Field(unique=True, index=True, max_length=255)
    is_active: bool = True
    is_superuser: bool = False
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on creation
class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserRegister(SQLModel):
    email: EmailStr = Field(max_length=255)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = Field(default=None, max_length=255)


# Properties to receive via API on update, all are optional
class UserUpdate(SQLModel):
    email: EmailStr | None = Field(default=None, max_length=255)
    is_active: bool | None = None
    is_superuser: bool | None = None
    full_name: str | None = Field(default=None, max_length=255)
    password: str | None = Field(default=None, min_length=8, max_length=128)


class UserUpdateMe(SQLModel):
    full_name: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = Field(default=None, max_length=255)


class UpdatePassword(SQLModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# Database model, database table inferred from class name
class User(UserBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    hashed_password: str
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    items: list[Item] = Relationship(back_populates="owner", cascade_delete=True)
    projects: list[Project] = Relationship(back_populates="owner", cascade_delete=True)


# Properties to return via API, id is always required
class UserPublic(UserBase):
    id: uuid.UUID
    created_at: datetime | None = None


class UsersPublic(SQLModel):
    data: list[UserPublic]
    count: int


# Shared properties
class ItemBase(SQLModel):
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Properties to receive on item creation
class ItemCreate(ItemBase):
    pass


# Properties to receive on item update
class ItemUpdate(SQLModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=255)


# Database model, database table inferred from class name
class Item(ItemBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime | None = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),  # type: ignore
    )
    owner_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    owner: User | None = Relationship(back_populates="items")


# Properties to return via API, id is always required
class ItemPublic(ItemBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None


class ItemsPublic(SQLModel):
    data: list[ItemPublic]
    count: int


class ProjectBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


class Project(ProjectBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    owner_id: uuid.UUID = Field(foreign_key="user.id", nullable=False, ondelete="CASCADE", index=True)
    created_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))
    updated_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))
    owner: User | None = Relationship(back_populates="projects")
    documents: list[ProjectDocument] = Relationship(back_populates="project", cascade_delete=True)
    qualification_steps: list[QualificationStep] = Relationship(back_populates="project", cascade_delete=True)
    generation_runs: list[GenerationRun] = Relationship(back_populates="project", cascade_delete=True)


class ProjectPublic(ProjectBase):
    id: uuid.UUID
    owner_id: uuid.UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProjectsPublic(SQLModel):
    data: list[ProjectPublic]
    count: int


class ProjectDocumentCreate(SQLModel):
    document_type: str = Field(min_length=2, max_length=40)


class ProjectDocument(ProjectDocumentCreate, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID = Field(foreign_key="project.id", nullable=False, ondelete="CASCADE", index=True)
    filename: str = Field(max_length=255)
    media_type: str | None = Field(default=None, max_length=255)
    size_bytes: int = Field(ge=0)
    content: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    version: int = Field(default=1, ge=1)
    created_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))
    updated_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))
    project: Project | None = Relationship(back_populates="documents")


class ProjectDocumentPublic(SQLModel):
    id: uuid.UUID
    project_id: uuid.UUID
    document_type: str
    filename: str
    media_type: str | None = None
    size_bytes: int
    version: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DocumentVersion(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    document_id: uuid.UUID = Field(foreign_key="projectdocument.id", nullable=False, ondelete="CASCADE", index=True)
    version: int = Field(ge=1)
    filename: str = Field(max_length=255)
    media_type: str | None = Field(default=None, max_length=255)
    size_bytes: int = Field(ge=0)
    content: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    created_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))
    updated_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))


class DocumentVersionPublic(SQLModel):
    id: uuid.UUID
    document_id: uuid.UUID
    version: int
    filename: str
    media_type: str | None = None
    size_bytes: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class QualificationStepUpdate(SQLModel):
    status: str = Field(min_length=2, max_length=30)


class QualificationStep(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID = Field(foreign_key="project.id", nullable=False, ondelete="CASCADE", index=True)
    stage: str = Field(max_length=10)
    order_index: int = Field(ge=1)
    status: str = Field(default="not_started", max_length=30)
    created_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))
    updated_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))
    project: Project | None = Relationship(back_populates="qualification_steps")
    generation_runs: list[GenerationRun] = Relationship(back_populates="step", cascade_delete=True)
    test_cases: list[GeneratedTestCase] = Relationship(back_populates="step", cascade_delete=True)


class QualificationStepPublic(SQLModel):
    id: uuid.UUID
    project_id: uuid.UUID
    stage: str
    order_index: int
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class GenerationRun(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID = Field(foreign_key="project.id", nullable=False, ondelete="CASCADE", index=True)
    step_id: uuid.UUID = Field(foreign_key="qualificationstep.id", nullable=False, ondelete="CASCADE", index=True)
    status: str = Field(default="completed", max_length=30)
    model: str = Field(max_length=100)
    created_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))
    project: Project | None = Relationship(back_populates="generation_runs")
    step: QualificationStep | None = Relationship(back_populates="generation_runs")


class GenerationRunPublic(SQLModel):
    id: uuid.UUID
    project_id: uuid.UUID
    step_id: uuid.UUID
    status: str
    model: str
    created_at: datetime | None = None


class GeneratedTestCase(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    step_id: uuid.UUID = Field(foreign_key="qualificationstep.id", nullable=False, ondelete="CASCADE", index=True)
    test_case_id: str = Field(max_length=80)
    urs_id: str = Field(max_length=255)
    title: str = Field(max_length=255)
    payload: dict = Field(sa_column=Column(JSON, nullable=False))
    created_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))
    updated_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))
    step: QualificationStep | None = Relationship(back_populates="test_cases")


class GeneratedTestCasePublic(SQLModel):
    id: uuid.UUID
    step_id: uuid.UUID
    test_case_id: str
    urs_id: str
    title: str
    payload: dict
    created_at: datetime | None = None
    updated_at: datetime | None = None


class UrsRequirement(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID = Field(foreign_key="project.id", nullable=False, ondelete="CASCADE", index=True)
    document_id: uuid.UUID | None = Field(default=None, foreign_key="projectdocument.id", ondelete="SET NULL", index=True)
    requirement_id: str = Field(max_length=255)
    requirement_text: str = Field(max_length=10000)
    source_location: str | None = Field(default=None, max_length=255)
    created_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))
    updated_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))


class TestCaseRequirement(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    generated_test_case_id: uuid.UUID = Field(foreign_key="generatedtestcase.id", nullable=False, ondelete="CASCADE", index=True)
    requirement_id: uuid.UUID = Field(foreign_key="ursrequirement.id", nullable=False, ondelete="CASCADE", index=True)
    relationship_type: str = Field(default="tests", max_length=40)
    created_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))
    updated_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))


class TraceabilityCase(SQLModel):
    id: uuid.UUID
    test_case_id: str
    title: str
    stage: str
    step_count: int
    completed_steps: int
    execution_status: str
    review_status: str | None = None


class TraceabilityRequirement(SQLModel):
    id: uuid.UUID
    requirement_id: str
    requirement_text: str
    source_location: str | None = None
    cases: list[TraceabilityCase]


class TestCaseStep(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    generated_test_case_id: uuid.UUID = Field(foreign_key="generatedtestcase.id", nullable=False, ondelete="CASCADE", index=True)
    step_number: int = Field(ge=1)
    action: str = Field(max_length=10000)
    expected_result: str = Field(max_length=10000)
    evidence_required: str = Field(max_length=80)
    status: str = Field(default="not_started", max_length=30)
    observed_result: str | None = Field(default=None, max_length=10000)
    created_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))
    updated_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))


class TestCaseStepUpdate(SQLModel):
    status: str = Field(min_length=2, max_length=30)
    observed_result: str | None = Field(default=None, max_length=10000)


class TestCaseStepPublic(SQLModel):
    id: uuid.UUID
    generated_test_case_id: uuid.UUID
    step_number: int
    action: str
    expected_result: str
    evidence_required: str
    status: str
    observed_result: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TestStepExecution(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    test_case_step_id: uuid.UUID = Field(foreign_key="testcasestep.id", nullable=False, ondelete="CASCADE", index=True)
    executor_id: uuid.UUID = Field(foreign_key="user.id", nullable=False, ondelete="CASCADE", index=True)
    status: str = Field(default="not_started", max_length=30)
    observed_result: str | None = Field(default=None, max_length=10000)
    deviation_reference: str | None = Field(default=None, max_length=255)
    started_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    completed_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    created_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))
    updated_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))


class TestStepExecutionUpdate(SQLModel):
    status: str = Field(min_length=2, max_length=30)
    observed_result: str | None = Field(default=None, max_length=10000)
    deviation_reference: str | None = Field(default=None, max_length=255)


class TestStepExecutionPublic(SQLModel):
    id: uuid.UUID
    test_case_step_id: uuid.UUID
    executor_id: uuid.UUID
    status: str
    observed_result: str | None = None
    deviation_reference: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TestCaseReview(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    generated_test_case_id: uuid.UUID = Field(foreign_key="generatedtestcase.id", nullable=False, ondelete="CASCADE", index=True)
    reviewer_id: uuid.UUID = Field(foreign_key="user.id", nullable=False, ondelete="CASCADE", index=True)
    status: str = Field(default="pending", max_length=30)
    comment: str | None = Field(default=None, max_length=4000)
    created_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))
    updated_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))
    reviewed_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))


class TestCaseReviewUpdate(SQLModel):
    status: str = Field(min_length=2, max_length=30)
    comment: str | None = Field(default=None, max_length=4000)


class TestCaseReviewPublic(SQLModel):
    id: uuid.UUID
    generated_test_case_id: uuid.UUID
    reviewer_id: uuid.UUID
    status: str
    comment: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    reviewed_at: datetime | None = None


class TestExecution(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    generated_test_case_id: uuid.UUID = Field(foreign_key="generatedtestcase.id", nullable=False, ondelete="CASCADE", index=True)
    executor_id: uuid.UUID = Field(foreign_key="user.id", nullable=False, ondelete="CASCADE", index=True)
    status: str = Field(default="not_started", max_length=30)
    observed_result: str | None = Field(default=None, max_length=10000)
    deviation_reference: str | None = Field(default=None, max_length=255)
    executed_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    created_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))
    updated_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))


class TestExecutionUpdate(SQLModel):
    status: str = Field(min_length=2, max_length=30)
    observed_result: str | None = Field(default=None, max_length=10000)
    deviation_reference: str | None = Field(default=None, max_length=255)


class TestExecutionPublic(SQLModel):
    id: uuid.UUID
    generated_test_case_id: uuid.UUID
    executor_id: uuid.UUID
    status: str
    observed_result: str | None = None
    deviation_reference: str | None = None
    executed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TestEvidence(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    execution_id: uuid.UUID | None = Field(default=None, foreign_key="testexecution.id", ondelete="CASCADE", index=True)
    step_execution_id: uuid.UUID | None = Field(default=None, foreign_key="teststepexecution.id", ondelete="CASCADE", index=True)
    evidence_type: str = Field(max_length=50)
    filename: str = Field(max_length=255)
    media_type: str | None = Field(default=None, max_length=255)
    size_bytes: int = Field(ge=0)
    content: bytes = Field(sa_column=Column(LargeBinary, nullable=False))
    created_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))
    updated_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))


class GenerationFeedback(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    project_id: uuid.UUID = Field(foreign_key="project.id", nullable=False, ondelete="CASCADE", index=True)
    author_id: uuid.UUID = Field(foreign_key="user.id", nullable=False, ondelete="CASCADE", index=True)
    step_id: uuid.UUID | None = Field(default=None, foreign_key="qualificationstep.id", ondelete="SET NULL", index=True)
    generation_run_id: uuid.UUID | None = Field(default=None, foreign_key="generationrun.id", ondelete="SET NULL", index=True)
    feedback_type: str = Field(default="general", max_length=40)
    content: str = Field(min_length=1, max_length=10000)
    created_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))
    updated_at: datetime | None = Field(default_factory=get_datetime_utc, sa_type=DateTime(timezone=True))


# Generic message
class Message(SQLModel):
    message: str


# JSON payload containing access token
class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"


# Contents of JWT token
class TokenPayload(SQLModel):
    sub: str | None = None


class NewPassword(SQLModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)
