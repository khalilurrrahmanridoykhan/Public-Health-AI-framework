import pandas as pd

from public_health_framework.intelligence import profile_frame


def test_profiler_infers_public_health_roles_and_statistics():
    profile = profile_frame(pd.DataFrame({
        "facility_id": ["A", "B", "B"],
        "report_date": ["2026-01-01", "2026-02-01", None],
        "district": ["North", "South", "South"],
        "cases": [2, 4, 4],
        "latitude": [23.1, 24.2, 24.2],
    }))
    columns = {item["name"]: item for item in profile["columns"]}
    assert columns["facility_id"]["semantic_type"] == "identifier"
    assert columns["report_date"]["semantic_type"] == "date"
    assert columns["district"]["semantic_type"] == "location"
    assert columns["cases"]["semantic_type"] == "measure"
    assert columns["latitude"]["semantic_type"] == "latitude"
    assert columns["report_date"]["missing"] == 1
    assert columns["cases"]["maximum"] == 4
    assert len(profile["content_digest"]) == 64
    assert len(profile["schema_signature"]) == 64


def test_profiler_reports_duplicate_rows():
    profile = profile_frame(pd.DataFrame([{"area": "A", "value": 1}, {"area": "A", "value": 1}]))
    assert profile["duplicate_rows"] == 2
