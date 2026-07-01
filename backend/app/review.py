from __future__ import annotations

import json
from typing import Any, Literal
from urllib import error, request

from fastapi import HTTPException
from pydantic import BaseModel

from app.config import settings


Decision = Literal["keep", "discard"]


class ReviewDecisionRequest(BaseModel):
    proposal_id: str
    route: Literal["auto_merge", "review", "separate"]
    trust_score: float
    decision: Decision
    confirm_low_confidence: bool = False


REVIEW_DECISIONS: dict[str, dict[str, Any]] = {}


def enrich_proposal_for_review(proposal: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(proposal)
    enriched["review_state"] = _initial_review_state(proposal["route"])
    enriched["review_decision"] = REVIEW_DECISIONS.get(proposal["proposal_id"])
    if proposal["trust_score"] < 90:
        enriched["explanation"] = generate_explanation(proposal)
    else:
        enriched["explanation"] = {
            "status": "not_required",
            "text": "Auto-merge proposal. Reviewer may still reject it.",
            "model": None,
        }
    return enriched


def apply_review_decision(payload: ReviewDecisionRequest) -> dict[str, Any]:
    if payload.route == "separate" and payload.decision == "keep" and not payload.confirm_low_confidence:
        raise HTTPException(
            status_code=409,
            detail="Low-confidence override requires explicit confirmation.",
        )

    state = _state_after_decision(payload.route, payload.decision)
    decision = {
        "proposal_id": payload.proposal_id,
        "decision": payload.decision,
        "review_state": state,
        "low_confidence_confirmed": payload.confirm_low_confidence if payload.route == "separate" else False,
    }
    REVIEW_DECISIONS[payload.proposal_id] = decision
    return decision


def generate_explanation(proposal: dict[str, Any]) -> dict[str, Any]:
    if not settings.has_openai_key:
        return _fallback_explanation(proposal, "OpenAI API key is not configured.")

    try:
        return _openai_explanation(proposal)
    except Exception as exc:
        return _fallback_explanation(proposal, f"OpenAI explanation failed: {exc}")


def _initial_review_state(route: str) -> str:
    if route == "auto_merge":
        return "auto_merged"
    if route == "review":
        return "needs_review"
    return "separated_by_default"


def _state_after_decision(route: str, decision: str) -> str:
    if decision == "discard":
        return "rejected"
    if route == "separate":
        return "kept_with_low_confidence_override"
    return "kept"


def _fallback_explanation(proposal: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "status": "fallback",
        "text": (
            f"{proposal['source_field_a']['name']} and {proposal['source_field_b']['name']} were routed to "
            f"{proposal['route']} with {proposal['trust_score']}% trust. {proposal['rationale']}"
        ),
        "model": settings.openai_model,
        "recoverable_error": reason,
    }


_SYSTEM_PROMPT = (
    "You are MergeWise AI, a specialist in post-merger data harmonization and integration readiness. "
    "Your role is to help business reviewers understand whether two fields from two different companies "
    "represent the same underlying business concept and can safely be merged into a single canonical field "
    "in a unified data model.\n\n"
    "Context: Two companies are merging. Each company modeled equivalent business entities differently — "
    "using different field names, naming conventions, abbreviations, and sometimes different business "
    "definitions (e.g. Company A defines revenue as invoiced amount, Company B as booked contract value). "
    "The platform has algorithmically scored how similar each field pair is across five signals: "
    "field-name similarity, data-type compatibility, sample-value overlap, business-token alignment, "
    "and completeness alignment. A trust score drives the merge route: "
    "≥90 = auto-merge, 60–89 = needs human review, <60 = likely separate concepts.\n\n"
    "Your task: Reason as a senior data integration architect. For the proposed field mapping provided, "
    "explain in 2–3 concise sentences: (1) what business concept each field most likely represents in its "
    "company's data model, (2) whether they represent the same concept and why, and (3) any risk, "
    "conflict, or caveat a reviewer should be aware of before approving the merge. "
    "Be specific — reference the field names, sample values, and trust signals. "
    "Do not use vague language. If the merge is risky, say so clearly."
)


def _openai_explanation(proposal: dict[str, Any]) -> dict[str, Any]:
    field_a = proposal["source_field_a"]
    field_b = proposal["source_field_b"]
    components = proposal.get("components", {})

    samples_a = ", ".join(str(v) for v in field_a.get("sample_values", [])[:5]) or "none available"
    samples_b = ", ".join(str(v) for v in field_b.get("sample_values", [])[:5]) or "none available"

    prompt = (
        f"Merger field mapping proposal — please assess whether these two fields represent the same business concept.\n\n"
        f"Company A field: \"{field_a['name']}\"\n"
        f"  Data type: {field_a.get('inferred_type', 'unknown')}\n"
        f"  Sample values: {samples_a}\n"
        f"  Non-empty record count: {field_a.get('non_empty_count', 'unknown')}\n\n"
        f"Company B field: \"{field_b['name']}\"\n"
        f"  Data type: {field_b.get('inferred_type', 'unknown')}\n"
        f"  Sample values: {samples_b}\n"
        f"  Non-empty record count: {field_b.get('non_empty_count', 'unknown')}\n\n"
        f"Proposed canonical (merged) field name: \"{proposal['canonical_field']}\"\n\n"
        f"Similarity signals:\n"
        f"  - Field-name similarity: {components.get('name_similarity', 'n/a')}%\n"
        f"  - Data-type compatibility: {components.get('type_compatibility', 'n/a')}%\n"
        f"  - Sample-value overlap: {components.get('sample_similarity', 'n/a')}%\n"
        f"  - Business-token alignment: {components.get('business_token_overlap', 'n/a')}%\n"
        f"  - Completeness alignment: {components.get('completeness_alignment', 'n/a')}%\n"
        f"  Overall trust score: {proposal['trust_score']}% → route: {proposal['route']}\n\n"
        f"Algorithmic rationale: {proposal['rationale']}\n\n"
        f"Explain what each field represents in its company's data model, whether they describe the same "
        f"business concept, and any risk or conflict the reviewer must consider before approving this merge."
    )

    body_dict = {
        "model": settings.openai_model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3
    }
    body = json.dumps(body_dict).encode("utf-8")
    openai_request = request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(openai_request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc

    text = _extract_response_text(payload)
    return {
        "status": "generated",
        "text": text,
        "model": settings.openai_model,
    }


def _extract_response_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices", [])
    if choices and isinstance(choices, list):
        message = choices[0].get("message", {})
        if message and "content" in message:
            return str(message["content"]).strip()
    raise RuntimeError("OpenAI response did not include explanation text.")