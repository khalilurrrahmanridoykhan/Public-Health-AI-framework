from pathlib import Path
from public_health_framework.cli import main
from public_health_framework.config import ProjectConfig
from public_health_framework.operations import backup, doctor, restore
from public_health_framework.project import create_project
from public_health_framework.storage import Storage

def test_backup_restore_and_doctor(tmp_path: Path):
    root = create_project("Operations", tmp_path / "operations"); config = ProjectConfig.load(root / "phframe.yaml"); storage = Storage(config); storage.initialize()
    saved = backup(config, root / "backups" / "test.db"); assert saved.exists()
    config.database_path.unlink(); restore(config, saved); assert config.database_path.exists()
    assert doctor(config)["status"] == "ok"
    assert main(["doctor", "--config", str(root / "phframe.yaml")]) == 0
