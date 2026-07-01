from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import Workbook

from app.ingestion import parse_file
from app.main import app


def test_parse_csv_extracts_schema_metadata() -> None:
    parsed = parse_file("company-a.csv", b"cust_id,legal_name,revenue\nA-1,Acme,100\nA-2,Bravo,250\n")

    assert parsed.status == "valid"
    assert parsed.row_count == 2
    assert parsed.fields[0]["name"] == "cust_id"
    assert parsed.fields[2]["inferred_type"] == "integer"


def test_parse_json_array_extracts_schema_metadata() -> None:
    parsed = parse_file("company-b.json", b'[{"client_code":"B-1","active":true}]')

    assert parsed.status == "valid"
    assert parsed.row_count == 1
    assert {field["name"] for field in parsed.fields} == {"client_code", "active"}


def test_parse_xlsx_extracts_schema_metadata() -> None:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.append(["supplier_id", "legal_name"])
    worksheet.append(["S-1", "Global Parts Ltd"])
    stream = BytesIO()
    workbook.save(stream)

    parsed = parse_file("suppliers.xlsx", stream.getvalue())

    assert parsed.status == "valid"
    assert parsed.row_count == 1
    assert parsed.fields[0]["name"] == "supplier_id"


def test_unsupported_file_returns_recoverable_error() -> None:
    parsed = parse_file("notes.txt", b"not supported")

    assert parsed.status == "invalid"
    assert parsed.errors == ["Unsupported file format."]


def test_malformed_json_returns_recoverable_error() -> None:
    parsed = parse_file("broken.json", b"{")

    assert parsed.status == "invalid"
    assert parsed.errors[0].startswith("Malformed JSON")


def test_ingest_endpoint_accepts_two_peer_files() -> None:
    client = TestClient(app)

    response = client.post(
        "/ingest",
        files={
            "file_a": ("a.csv", b"cust_id,legal_name\nA-1,Acme\n", "text/csv"),
            "file_b": ("b.json", b'[{"client_code":"B-1","account_name":"Bravo"}]', "application/json"),
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "valid"
    assert payload["files"]["file_a"]["row_count"] == 1
    assert payload["files"]["file_b"]["fields"][0]["name"] == "client_code"