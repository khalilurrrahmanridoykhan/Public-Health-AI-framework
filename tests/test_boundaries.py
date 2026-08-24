from pathlib import Path

from starlette.testclient import TestClient

from public_health_framework.application import PHFrame
from public_health_framework.project import create_project
from public_health_framework.settings import SiteSettings


def test_boundary_download_and_api(monkeypatch, tmp_path: Path):
    root = create_project("Boundary Test", tmp_path / "boundary-test")
    metadata = {"boundaryName": "Bangladesh", "boundaryYearRepresented": "2024", "simplifiedGeometryGeoJSON": "https://example.test/bgd.json"}
    geojson = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {"shapeName": "Bandarban"}, "geometry": {"type": "Polygon", "coordinates": [[[92, 21], [93, 21], [93, 22], [92, 21]]]}}]}
    monkeypatch.setattr(SiteSettings, "_download_json", staticmethod(lambda url, maximum: metadata if "api/current" in url else geojson))
    client = TestClient(PHFrame.from_file(str(root / "phframe.yaml")))

    created = client.post("/api/boundaries", json={"iso3": "BGD", "level": "ADM2"})
    assert created.status_code == 201
    assert created.json()["data"]["feature_count"] == 1
    assert client.get("/api/boundaries").json()["data"][0]["id"] == "BGD-ADM2"
    detail = client.get("/api/boundaries/BGD-ADM2")
    assert detail.status_code == 200
    assert detail.json()["data"]["geojson"]["features"][0]["properties"]["shapeName"] == "Bandarban"


def test_boundary_download_validates_country_and_level(tmp_path: Path):
    settings = SiteSettings(tmp_path, "Test")
    try:
        settings.download_boundary("Bangladesh", "district")
    except ValueError as error:
        assert "three-letter ISO" in str(error)
    else:
        raise AssertionError("Invalid boundary request accepted")


def test_searchable_country_catalog_is_sorted_and_cached(monkeypatch, tmp_path: Path):
    records = [{"boundaryName": "Zimbabwe", "boundaryISO": "ZWE"}, {"boundaryName": "Bangladesh", "boundaryISO": "BGD"}]
    monkeypatch.setattr(SiteSettings, "_download_json", staticmethod(lambda url, maximum: records))
    settings = SiteSettings(tmp_path, "Test")
    assert settings.boundary_countries() == [{"name": "Bangladesh", "iso3": "BGD"}, {"name": "Zimbabwe", "iso3": "ZWE"}]
    monkeypatch.setattr(SiteSettings, "_download_json", staticmethod(lambda url, maximum: (_ for _ in ()).throw(AssertionError("cache not used"))))
    assert settings.boundary_countries()[0]["iso3"] == "BGD"
    assert settings.boundaries() == []


def test_boundary_index_ignores_non_boundary_json(tmp_path: Path):
    settings = SiteSettings(tmp_path, "Test")
    settings.boundary_dir.mkdir(parents=True)
    (settings.boundary_dir / "countries.json").write_text('[{"name":"Bangladesh","iso3":"BGD"}]', encoding="utf-8")
    (settings.boundary_dir / "unrelated.json").write_text('[1, 2, 3]', encoding="utf-8")
    (settings.boundary_dir / "broken.json").write_text('{', encoding="utf-8")
    assert settings.boundaries() == []
