from pathlib import Path

from starlette.testclient import TestClient

from public_health_framework.application import PHFrame
from public_health_framework.intelligence_repair import apply_repair
from public_health_framework.project import create_project


def test_repair_recipes_are_deterministic_and_non_destructive():
    source = [{"area": " North ", "value": "N/A"}, {"area": " North ", "value": "N/A"}]
    trimmed, summary = apply_repair(source, "trim_whitespace")
    assert trimmed[0]["area"] == "North"
    assert source[0]["area"] == " North "
    assert summary["changed_rows"] == 2
    deduplicated, summary = apply_repair(trimmed, "deduplicate")
    assert len(deduplicated) == 1
    assert summary["safety"] == "review_required"


def test_repair_preview_apply_and_audit_api(tmp_path: Path):
    root = create_project("Repair Review", tmp_path / "repair-review")
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    content = b"case_id,disease,status,report_date,district,cases\nA,Malaria,confirmed,2026-01-01,North,2\nA,Malaria,confirmed,2026-01-01,North,2\n"
    version_id = client.post("/api/browser-import/case_reports/preview?filename=repair.csv", content=content).json()["data"]["version"]["id"]
    proposals = client.get(f"/api/staging/{version_id}/repairs").json()["data"]
    assert any(item["recipe"] == "deduplicate" for item in proposals)
    preview = client.post(f"/api/staging/{version_id}/repairs", json={"recipe": "deduplicate", "preview": True, "actor": "reviewer", "reason": "Exact duplicate"})
    assert preview.json()["data"]["status"] == "previewed"
    applied = client.post(f"/api/staging/{version_id}/repairs", json={"recipe": "deduplicate", "preview": False, "actor": "reviewer", "reason": "Approved exact duplicate removal"})
    assert applied.status_code == 201
    data = applied.json()["data"]
    assert data["summary"]["output_rows"] == 1
    assert data["output_version"]["id"] != version_id
    assert client.get(f"/api/staging/{version_id}/rows").json()["data"][-1]["row_number"] == 2
    assert len(client.get(f"/api/staging/{data['output_version']['id']}/rows").json()["data"]) == 1
    assert len(client.get(f"/api/transformations?version_id={version_id}").json()["data"]) == 2
