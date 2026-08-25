from io import BytesIO
from pathlib import Path
import json

import pandas as pd
from starlette.testclient import TestClient

from public_health_framework.application import PHFrame
from public_health_framework.project import create_project


MAPPING = {
    "Case Number": "case_id", "Disease": "disease", "Status": "status",
    "Reported": "report_date", "District": "district", "Cases": "cases",
}


def _csv() -> bytes:
    return b"Case Number,Disease,Status,Reported,District,Cases\nM-1,Malaria,confirmed,2026-08-20,Bandarban,2\n"


def test_browser_import_supports_json_xml_and_examples(tmp_path: Path):
    root = create_project("Structured Import", tmp_path / "structured-import")
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    record = {
        "case_id": "GLOBAL-1", "disease": "Influenza", "status": "confirmed",
        "report_date": "2026-08-24", "district": "Northern Region",
        "country": "Exampleland", "cases": 3,
    }
    preview = client.post(
        "/api/browser-import/case_reports/preview?filename=records.json",
        content=json.dumps([record]), headers={"content-type": "application/octet-stream"},
    )
    assert preview.status_code == 200
    assert preview.json()["data"]["sample"][0]["country"] == "Exampleland"
    xml = """<records><record><case_id>GLOBAL-2</case_id><disease>Influenza</disease><status>suspected</status><report_date>2026-08-24</report_date><district>Western Region</district><country>Exampleland</country><cases>2</cases></record></records>"""
    assert client.post(
        "/api/browser-import/case_reports/preview?filename=records.xml",
        content=xml, headers={"content-type": "application/octet-stream"},
    ).status_code == 200
    for file_format, media in [("csv", "text/csv"), ("json", "application/json"), ("xml", "application/xml")]:
        response = client.get(f"/api/import-example/case_reports?format={file_format}")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith(media)


def test_browser_csv_preview_validate_and_import(tmp_path: Path):
    root = create_project("Browser Import", tmp_path / "browser-import")
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    preview = client.post(
        "/api/browser-import/case_reports/preview?filename=cases.csv", content=_csv()
    )
    assert preview.status_code == 200
    assert preview.json()["data"]["columns"][0] == "Case Number"
    assert preview.json()["data"]["total_rows"] == 1
    staged = preview.json()["data"]["version"]
    assert staged["status"] == "staged"
    profile = preview.json()["data"]["profile"]
    assert profile["row_count"] == 1
    assert next(item for item in profile["columns"] if item["name"] == "Cases")["semantic_type"] == "measure"

    detail = client.get(f"/api/staging/{staged['id']}")
    assert detail.status_code == 200
    assert detail.json()["data"]["content_digest"] == staged["content_digest"]
    assert client.get("/api/staging?dataset=case_reports").json()["data"][0]["id"] == staged["id"]
    assert client.get(f"/api/staging/{staged['id']}/rows").json()["data"][0]["data"]["Case Number"] == "M-1"

    query = f"filename=cases.csv&mapping={json.dumps(MAPPING)}&dry_run=true&version_id={staged['id']}"
    validated = client.post(f"/api/browser-import/case_reports?{query}", content=_csv())
    assert validated.status_code == 200
    assert validated.json()["data"]["status"] == "validated"
    imported = client.post(
        f"/api/browser-import/case_reports?filename=cases.csv&mapping={json.dumps(MAPPING)}&version_id={staged['id']}", content=_csv()
    )
    assert imported.status_code == 200
    assert imported.json()["data"]["imported_rows"] == 1
    assert client.get(f"/api/staging/{staged['id']}").json()["data"]["status"] == "approved"


def test_staged_version_can_be_rejected_but_not_reapproved(tmp_path: Path):
    root = create_project("Version Review", tmp_path / "version-review")
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    version_id = client.post("/api/browser-import/case_reports/preview?filename=cases.csv", content=_csv()).json()["data"]["version"]["id"]
    rejected = client.patch(f"/api/staging/{version_id}", json={"status": "rejected"})
    assert rejected.status_code == 200
    assert rejected.json()["data"]["status"] == "rejected"
    assert client.patch(f"/api/staging/{version_id}", json={"status": "approved"}).status_code == 422


def test_browser_excel_preview_and_error_report(tmp_path: Path):
    root = create_project("Excel Browser Import", tmp_path / "excel-import")
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    output = BytesIO()
    pd.DataFrame([{
        "Case Number": "M-2", "Disease": "Malaria", "Status": "confirmed",
        "Reported": "2026-08-21", "District": "Bandarban", "Cases": "invalid",
    }]).to_excel(output, index=False)
    content = output.getvalue()
    assert client.post(
        "/api/browser-import/case_reports/preview?filename=cases.xlsx", content=content
    ).status_code == 200
    response = client.post(
        f"/api/browser-import/case_reports?filename=cases.xlsx&mapping={json.dumps(MAPPING)}", content=content
    )
    assert response.status_code == 422
    data = response.json()["data"]
    assert data["errors"][0]["row"] == 2
    report = client.get(f"/api/imports/{data['run_id']}/errors")
    assert report.status_code == 200
    assert report.json()["data"]["error_rows"] == 1


def test_browser_saved_mapping_api(tmp_path: Path):
    root = create_project("Saved Browser Mapping", tmp_path / "saved-browser-mapping")
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    saved = client.put("/api/import-mappings/monthly_cases", json={
        "dataset": "case_reports", "mapping": MAPPING,
    })
    assert saved.status_code == 200
    listing = client.get("/api/import-mappings?dataset=case_reports").json()["data"]
    assert listing[0]["name"] == "monthly_cases"
    assert listing[0]["mapping"] == MAPPING
    assert client.put("/api/import-mappings/Invalid Name", json={
        "dataset": "case_reports", "mapping": MAPPING,
    }).status_code == 422
