from __future__ import annotations

from collections import defaultdict
from difflib import SequenceMatcher
from typing import Any

from app.classification import classify_all_fields


WEIGHTS = {
    "name_similarity": 35,
    "type_compatibility": 25,
    "sample_similarity": 20,
    "business_token_overlap": 10,
    "completeness_alignment": 10,
}

TOKEN_ALIASES = {
    # Customer / Account Aliases
    "account": "customer",
    "client": "customer",
    "cust": "customer",
    "customer": "customer",
    "company": "customer",
    "org": "customer",
    "organization": "customer",

    # Naming / Business details
    "legal": "name",
    "name": "name",
    "display": "name",
    "title": "name",
    "alias": "name",

    # Identifiers
    "code": "id",
    "id": "id",
    "number": "id",
    "uid": "id",
    "uuid": "id",
    "key": "id",
    "ref": "id",
    "reference": "id",

    # Tax / Financial Authorities
    "tax": "tax",
    "vat": "tax",
    "ein": "tax",
    "tin": "tax",
    "taxpayer": "tax",
    "fiscal": "tax",
    "abn": "tax",

    # Financial metrics
    "revenue": "revenue",
    "sales": "revenue",
    "turnover": "revenue",
    "income": "revenue",
    "earnings": "revenue",

    # Descriptive details
    "definition": "definition",
    "source": "definition",
    "desc": "definition",
    "description": "definition",
    "details": "definition",

    # Location
    "country": "country",
    "nation": "country",
    "region": "country",
    "state": "country",
    "city": "country",

    # Email / Contacts
    "email": "email",
    "mail": "email",
    "addr": "email",

    # Phones
    "phone": "phone",
    "telephone": "phone",
    "mobile": "phone",
    "cell": "phone",
    "tel": "phone",

    # Addresses
    "address": "address",
    "loc": "address",
    "street": "address",
    "location": "address",
    "site": "address",

    # Postal Codes
    "zip": "zip_code",
    "zipcode": "zip_code",
    "postal": "zip_code",
    "postcode": "zip_code",
    "post_code": "zip_code"
}


def compare_files(parsed_a: dict[str, Any], parsed_b: dict[str, Any]) -> dict[str, Any]:
    fields_a = parsed_a.get("fields", [])
    fields_b = parsed_b.get("fields", [])

    # Phase 1 — AI-assisted concept classification (heuristic fallback when no key)
    concepts_a, concepts_b = classify_all_fields(fields_a, fields_b)

    # Phase 2 — match fields that share the same concept; flag the rest as unmatched
    proposals, unmatched_a, unmatched_b = _match_by_concept(
        fields_a, fields_b, concepts_a, concepts_b
    )
    proposals = sorted(proposals, key=lambda p: p["trust_score"], reverse=True)
    trust_scores = [p["trust_score"] for p in proposals]
    return {
        "overall_trust_score": round(sum(trust_scores) / len(trust_scores), 2) if trust_scores else 0,
        "proposal_count": len(proposals),
        "proposals": proposals,
        "unmatched_fields_a": unmatched_a,
        "unmatched_fields_b": unmatched_b,
    }


