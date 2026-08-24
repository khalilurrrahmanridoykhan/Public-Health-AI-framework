from pathlib import Path
import sqlite3

from public_health_framework.config import ProjectConfig
from public_health_framework.project import CONFIG_TEMPLATE
from public_health_framework.storage import Storage


def write_config(root: Path, database: str = "sqlite:///data/phframe.db") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / "phframe.yaml"
    path.write_text(CONFIG_TEMPLATE.format(title="Runtime Test").replace(
        "sqlite:///data/phframe.db", database
    ), encoding="utf-8")
    return path


def test_environment_database_override_and_redaction(tmp_path: Path, monkeypatch):
    path = write_config(tmp_path)
    monkeypatch.setenv(
        "PHFRAME_DATABASE_URL", "postgresql+psycopg://health_user:secret@db.internal/phframe"
    )
    monkeypatch.setenv("PHFRAME_ENV", "production")
    monkeypatch.setenv("PHFRAME_HOST", "0.0.0.0")
    monkeypatch.setenv("PHFRAME_PORT", "9000")
    config = ProjectConfig.load(path)
    assert config.environment == "production"
    assert config.host == "0.0.0.0"
    assert config.port == 9000
    assert config.database_display == "postgresql+psycopg://***@db.internal/phframe"
    assert "secret" not in config.database_display


def test_database_url_environment_placeholder(tmp_path: Path, monkeypatch):
    path = write_config(tmp_path, "${DATABASE_URL}")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///alternate.db")
    config = ProjectConfig.load(path)
    assert config.database_path == (tmp_path / "alternate.db").resolve()


def test_legacy_sqlite_schema_remains_compatible(tmp_path: Path):
    config_path = write_config(tmp_path)
    database = tmp_path / "data" / "phframe.db"
    database.parent.mkdir(parents=True)
    connection = sqlite3.connect(database)
    connection.execute(
        """CREATE TABLE case_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id TEXT NOT NULL, disease TEXT NOT NULL, status TEXT NOT NULL,
            onset_date TEXT, report_date TEXT NOT NULL, district TEXT NOT NULL,
            cases INTEGER NOT NULL, population INTEGER,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )"""
    )
    connection.commit()
    connection.close()
    storage = Storage(ProjectConfig.load(config_path))
    assert storage.migrate() == [
        "add field case_reports.country",
        "add field case_reports.patient_age",
        "add field case_reports.epi_week",
        "add field case_reports.reporting_unit",
    ]
