# Demo Fixtures

The files in `data/fixtures` are synthetic and safe for local validation. They are intentionally small so smoke checks can prove the Dockerized runtime is working before feature tasks add ingestion, matching, review, preview, and export behavior.

## Files

- `company-a-customers.csv` uses Company A-style customer field names.
- `company-b-customers.csv` uses Company B-style customer field names.

## Smoke Validation Scope

The MW005 runtime smoke path validates only that:

- the backend container starts and returns `GET /health` successfully;
- the frontend container starts and serves the MergeWise AI shell;
- local configuration can use `.env.example` values without real secrets.

Full fixture ingestion and matching are part of later feature tasks.
