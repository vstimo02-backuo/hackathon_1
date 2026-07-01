from __future__ import annotations

import json
from typing import Any
from urllib import error, request

from app.config import settings

# Canonical concept taxonomy used across the platform
CONCEPT_LABELS = {
    "customer_identifier",
    "customer_name",
    "tax_identifier",
    "country",
    "email",
    "phone",
    "address",
    "postal_code",
    "revenue_category",
    "contract_value",
    "date",
    "status",
    "description",
    "other",
}

_SYSTEM_PROMPT = (
    "You are a data integration specialist helping harmonize schemas from two companies that are merging. "
    "Your task: classify each field into exactly one canonical business concept. "
    "You will receive fields from Company A and Company B with their names, types, and sample values.\n\n"
    "Return a single JSON object mapping every field name (exactly as given) to one of these concept labels:\n\n"
    "customer_identifier — unique ID for a customer/client/account "
    "(e.g. cust_id, client_code, customer_number, account_ref)\n"
    "customer_name — legal or display name of a customer "
    "(e.g. legal_name, account_name, customer_nam, company_title)\n"
    "tax_identifier — tax ID, VAT, fiscal code, EIN, TIN, registration_tax_id\n"
    "country — country, nation, jurisdiction, region code\n"
    "email — email address field\n"
    "phone — phone, mobile, telephone\n"
    "address — physical street address or location\n"
    "postal_code — zip code, postal code, postcode\n"
    "revenue_category — revenue type, revenue source, revenue classification\n"
    "contract_value — contract amount, invoice amount, booked value\n"
    "date — any date or timestamp field\n"
    "status — status, state, active/inactive flag\n"
    "description — notes, description, comments, remarks\n"
    "other — anything that does not clearly fit the above\n\n"
    "Rules:\n"
    "- Return ONLY a valid JSON object — no explanation, no markdown.\n"
    "- Every field name provided must appear as a key in the response.\n"
    "- Use only the concept labels listed above.\n"
    "- When genuinely ambiguous, choose 'other'."
)


def classify_all_fields(
    fields_a: list[dict[str, Any]],
    fields_b: list[dict[str, Any]],
) -> tuple[dict[str, str], dict[str, str]]:
    """Return (concepts_a, concepts_b) each mapping field_name → concept_label.

    Attempts AI classification first; falls back to heuristic rules if unavailable.
    """
    if settings.has_openai_key:
        try:
            return _classify_with_ai(fields_a, fields_b)
        except Exception:
            pass
    return _classify_heuristic(fields_a), _classify_heuristic(fields_b)


# ---------------------------------------------------------------------------
# AI-assisted classification
# ---------------------------------------------------------------------------

def _classify_with_ai(
    fields_a: list[dict[str, Any]],
    fields_b: list[dict[str, Any]],
) -> tuple[dict[str, str], dict[str, str]]:
    user_message = _build_user_message(fields_a, fields_b)

    body = json.dumps({
        "model": settings.openai_model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }).encode("utf-8")

    req = request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Classification HTTP {exc.code}: {detail}") from exc

    choices = payload.get("choices", [])
    if not choices:
        raise RuntimeError("No choices in OpenAI classification response")

    raw = choices[0]["message"]["content"]
    mapping: dict[str, str] = json.loads(raw)

    # Sanitise: replace any unknown label with "other"
    mapping = {k: (v if v in CONCEPT_LABELS else "other") for k, v in mapping.items()}

    concepts_a = {f["name"]: mapping.get(f["name"], "other") for f in fields_a}
    concepts_b = {f["name"]: mapping.get(f["name"], "other") for f in fields_b}
    return concepts_a, concepts_b


def _build_user_message(
    fields_a: list[dict[str, Any]],
    fields_b: list[dict[str, Any]],
) -> str:
    lines = ["Company A fields:"]
    for f in fields_a:
        samples = ", ".join(str(v) for v in f.get("sample_values", [])[:4]) or "none"
        lines.append(f"  - {f['name']} ({f.get('inferred_type', 'unknown')}) | samples: {samples}")

    lines.append("\nCompany B fields:")
    for f in fields_b:
        samples = ", ".join(str(v) for v in f.get("sample_values", [])[:4]) or "none"
        lines.append(f"  - {f['name']} ({f.get('inferred_type', 'unknown')}) | samples: {samples}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Heuristic fallback (no API key required)
# ---------------------------------------------------------------------------

def _classify_heuristic(fields: list[dict[str, Any]]) -> dict[str, str]:
    return {f["name"]: _concept_from_name(f["name"]) for f in fields}


def _concept_from_name(name: str) -> str:
    tokens = [t for t in name.lower().replace("-", "_").split("_") if t]

    # Tax identifiers take highest priority (tax_id should not map to customer_identifier)
    if any(t in {"tax", "vat", "ein", "tin", "fiscal"} for t in tokens):
        return "tax_identifier"
    if "registration" in tokens and any(t in {"tax", "id", "number"} for t in tokens):
        return "tax_identifier"

    # Contact / location
    if any(t in {"email", "mail"} for t in tokens):
        return "email"
    if any(t in {"phone", "mobile", "tel", "telephone"} for t in tokens):
        return "phone"
    if any(t in {"country", "nation", "jurisdiction"} for t in tokens):
        return "country"
    if any(t in {"zip", "postal", "postcode"} for t in tokens):
        return "postal_code"
    if any(t in {"address", "street", "location"} for t in tokens):
        return "address"

    # Revenue / financial
    if any(t in {"revenue", "sales", "turnover", "income"} for t in tokens):
        return "revenue_category"
    if any(t in {"amount", "value", "contract", "invoice", "booked"} for t in tokens):
        return "contract_value"

    # Temporal
    if any(t in {"date", "created", "updated", "timestamp", "modified"} for t in tokens):
        return "date"

    # Lifecycle
    if any(t in {"status", "state", "flag", "active"} for t in tokens):
        return "status"

    # Descriptive
    if any(t in {"desc", "description", "notes", "comment", "remarks"} for t in tokens):
        return "description"

    # Customer identity — name before ID so "legal_name" wins over any id-like token
    if any(t in {"name", "legal", "title"} for t in tokens):
        return "customer_name"
    if any(t in {"id", "uid", "uuid", "key", "code", "number", "num",
                 "cust", "client", "customer", "account", "ref"} for t in tokens):
        return "customer_identifier"

    return "other"
