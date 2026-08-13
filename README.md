# Vexa

Vexa turns GxP User Requirements Specifications (URS) and design specifications into reviewable, executable qualification workflows.

The app currently supports sequential FAT, SAT, IQ, and OQ work. It creates structured test cases, preserves traceability back to URS requirements, and provides review, execution, evidence, and feedback records. Generated content is always a draft for human review; Vexa never claims that a test has passed or that a system is compliant.

## Workflow

```text
create project
    → upload one or more URS and design documents
    → generate FAT test cases
    → review and execute FAT
    → complete FAT
    → generate SAT
    → continue through IQ and OQ
```

Qualification stages are sequential. Only the active stage can be generated, and the next stage is unlocked after the current stage is completed. A project overview shows stage progress, source documents, test cases, analytics, and a URS-to-test traceability view. Each test case has a dedicated page for review, step execution, evidence, and lifecycle feedback.

## Generation rules

The generation service:

- preserves URS identifiers and assigns deterministic IDs when a source requirement has none;
- creates one or more cases for a requirement only when it genuinely spans qualification stages;
- assigns exactly one stage to each test case: FAT, SAT, IQ, or OQ;
- writes executable steps with one operator action and one objectively verifiable result;
- carries quantitative limits and units from the source documents without inventing values;
- flags ambiguous, compound, unverifiable, incomplete, or out-of-scope requirements;
- specifies evidence only where it helps reconstruct the result;
- includes audit-trail, electronic-signature, access-control, and data-integrity checks when supported by the source material;
- treats PQ as out of scope and records a PQ dependency when an OQ draft depends on production use.

The OpenAI Responses API returns structured JSON. Vexa stores the original payload on the generated test case and also normalizes its contents into database records so individual cases, steps, reviews, executions, evidence, and mappings can be updated independently.

## Data model

```text
Project
├── ProjectDocument
│   └── DocumentVersion
├── QualificationStep
│   └── GenerationRun
├── UrsRequirement
│   └── TestCaseRequirement
│       └── GeneratedTestCase
│           ├── TestCaseStep
│           │   └── TestStepExecution
│           │       └── TestEvidence
│           ├── TestCaseReview
│           └── TestExecution
└── GenerationFeedback
```

All records retain standard identifiers and timestamps. Document versions are immutable snapshots. A generation run records the source documents, stage, model, prompt version, and result. The structured JSON payload is retained for auditability while normalized child tables support CRUD operations and future execution workflows.

## API

The API is protected by JWT authentication except for authentication and health endpoints. The main project routes include:

| Route | Purpose |
| --- | --- |
| `/api/v1/projects` | Create and list projects |
| `/api/v1/projects/{id}/documents` | Upload and list source documents |
| `/api/v1/projects/{id}/generate` | Generate the active qualification stage |
| `/api/v1/projects/{id}/steps` | Read and update qualification-stage status |
| `/api/v1/projects/{id}/test-cases` | List normalized generated cases |
| `/api/v1/projects/{id}/test-cases/{case}/steps` | Read and update protocol steps |
| `/api/v1/projects/{id}/test-cases/{case}/steps/{step}/executions` | Record step execution results |
| `/api/v1/projects/{id}/traceability` | Map URS requirements to generated cases and stages |
| `/api/v1/projects/{id}/feedback` | Store generation and workflow feedback |

Interactive API documentation is available at `http://localhost:8000/docs` when the stack is running.

## Technology

- Backend: FastAPI, SQLModel, Pydantic, PostgreSQL, Alembic
- Frontend: React, TypeScript, Vite, Tailwind CSS, shadcn/ui, TanStack Router
- Generation: OpenAI Responses API with structured output
- Development: Docker Compose with mounted source and hot reload
- Verification: Pytest and Playwright

## Local development

Create or update `.env` with the local database settings and an OpenAI API key. Keep secrets out of source control; the key is used by the backend only.

Start the development stack:

```bash
docker compose up --build
```

Open:

- Vexa: <http://localhost:5173>
- API documentation: <http://localhost:8000/docs>
- Adminer: <http://localhost:8080>
- Mailcatcher: <http://localhost:1080>

Useful checks:

```bash
docker compose ps
curl http://localhost:8000/api/v1/utils/health-check/
curl -I http://localhost:5173/
```

Backend source is mounted with FastAPI reload enabled. Frontend changes use Vite HMR. Rebuild after changing dependencies or Dockerfiles; ordinary Python, TypeScript, and CSS changes only require saving the file.

## Database migrations

Run migrations inside the backend container:

```bash
docker compose exec backend alembic upgrade head
```

Migration history covers project workflows, output lifecycle records, immutable document versions, normalized test-case steps, step executions, and URS-to-test traceability. Do not edit an applied migration; create a new migration for schema changes.

## Verification commands

```bash
npm run build --prefix frontend
python3 -m compileall -q backend/app
docker compose exec backend bash scripts/tests-start.sh
npm run test --prefix frontend
```

When testing generation, use a representative URS and the matching design specification. Check the generated stage, requirement IDs, traceability links, limits, quality flags, evidence types, and normalized database rows—not only the rendered output.

## Project documentation

- [Development guide](development.md)
- [Database and workflow design](design/)
- [URS-to-test reference material](orion01-hackathon-kit/)

The reference material is used for validation rules and examples; the current application architecture and runtime behavior are defined by the backend, frontend, migrations, and this README.
