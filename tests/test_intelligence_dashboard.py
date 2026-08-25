from pathlib import Path
import pandas as pd
from starlette.testclient import TestClient
from public_health_framework.application import PHFrame
from public_health_framework.project import create_project
from public_health_framework.intelligence import profile_frame
from public_health_framework.intelligence_dashboard import generate_dashboard, lint_dashboard
from public_health_framework.intelligence_semantic import compile_semantic_model


def test_generator_creates_explainable_professional_variants():
    profile = profile_frame(pd.DataFrame({"date": ["2026-01-01", "2026-02-01"], "district": ["A", "B"], "cases": [2, 4]}))
    semantic = compile_semantic_model(profile, {"score": 96, "readiness": "ready"}, {"map_ready": True, "filter_fields": ["district"]})
    for variant in ("recommended", "executive", "programme", "data_quality"):
        spec = generate_dashboard(semantic, variant)
        assert spec["lint"]["valid"] and spec["lint"]["score"] >= 80
        assert all(item.get("explanation") for item in spec["widgets"])
    broken = {"widgets": [{"view": "number", "measure": "made_up", "dimension": None}]}
    assert not lint_dashboard(broken, semantic)["valid"]


def test_generated_dashboard_requires_semantic_contract_and_approval(tmp_path: Path):
    root = create_project("Dashboard Review", tmp_path / "dashboard-review")
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))
    content = b"case_id,disease,status,report_date,district,cases\nA,Malaria,confirmed,2026-01-01,A,2\n"
    version_id = client.post("/api/browser-import/case_reports/preview?filename=data.csv", content=content).json()["data"]["version"]["id"]
    assert client.post(f"/api/staging/{version_id}/dashboards", json={}).status_code == 409
    assert client.post(f"/api/staging/{version_id}/semantic", json={}).status_code == 201
    made = client.post(f"/api/staging/{version_id}/dashboards", json={"variant": "recommended"})
    assert made.status_code == 201
    item = made.json()["data"]
    approved = client.patch(f"/api/staging/{version_id}/dashboards/{item['id']}")
    assert approved.json()["data"]["status"] == "approved"
