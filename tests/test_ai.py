from pathlib import Path

from starlette.testclient import TestClient

from public_health_framework.ai import deidentify_records, generate_summary
from public_health_framework.application import PHFrame
from public_health_framework.project import create_project


def _app(tmp_path: Path) -> tuple[Path, TestClient]:
    root = create_project("AI Safety App", tmp_path / "ai-safety-app")
    return root, TestClient(PHFrame.from_file(str(root / "phframe.yaml")))


def test_deidentification_removes_protected_identifiers_and_generalizes(tmp_path: Path):
    root, client = _app(tmp_path)
    app = client.app
    dataset = app.config.datasets["case_reports"]
    result = deidentify_records(dataset, [{"case_id": "person-1", "patient_age": 94, "report_date": "2026-08-24", "country": "Example"}])
    assert result.records == [{"report_date": "2026", "country": "Example", "patient_age": "90+"}]
    assert "case_id" in result.removed_fields
    assert set(result.transformed_fields) >= {"patient_age", "report_date"}


def test_deidentification_preview_explains_transformations(tmp_path: Path):
    root, client = _app(tmp_path)
    client.post("/api/case_reports", json={"case_id": "secret", "disease": "malaria", "status": "confirmed", "report_date": "2026-08-24", "district": "Example", "cases": 2, "patient_age": 35})
    response = client.post("/api/ai/deidentify/case_reports", json={"limit": 10})
    assert response.status_code == 200
    data = response.json()["data"]
    assert "case_id" in data["removed_fields"]
    assert data["records"][0]["report_date"] == "2026"
    assert data["records"][0]["patient_age"] == "30-39"
    assert "legal certification" in data["notice"]


def test_evidence_summary_requires_human_review_and_records_audit(tmp_path: Path):
    root, client = _app(tmp_path)
    client.post("/api/case_reports", json={"case_id": "secret", "disease": "malaria", "status": "confirmed", "report_date": "2026-08-24", "district": "Example", "country": "Example", "cases": 4, "population": 1000})
    generated = client.post("/api/ai/summaries", json={"title": "Weekly briefing", "purpose": "Operations meeting", "author": "Analyst One"})
    assert generated.status_code == 201
    summary = generated.json()["data"]
    assert summary["status"] == "draft"
    assert summary["provider"] == "local"
    assert "requires human review" in summary["content"]
    assert "[1]" in summary["content"]
    assert summary["privacy"]["protected_fields_sent"] == []
    assert summary["privacy"]["row_level_records_sent"] == 0
    assert len(summary["evidence_digest"]) == 64

    missing_note = client.post(f"/api/ai/summaries/{summary['id']}/review", json={"decision": "approved"})
    assert missing_note.status_code == 422
    reviewed = client.post(f"/api/ai/summaries/{summary['id']}/review", json={"decision": "approved", "note": "Checked against the dashboard.", "reviewer": "Reviewer One"})
    assert reviewed.status_code == 200
    assert reviewed.json()["data"]["status"] == "approved"
    assert client.post(f"/api/ai/summaries/{summary['id']}/review", json={"decision": "rejected", "note": "Again"}).status_code == 422
    events = client.get("/api/ai/audit").json()["data"]
    assert [item["event"] for item in events] == ["approved", "generated"]


def test_external_ai_is_opt_in_and_https_only(tmp_path: Path):
    root, client = _app(tmp_path)
    invalid = client.put("/api/settings", json={"ai_provider": "openai_compatible", "allow_external_ai": True, "ai_endpoint": "http://example.org/v1/chat", "ai_api_key_env": "AI_KEY"})
    assert invalid.status_code == 422
    disabled = client.put("/api/settings", json={"ai_provider": "openai_compatible", "allow_external_ai": False, "ai_endpoint": "https://example.org/v1/chat", "ai_api_key_env": "AI_KEY"})
    assert disabled.status_code == 200
    response = client.post("/api/ai/summaries", json={"title": "Draft", "author": "Analyst"})
    assert response.status_code == 422
    assert "disabled" in response.json()["error"]["message"]


def test_local_summary_contains_numbered_evidence_citations():
    evidence = [{"kind": "indicator", "label": "Cases", "value": 3, "endpoint": "/api/indicators/cases"}]
    content, provider, _ = generate_summary("Brief", evidence, "Review", {"ai_provider": "local"})
    assert provider == "local"
    assert "[1]" in content
