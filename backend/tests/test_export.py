from fastapi.testclient import TestClient

from app.export import build_export, build_preview
from app.review import REVIEW_DECISIONS
from app.main import app


def _parsed_file(filename: str, field_name: str, value: str) -> dict[str, object]:
    return {
        "filename": filename,
        "format": "csv",
        "status": "valid",
        "row_count": 1,
        "fields": [{"name": field_name, "inferred_type": "string", "non_empty_count": 1, "sample_values": [value]}],
        "records": [{field_name: value}],
        "errors": [],
    }


def _comparison(route: str = "review") -> dict[str, object]:
    return {
        "overall_trust_score": 75,
        "proposal_count": 1,
        "proposals": [
            {
                "proposal_id": "legal_name::account_name",
                "canonical_field": "customer_name",
                "trust_score": 75,
                "route": route,
                "source_field_a": {"name": "legal_name", "inferred_type": "string", "non_empty_count": 1, "sample_values": ["Acme"]},
                "source_field_b": {"name": "account_name", "inferred_type": "string", "non_empty_count": 1, "sample_values": ["Acme Ltd"]},
            }
        ],
    }


def test_preview_reflects_unresolved_review_required_proposal() -> None:
    REVIEW_DECISIONS.clear()

    preview = build_preview(_parsed_file("a.csv", "legal_name", "Acme"), _parsed_file("b.csv", "account_name", "Acme Ltd"), _comparison())

    assert preview["status"] == "blocked"
    assert preview["summary"]["unresolved_count"] == 1
    assert preview["export_blockers"] == ["legal_name::account_name"]


def test_export_blocks_when_review_required_proposal_is_unresolved() -> None:
    REVIEW_DECISIONS.clear()
    client = TestClient(app)

    response = client.post(
        "/export",
        files={
            "file_a": ("a.csv", b"legal_name\nAcme\n", "text/csv"),
            "file_b": ("b.csv", b"account_name\nAcme Ltd\n", "text/csv"),
        },
    )

    assert response.status_code == 409
    assert "unresolved_proposals" in response.json()["detail"]


def test_export_preserves_mapping_and_source_traceability_after_keep_decision() -> None:
    REVIEW_DECISIONS.clear()
    REVIEW_DECISIONS["legal_name::account_name"] = {
        "proposal_id": "legal_name::account_name",
        "decision": "keep",
        "review_state": "kept",
        "low_confidence_confirmed": False,
    }

    export = build_export(_parsed_file("a.csv", "legal_name", "Acme"), _parsed_file("b.csv", "account_name", "Acme Ltd"), _comparison())

    assert export["status"] == "ready"
    assert export["canonical_mapping"]["fields"][0]["canonical_field"] == "customer_name"
    assert export["merged_output"]["records"][0]["fields"]["customer_name"]["file_a_value"] == "Acme"
    assert export["merged_output"]["records"][0]["fields"]["customer_name"]["source_traceability"]["file_b"]["name"] == "account_name"


def test_preview_reflects_rejected_auto_merge() -> None:
    REVIEW_DECISIONS.clear()
    REVIEW_DECISIONS["legal_name::account_name"] = {
        "proposal_id": "legal_name::account_name",
        "decision": "discard",
        "review_state": "rejected",
        "low_confidence_confirmed": False,
    }

    preview = build_preview(_parsed_file("a.csv", "legal_name", "Acme"), _parsed_file("b.csv", "account_name", "Acme Ltd"), _comparison("auto_merge"))

    assert preview["summary"]["rejected_count"] == 1
    assert preview["field_preview"][0]["decision_state"] == "rejected"