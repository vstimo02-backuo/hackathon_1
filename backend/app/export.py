from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.review import REVIEW_DECISIONS


def build_preview(parsed_a: dict[str, Any], parsed_b: dict[str, Any], comparison: dict[str, Any]) -> dict[str, Any]:
    proposal_states = [_proposal_state(proposal) for proposal in comparison.get("proposals", [])]
    accepted = [state for state in proposal_states if state["decision_state"] in {"accepted", "auto_accepted", "override_accepted"}]
    rejected = [state for state in proposal_states if state["decision_state"] == "rejected"]
    unresolved = [state for state in proposal_states if state["decision_state"] == "unresolved"]
    separated = [state for state in proposal_states if state["decision_state"] == "separated"]

    return {
        "status": "blocked" if unresolved else "ready",
        "files": {
            "file_a": _file_preview(parsed_a),
            "file_b": _file_preview(parsed_b),
        },
        "summary": {
            "accepted_count": len(accepted),
            "rejected_count": len(rejected),
            "separated_count": len(separated),
            "unresolved_count": len(unresolved),
            "overall_trust_score": comparison.get("overall_trust_score", 0),
        },
        "field_preview": proposal_states,
        "entity_preview": _entity_preview(parsed_a, parsed_b, accepted),
        "export_blockers": [state["proposal_id"] for state in unresolved],
    }


def build_export(parsed_a: dict[str, Any], parsed_b: dict[str, Any], comparison: dict[str, Any]) -> dict[str, Any]:
    preview = build_preview(parsed_a, parsed_b, comparison)
    if preview["export_blockers"]:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Export blocked until review-required proposals are resolved.",
                "unresolved_proposals": preview["export_blockers"],
            },
        )

    accepted = [item for item in preview["field_preview"] if item["decision_state"] in {"accepted", "auto_accepted", "override_accepted"}]
    all_proposals = preview["field_preview"]
    return {
        "status": "ready",
        "canonical_mapping": {
            "version": "1.0",
            "fields": [
                {
                    "canonical_field": item["canonical_field"],
                    "trust_score": item["trust_score"],
                    "decision_state": item["decision_state"],
                    "source_fields": item["source_fields"],
                }
                for item in accepted
            ],
        },
        "merged_output": {
            "version": "1.0",
            "records": _merged_records(parsed_a, parsed_b, accepted, all_proposals),
        },
        "preview": preview,
    }


def _proposal_state(proposal: dict[str, Any]) -> dict[str, Any]:
    decision = REVIEW_DECISIONS.get(proposal["proposal_id"])
    decision_state = _decision_state(proposal, decision)
    return {
        "proposal_id": proposal["proposal_id"],
        "canonical_field": proposal["canonical_field"],
        "trust_score": proposal["trust_score"],
        "route": proposal["route"],
        "decision_state": decision_state,
        "review_decision": decision,
        "source_fields": {
            "file_a": proposal["source_field_a"],
            "file_b": proposal["source_field_b"],
        },
    }


def _decision_state(proposal: dict[str, Any], decision: dict[str, Any] | None) -> str:
    if decision and decision["decision"] == "discard":
        return "rejected"
    if decision and decision["decision"] == "keep" and proposal["route"] == "separate":
        return "override_accepted"
    if decision and decision["decision"] == "keep":
        return "accepted"
    if proposal["route"] == "auto_merge":
        return "auto_accepted"
    if proposal["route"] == "review":
        return "unresolved"
    return "separated"


def _file_preview(parsed_file: dict[str, Any]) -> dict[str, Any]:
    return {
        "filename": parsed_file["filename"],
        "format": parsed_file["format"],
        "row_count": parsed_file["row_count"],
        "field_count": len(parsed_file.get("fields", [])),
    }


def _entity_preview(parsed_a: dict[str, Any], parsed_b: dict[str, Any], accepted: list[dict[str, Any]]) -> list[dict[str, Any]]:
    row_count = max(len(parsed_a.get("records", [])), len(parsed_b.get("records", [])))
    return [
        {
            "row_index": index,
            "canonical_fields": [item["canonical_field"] for item in accepted],
        }
        for index in range(row_count)
    ]


def _merged_records(
    parsed_a: dict[str, Any],
    parsed_b: dict[str, Any],
    accepted: list[dict[str, Any]],
    all_proposals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Produce a flat union of all rows from both companies.

    Column resolution order:
    1. Accepted proposals → source fields renamed to their canonical field name.
    2. Non-accepted proposals (separated/rejected) → each source field kept under
       its original name, prefixed with 'a_' / 'b_' only when both sides share
       the same original name.
    3. Fields that appear in the parsed records but were never part of any proposal
       (truly unmatched) → kept under their original name with the same prefix
       conflict-resolution rule.
    """
    # ── Build accepted field maps ─────────────────────────────────────────────
    a_accepted: dict[str, str] = {
        item["source_fields"]["file_a"]["name"]: item["canonical_field"] for item in accepted
    }
    b_accepted: dict[str, str] = {
        item["source_fields"]["file_b"]["name"]: item["canonical_field"] for item in accepted
    }

    # ── Collect ALL source field names that appear in each file's records ─────
    all_a_fields: list[str] = [f["name"] for f in parsed_a.get("fields", [])]
    all_b_fields: list[str] = [f["name"] for f in parsed_b.get("fields", [])]

    # ── Fields not covered by an accepted proposal → "extra" fields ──────────
    extra_a = [name for name in all_a_fields if name not in a_accepted]
    extra_b = [name for name in all_b_fields if name not in b_accepted]

    # If both sides have an extra field with the same original name, prefix them
    # so the two columns remain distinct in the merged output.
    extra_a_conflict = set(extra_a) & set(extra_b)

    def col_a(name: str) -> str:
        return f"a_{name}" if name in extra_a_conflict else name

    def col_b(name: str) -> str:
        return f"b_{name}" if name in extra_a_conflict else name

    # ── Build rows ────────────────────────────────────────────────────────────
    records: list[dict[str, Any]] = []

    for row in parsed_a.get("records", []):
        out: dict[str, Any] = {"_source": "company_a"}
        # Accepted (canonical) fields
        for src, canon in a_accepted.items():
            out[canon] = row.get(src)
        # Extra / unmatched / separated fields – keep original values
        for name in extra_a:
            out[col_a(name)] = row.get(name)
        # Columns that only exist on the B side are absent (will show as missing)
        records.append(out)

    for row in parsed_b.get("records", []):
        out = {"_source": "company_b"}
        for src, canon in b_accepted.items():
            out[canon] = row.get(src)
        for name in extra_b:
            out[col_b(name)] = row.get(name)
        records.append(out)

    return records