def _match_by_concept(
    fields_a: list[dict[str, Any]],
    fields_b: list[dict[str, Any]],
    concepts_a: dict[str, str],
    concepts_b: dict[str, str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    group_a: dict[str, list[dict[str, Any]]] = defaultdict(list)
    group_b: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for field in fields_a:
        group_a[concepts_a.get(field["name"], "other")].append(field)
    for field in fields_b:
        group_b[concepts_b.get(field["name"], "other")].append(field)

    proposals: list[dict[str, Any]] = []
    unmatched_a: list[dict[str, Any]] = []
    unmatched_b: list[dict[str, Any]] = []

    for concept in set(group_a) | set(group_b):
        a_fields = group_a.get(concept, [])
        b_fields = group_b.get(concept, [])

        if a_fields and b_fields:
            # Score every cross-pair and keep the best overall match
            best = max(
                (_score_pair(fa, fb) for fa in a_fields for fb in b_fields),
                key=lambda p: p["trust_score"],
            )
            best["concept"] = concept
            proposals.append(best)

            # Any extras within the same concept group that were not selected → unmatched
            matched_a = best["source_field_a"]["name"]
            matched_b = best["source_field_b"]["name"]
            for fa in a_fields:
                if fa["name"] != matched_a:
                    unmatched_a.append(_unmatched_entry(fa, concept))
            for fb in b_fields:
                if fb["name"] != matched_b:
                    unmatched_b.append(_unmatched_entry(fb, concept))
        elif a_fields:
            unmatched_a.extend(_unmatched_entry(f, concept) for f in a_fields)
        else:
            unmatched_b.extend(_unmatched_entry(f, concept) for f in b_fields)

    return proposals, unmatched_a, unmatched_b


def _unmatched_entry(field: dict[str, Any], concept: str) -> dict[str, Any]:
    return {
        "name": field["name"],
        "inferred_type": field.get("inferred_type", "unknown"),
        "concept": concept,
        "sample_values": field.get("sample_values", [])[:3],
    }


def compare_fields(fields_a: list[dict[str, Any]], fields_b: list[dict[str, Any]]) -> list[dict[str, Any]]:
    proposals: list[dict[str, Any]] = []
    for field_a in fields_a:
        scored_pairs = [_score_pair(field_a, field_b) for field_b in fields_b]
        if scored_pairs:
            proposals.append(max(scored_pairs, key=lambda proposal: proposal["trust_score"]))
    return sorted(proposals, key=lambda proposal: proposal["trust_score"], reverse=True)


def route_trust_score(score: float) -> str:
    if score >= 90:
        return "auto_merge"
    if score >= 60:
        return "review"
    return "separate"


def _score_pair(field_a: dict[str, Any], field_b: dict[str, Any]) -> dict[str, Any]:
    components = {
        "name_similarity": _name_similarity(field_a["name"], field_b["name"]),
        "type_compatibility": _type_compatibility(field_a.get("inferred_type"), field_b.get("inferred_type")),
        "sample_similarity": _sample_similarity(field_a.get("sample_values", []), field_b.get("sample_values", [])),
        "business_token_overlap": _business_token_overlap(field_a["name"], field_b["name"]),
        "completeness_alignment": _completeness_alignment(field_a.get("non_empty_count", 0), field_b.get("non_empty_count", 0)),
    }
    score = round(sum(components[key] * WEIGHTS[key] / 100 for key in WEIGHTS), 2)
    return {
        "proposal_id": f"{field_a['name']}::{field_b['name']}",
        "source_field_a": _source_field(field_a),
        "source_field_b": _source_field(field_b),
        "canonical_field": _canonical_field_name(field_a["name"], field_b["name"]),
        "trust_score": score,
        "route": route_trust_score(score),
        "components": components,
        "rationale": _rationale(field_a, field_b, components),
    }


def _source_field(field: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": field["name"],
        "inferred_type": field.get("inferred_type", "unknown"),
        "non_empty_count": field.get("non_empty_count", 0),
        "sample_values": field.get("sample_values", []),
    }


def _name_similarity(name_a: str, name_b: str) -> float:
    tokens_a = " ".join(_tokens(name_a))
    tokens_b = " ".join(_tokens(name_b))
    return round(SequenceMatcher(None, tokens_a, tokens_b).ratio() * 100, 2)


def _type_compatibility(type_a: str | None, type_b: str | None) -> float:
    if type_a == type_b:
        return 100
    if {type_a, type_b} <= {"integer", "number"}:
        return 80
    if "empty" in {type_a, type_b}:
        return 30
    return 45


def _sample_similarity(values_a: list[str], values_b: list[str]) -> float:
    normalized_a = {_normalize_sample(value) for value in values_a if value}
    normalized_b = {_normalize_sample(value) for value in values_b if value}
    if not normalized_a or not normalized_b:
        return 40
    exact_overlap = len(normalized_a & normalized_b) / max(len(normalized_a | normalized_b), 1)
    closest = max(
        SequenceMatcher(None, value_a, value_b).ratio()
        for value_a in normalized_a
        for value_b in normalized_b
    )
    return round(max(exact_overlap, closest) * 100, 2)


def _business_token_overlap(name_a: str, name_b: str) -> float:
    tokens_a = set(_business_tokens(name_a))
    tokens_b = set(_business_tokens(name_b))
    if not tokens_a or not tokens_b:
        return 30
    return round(len(tokens_a & tokens_b) / len(tokens_a | tokens_b) * 100, 2)


def _completeness_alignment(count_a: int, count_b: int) -> float:
    if count_a == 0 and count_b == 0:
        return 100
    return round(min(count_a, count_b) / max(count_a, count_b, 1) * 100, 2)


def _tokens(value: str) -> list[str]:
    return [token for token in value.lower().replace("-", "_").split("_") if token]


def _business_tokens(value: str) -> list[str]:
    return [TOKEN_ALIASES.get(token, token) for token in _tokens(value)]


def _normalize_sample(value: Any) -> str:
    return str(value).strip().lower().replace("limited", "ltd")


def _canonical_field_name(name_a: str, name_b: str) -> str:
    tokens = _business_tokens(name_a) + _business_tokens(name_b)
    if "name" in tokens:
        return "customer_name" if "customer" in tokens else "name"
    if "tax" in tokens and "id" in tokens:
        return "tax_id"
    if "customer" in tokens and "id" in tokens:
        return "customer_id"
    if "country" in tokens:
        return "country"
    if "revenue" in tokens:
        return "revenue_definition"
    return name_a if len(name_a) <= len(name_b) else name_b


def _rationale(field_a: dict[str, Any], field_b: dict[str, Any], components: dict[str, float]) -> str:
    strongest = max(components, key=components.get)
    return (
        f"Compared {field_a['name']} with {field_b['name']} using field-name, type, sample, "
        f"business-token, and completeness signals. Strongest signal: {strongest.replace('_', ' ')}."
    )