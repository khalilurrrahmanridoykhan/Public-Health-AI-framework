from pathlib import Path
import json

import pandas as pd
from starlette.testclient import TestClient

from public_health_framework.application import PHFrame
from public_health_framework.config import ProjectConfig
from public_health_framework.importer import import_dataset, load_mapping, save_mapping
from public_health_framework.project import create_project


def test_file_import_supports_json_and_xml(tmp_path: Path):
    root = create_project("Structured Files", tmp_path / "structured-files")
    config = ProjectConfig.load(root / "phframe.yaml")
    record = {
        "case_id": "JSON-1", "disease": "Influenza", "status": "confirmed",
        "report_date": "2026-08-24", "district": "Region 1", "cases": 2,
    }
    json_path = tmp_path / "records.json"
    json_path.write_text(json.dumps([record]), encoding="utf-8")
    assert import_dataset(config, "case_reports", json_path).imported_rows == 1
    xml_path = tmp_path / "records.xml"
    xml_path.write_text("""<records><record><case_id>XML-1</case_id><disease>Influenza</disease><status>suspected</status><report_date>2026-08-24</report_date><district>Region 2</district><cases>3</cases></record></records>""", encoding="utf-8")
    assert import_dataset(config, "case_reports", xml_path).imported_rows == 1
from public_health_framework.storage import Storage


def records() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Case Number": "MAL-100",
                "Disease Name": "Malaria",
                "Classification": "confirmed",
                "Reported": "2026-07-20",
                "Area": "Bandarban",
                "Case Count": 1,
            },
            {
                "Case Number": "MAL-101",
                "Disease Name": "Malaria",
                "Classification": "suspected",
                "Reported": "2026-07-21",
                "Area": "Rangamati",
                "Case Count": 2,
            },
        ]
    )


MAPPING = {
    "Case Number": "case_id",
    "Disease Name": "disease",
    "Classification": "status",
    "Reported": "report_date",
    "Area": "district",
    "Case Count": "cases",
}


def test_atomic_csv_import_and_history(tmp_path: Path):
    root = create_project("Malaria Imports", tmp_path / "project")
    source = tmp_path / "records.csv"
    records().to_csv(source, index=False)
    config = ProjectConfig.load(root / "phframe.yaml")

    result = import_dataset(config, "case_reports", source, MAPPING)
    assert result.status == "completed"
    assert result.imported_rows == 2
    storage = Storage(config)
    assert len(storage.list(config.datasets["case_reports"])) == 2
    assert storage.import_history()[0]["status"] == "completed"

    client = TestClient(PHFrame(config))
    assert client.get("/api/imports").json()["data"][0]["imported_rows"] == 2


def test_invalid_import_writes_no_records(tmp_path: Path):
    root = create_project("Validated Imports", tmp_path / "project")
    source = tmp_path / "invalid.csv"
    invalid = records()
    invalid["Case Count"] = invalid["Case Count"].astype(object)
    invalid.loc[1, "Case Count"] = "not-a-number"
    invalid.to_csv(source, index=False)
    config = ProjectConfig.load(root / "phframe.yaml")

    result = import_dataset(config, "case_reports", source, MAPPING)
    assert result.status == "failed"
    assert result.imported_rows == 0
    assert result.errors[0]["row"] == 3
    assert Storage(config).list(config.datasets["case_reports"]) == []


def test_dry_run_and_reusable_mapping(tmp_path: Path):
    root = create_project("Mapping Test", tmp_path / "project")
    source = tmp_path / "records.xlsx"
    records().to_excel(source, index=False)
    mapping_path = save_mapping(tmp_path / "mapping.yaml", "case_reports", MAPPING)
    dataset, mapping = load_mapping(mapping_path)

    result = import_dataset(ProjectConfig.load(root / "phframe.yaml"), dataset or "", source, mapping, dry_run=True)
    assert result.status == "validated"
    assert result.imported_rows == 0


def test_safe_additive_migration(tmp_path: Path):
    root = create_project("Migration Test", tmp_path / "project")
    config_path = root / "phframe.yaml"
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            "      population:\n        type: integer\n",
            "      population:\n        type: integer\n      investigation_notes:\n        type: string\n",
        ),
        encoding="utf-8",
    )
    config = ProjectConfig.load(config_path)
    storage = Storage(config)
    assert storage.migrate(check_only=True) == ["add field case_reports.investigation_notes"]
    assert storage.migrate() == ["add field case_reports.investigation_notes"]
    assert storage.migrate(check_only=True) == []
