# FAT

FAT is a URS-to-test-case generator for GxP manufacturing equipment. It helps
computerised systems validation engineers turn User Requirement Specification
(URS) statements into executable qualification protocols aligned with GAMP 5
and 21 CFR Part 11.

The generator is designed for supplier and customer qualification activities.
It produces structured JSON that can be reviewed, approved, and executed by a
qualified human; it does not claim that a test has passed.

## What FAT does

Given a list of URS requirements, FAT:

- Preserves each requirement and assigns an ID when one is not supplied.
- Creates one or more test cases when a requirement spans qualification stages.
- Assigns exactly one stage to each case: FAT, SAT, IQ, or OQ.
- Writes objective operator steps, expected results, and appropriate evidence.
- Carries quantitative limits from the requirement into the expected results
  without inventing tolerances or other specifications.
- Flags requirements that are ambiguous, compound, unverifiable, missing a
  limit or condition, or out of scope.
- Adds relevant regulatory references for data integrity controls such as
  audit trails, electronic signatures, access control, and backup/restore.

PQ is outside FAT's scope. Requirements that depend on real product or a
commercial-scale campaign are tagged OQ and include a note explaining the PQ
dependency.

## Qualification stages

| Stage | Use for | Typical location |
| --- | --- | --- |
| FAT | Design, build quality, component count, safety functions, and closed-system integrity verified before shipment | Supplier site |
| SAT | Re-verification after transport and reassembly, site connections, and shipping-related damage | Customer site |
| IQ | Installed configuration, documentation, utilities, labels, materials, and calibration certificates | Customer site |
| OQ | Operation across a range, alarms, interlocks under load, security, audit trails, signatures, and failure modes | Customer site |

## Output contract

FAT returns only a JSON object conforming to the supplied schema. The object
contains a `test_cases` array, with each test case including its requirement,
qualification stage, executable steps, evidence requirements, quality flags,
and regulatory references where applicable.

Each step has one operator action, one objectively verifiable expected result,
and exactly one evidence type. Test cases leave the system in a safe, restored
state and include a record-verification step whenever the requirement concerns
a GxP record.

## Technology stack

- [FastAPI](https://fastapi.tiangolo.com), SQLModel, Pydantic, and PostgreSQL
  for the backend.
- [React](https://react.dev), TypeScript, Vite, Tailwind CSS, and shadcn/ui
  for the frontend.
- Playwright for end-to-end tests and Pytest for backend tests.
- Docker Compose for local services and self-hosted deployment.
- GitHub Actions for continuous integration and deployment.

## Development

Backend instructions: [backend/README.md](./backend/README.md)

Frontend instructions: [frontend/README.md](./frontend/README.md)

General local development: [development.md](./development.md)

Deployment with FastAPI Cloud: [deployment.md](./deployment.md)

Self-hosted deployment with Docker Compose:
[deployment-docker-compose.md](./deployment-docker-compose.md)

## License

FAT is licensed under the terms of the MIT license.
