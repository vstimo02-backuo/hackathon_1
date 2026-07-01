# MergeWise AI Source Code

This repository is the source-code home for the MergeWise AI POC implementation. It now starts with the Dockerized local runtime required by MW005.

## Relationship to Dava.Flow

Planning, discovery, governance, specifications, tasks, and delivery context are managed in the sibling Dava.Flow warehouse:

- `../hackathon-davaflow`

Implementation work should happen in this repository once tasks and technical direction are shaped through Dava.Flow.

## Current Status

- Dockerized local-first runtime scaffolded.
- Backend skeleton: Python/FastAPI with `GET /health`.
- Frontend shell: React/Vite with environment-driven backend URL and peer file upload.
- File ingestion: `CSV`, `XLSX`, and `JSON` parsing with schema metadata extraction.
- Concept comparison: deterministic trust-scored field proposals using the initial weighted model.
- Review flow: explanation fallback/OpenAI path plus keep/discard reviewer decisions.
- Preview/export: JSON preview, canonical mapping export, and merged output export with source traceability.
- Safe synthetic demo fixtures captured in `data/fixtures`.

## Local Configuration

Create a local `.env` from the safe example before running Docker:

```powershell
Copy-Item .env.example .env
```

`OPENAI_API_KEY` may stay empty for health checks and smoke validation. AI-enabled flows added later must read `OPENAI_API_KEY` and `OPENAI_MODEL` from the environment.

## Run With Docker

```powershell
docker compose up --build
```

- Frontend: `http://localhost:5173`
- Backend health: `http://localhost:8000/health`
- Backend ingestion: `POST http://localhost:8000/ingest` with `file_a` and `file_b`
- Backend comparison: `POST http://localhost:8000/compare` with `file_a` and `file_b`
- Backend review decision: `POST http://localhost:8000/review/decision`
- Backend preview: `POST http://localhost:8000/preview` with `file_a` and `file_b`
- Backend export: `POST http://localhost:8000/export` with `file_a` and `file_b`

## Smoke Validation

```powershell
.\scripts\smoke.ps1
```

The smoke script builds the Docker services, checks backend health, checks the frontend shell, and shuts the runtime down unless `-KeepRunning` is provided.

## Backend Tests

```powershell
Set-Location backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
pytest
```
