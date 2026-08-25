from pathlib import Path
from public_health_framework.config import ProjectConfig
from public_health_framework.jobs import run_due, work
from public_health_framework.project import create_project

def test_worker_with_no_due_connectors(tmp_path: Path):
    root = create_project("Worker", tmp_path / "worker"); config = ProjectConfig.load(root / "phframe.yaml")
    assert run_due(config) == []
    assert work(config, once=True) is None
