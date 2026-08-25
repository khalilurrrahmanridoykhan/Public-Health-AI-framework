import pandas as pd
from public_health_framework.intelligence import profile_frame
from public_health_framework.intelligence_assurance import assess_drift, evaluate_assurance


def version(frame, version_id=1):
    profile = profile_frame(pd.DataFrame(frame))
    return {"id": version_id, "row_count": profile["row_count"], "schema_signature": profile["schema_signature"], "profile": profile}


def test_assurance_allows_stable_refresh_and_blocks_breaking_drift():
    old = version({"district": ["A", "B"], "cases": [1, 2]}, 1)
    stable = version({"district": ["C", "D"], "cases": [3, 4]}, 2)
    report = assess_drift(stable, old, {"score": 95}, {"score": 95})
    assert report["refresh_action"] == "refresh_in_place"
    broken = version({"district": ["C", "D"], "case_label": ["3", "4"]}, 3)
    report = assess_drift(broken, old, {"score": 50}, {"score": 95}, [{"id": 10, "variant": "executive"}])
    assert report["severity"] == "blocking" and not report["publish_allowed"]
    assert report["affected_dashboards"][0]["id"] == 10
    assert evaluate_assurance(report)["passed"]


def test_first_version_is_a_governed_baseline():
    report = assess_drift(version({"cases": [1]}), None)
    assert report["severity"] == "baseline" and report["refresh_action"] == "approval_required"
