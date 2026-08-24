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


def test_browser_csv_preview_validate_and_import(tmp_path: Path):
    root = create_project("Browser Import", tmp_path / "browser-import")
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    preview = client.post(
        "/api/browser-import/case_reports/preview?filename=cases.csv", content=_csv()
    )
    assert preview.status_code == 200
    assert preview.json()["data"]["columns"][0] == "Case Number"
    assert preview.json()["data"]["total_rows"] == 1

    query = f"filename=cases.csv&mapping={json.dumps(MAPPING)}&dry_run=true"
    validated = client.post(f"/api/browser-import/case_reports?{query}", content=_csv())
    assert validated.status_code == 200
    assert validated.json()["data"]["status"] == "validated"
    imported = client.post(
        f"/api/browser-import/case_reports?filename=cases.csv&mapping={json.dumps(MAPPING)}", content=_csv()
    )
    assert imported.status_code == 200
    assert imported.json()["data"]["imported_rows"] == 1


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
