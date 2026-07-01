from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from app.comparison import compare_files
from app.config import settings
from app.export import build_export, build_preview
from app.ingestion import parse_file
from app.review import ReviewDecisionRequest, apply_review_decision, enrich_proposal_for_review

app = FastAPI(title=settings.app_name, version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "mergewise-backend",
        "openai": {
            "configured": settings.has_openai_key,
            "model": settings.openai_model,
        },
    }


@app.post("/ingest")
async def ingest_files(file_a: UploadFile = File(...), file_b: UploadFile = File(...)) -> dict[str, object]:
    parsed_a = parse_file(file_a.filename or "file_a", await file_a.read())
    parsed_b = parse_file(file_b.filename or "file_b", await file_b.read())
    return _ingest_response(parsed_a.to_dict(), parsed_b.to_dict())


@app.post("/compare")
async def compare_uploaded_files(file_a: UploadFile = File(...), file_b: UploadFile = File(...)) -> dict[str, object]:
    parsed_a = parse_file(file_a.filename or "file_a", await file_a.read()).to_dict()
    parsed_b = parse_file(file_b.filename or "file_b", await file_b.read()).to_dict()
    response = _ingest_response(parsed_a, parsed_b)
    if response["status"] == "valid":
        comparison = compare_files(parsed_a, parsed_b)
        comparison["proposals"] = [enrich_proposal_for_review(proposal) for proposal in comparison["proposals"]]
        response["comparison"] = comparison
    else:
        response["comparison"] = None
    return response


@app.post("/review/decision")
def review_decision(payload: ReviewDecisionRequest) -> dict[str, object]:
    return apply_review_decision(payload)


@app.post("/preview")
async def preview_uploaded_files(file_a: UploadFile = File(...), file_b: UploadFile = File(...)) -> dict[str, object]:
    parsed_a, parsed_b, comparison = await _comparison_bundle(file_a, file_b)
    return build_preview(parsed_a, parsed_b, comparison)


@app.post("/export")
async def export_uploaded_files(file_a: UploadFile = File(...), file_b: UploadFile = File(...)) -> dict[str, object]:
    parsed_a, parsed_b, comparison = await _comparison_bundle(file_a, file_b)
    return build_export(parsed_a, parsed_b, comparison)


def _ingest_response(parsed_a: dict[str, object], parsed_b: dict[str, object]) -> dict[str, object]:
    return {
        "status": "valid" if parsed_a["status"] == "valid" and parsed_b["status"] == "valid" else "invalid",
        "files": {
            "file_a": parsed_a,
            "file_b": parsed_b,
        },
    }


async def _comparison_bundle(file_a: UploadFile, file_b: UploadFile) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    parsed_a = parse_file(file_a.filename or "file_a", await file_a.read()).to_dict()
    parsed_b = parse_file(file_b.filename or "file_b", await file_b.read()).to_dict()
    if parsed_a["status"] != "valid" or parsed_b["status"] != "valid":
        return parsed_a, parsed_b, {"overall_trust_score": 0, "proposal_count": 0, "proposals": []}
    comparison = compare_files(parsed_a, parsed_b)
    comparison["proposals"] = [enrich_proposal_for_review(proposal) for proposal in comparison["proposals"]]
    return parsed_a, parsed_b, comparison