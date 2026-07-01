from fastapi.testclient import TestClient

from app.main import app
from app.review import REVIEW_DECISIONS, apply_review_decision, enrich_proposal_for_review, ReviewDecisionRequest


def _proposal(trust_score: float, route: str = "review") -> dict[str, object]:
    return {
        "proposal_id": "legal_name::account_name",
        "source_field_a": {"name": "legal_name", "inferred_type": "string", "non_empty_count": 3, "sample_values": []},
        "source_field_b": {"name": "account_name", "inferred_type": "string", "non_empty_count": 3, "sample_values": []},
        "canonical_field": "customer_name",
        "trust_score": trust_score,
        "route": route,
        "components": {},
        "rationale": "Fields have similar business meaning.",
    }


def test_proposals_below_90_include_recoverable_explanation_state() -> None:
    enriched = enrich_proposal_for_review(_proposal(75, "review"))

    assert enriched["review_state"] == "needs_review"
    assert enriched["explanation"]["status"] == "fallback"
    assert "recoverable_error" in enriched["explanation"]


def test_auto_merge_can_be_rejected_by_reviewer() -> None:
    REVIEW_DECISIONS.clear()

    decision = apply_review_decision(
        ReviewDecisionRequest(
            proposal_id="country::country",
            route="auto_merge",
            trust_score=100,
            decision="discard",
        )
    )

    assert decision["review_state"] == "rejected"
    assert REVIEW_DECISIONS["country::country"]["decision"] == "discard"


def test_low_confidence_keep_requires_confirmation() -> None:
    client = TestClient(app)

    response = client.post(
        "/review/decision",
        json={
            "proposal_id": "revenue_source::client_code",
            "route": "separate",
            "trust_score": 42,
            "decision": "keep",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Low-confidence override requires explicit confirmation."


def test_low_confidence_keep_with_confirmation_is_recorded() -> None:
    client = TestClient(app)

    response = client.post(
        "/review/decision",
        json={
            "proposal_id": "revenue_source::revenue_definition",
            "route": "separate",
            "trust_score": 55,
            "decision": "keep",
            "confirm_low_confidence": True,
        },
    )

    assert response.status_code == 200
    assert response.json()["review_state"] == "kept_with_low_confidence_override"
    assert response.json()["low_confidence_confirmed"] is True


def test_compare_endpoint_returns_review_states_and_explanations() -> None:
    client = TestClient(app)

    response = client.post(
        "/compare",
        files={
            "file_a": ("a.csv", b"legal_name,revenue_source\nGlobal Mining Ltd,invoiced\n", "text/csv"),
            "file_b": ("b.csv", b"account_name,revenue_definition\nGlobal Mining Limited,booked\n", "text/csv"),
        },
    )

    proposals = response.json()["comparison"]["proposals"]
    assert all("review_state" in proposal for proposal in proposals)
    assert any(proposal["explanation"]["status"] == "fallback" for proposal in proposals if proposal["trust_score"] < 90)