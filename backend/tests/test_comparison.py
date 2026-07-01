from fastapi.testclient import TestClient

from app.comparison import compare_fields, route_trust_score
from app.main import app


def test_trust_score_threshold_routing_boundaries() -> None:
    assert route_trust_score(90) == "auto_merge"
    assert route_trust_score(89.99) == "review"
    assert route_trust_score(60) == "review"
    assert route_trust_score(59.99) == "separate"


def test_weighted_scoring_generates_traceable_proposals() -> None:
    proposals = compare_fields(
        [
            {
                "name": "legal_name",
                "inferred_type": "string",
                "non_empty_count": 3,
                "sample_values": ["Global Mining Ltd", "Northstar Retail SRL"],
            }
        ],
        [
            {
                "name": "account_name",
                "inferred_type": "string",
                "non_empty_count": 3,
                "sample_values": ["Global Mining Limited", "North Star Retail"],
            }
        ],
    )

    assert proposals[0]["canonical_field"] == "customer_name"
    assert proposals[0]["trust_score"] >= 60
    assert proposals[0]["source_field_a"]["name"] == "legal_name"
    assert proposals[0]["source_field_b"]["name"] == "account_name"
    assert set(proposals[0]["components"]) == {
        "name_similarity",
        "type_compatibility",
        "sample_similarity",
        "business_token_overlap",
        "completeness_alignment",
    }


def test_compare_endpoint_returns_proposals_for_uploaded_files() -> None:
    client = TestClient(app)

    response = client.post(
        "/compare",
        files={
            "file_a": ("a.csv", b"cust_id,legal_name,country\nA-1,Global Mining Ltd,RO\n", "text/csv"),
            "file_b": ("b.csv", b"client_code,account_name,country\nB-1,Global Mining Limited,RO\n", "text/csv"),
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "valid"
    assert payload["comparison"]["proposal_count"] == 3
    assert payload["comparison"]["overall_trust_score"] > 0
    assert all("route" in proposal for proposal in payload["comparison"]["proposals"])