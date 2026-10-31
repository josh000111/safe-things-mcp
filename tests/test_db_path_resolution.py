"""Things DB path must be resolved per call, not frozen at import."""
from __future__ import annotations

from pathlib import Path

from safe_things_mcp import config
from safe_things_mcp.services import things_repo


def _make_db(root: Path, suffix: str) -> Path:
    db = root / f"ThingsData-{suffix}" / "Things Database.thingsdatabase" / "main.sqlite"
    db.parent.mkdir(parents=True)
    db.touch()
    return db


def _point_at(monkeypatch, tmp_path: Path) -> Path:
    legacy = tmp_path / "legacy" / "main.sqlite"
    monkeypatch.delenv("THINGS_DB_PATH", raising=False)
    monkeypatch.setattr(config, "THINGS_DB_GLOB", str(tmp_path / "ThingsData-*" / "Things Database.thingsdatabase" / "main.sqlite"))
    monkeypatch.setattr(config, "THINGS_DB_LEGACY_PATH", legacy)
    return legacy


def test_env_var_override_wins(monkeypatch, tmp_path):
    _point_at(monkeypatch, tmp_path)
    _make_db(tmp_path, "AAAAA")
    override = tmp_path / "custom.sqlite"
    monkeypatch.setenv("THINGS_DB_PATH", str(override))
    assert config.resolve_things_db_path() == override


def test_db_created_after_import_is_found_on_next_call(monkeypatch, tmp_path):
    legacy = _point_at(monkeypatch, tmp_path)
    assert config.resolve_things_db_path() == legacy
    db = _make_db(tmp_path, "XXXXX")
    assert config.resolve_things_db_path() == db


def test_falls_back_to_legacy_path_when_nothing_matches(monkeypatch, tmp_path):
    legacy = _point_at(monkeypatch, tmp_path)
    assert config.resolve_things_db_path() == legacy


def test_empty_env_var_is_ignored(monkeypatch, tmp_path):
    _point_at(monkeypatch, tmp_path)
    db = _make_db(tmp_path, "XXXXX")
    monkeypatch.setenv("THINGS_DB_PATH", "")
    assert config.resolve_things_db_path() == db


def test_repo_kw_filepath_tracks_resolution_changes(monkeypatch, tmp_path):
    legacy = _point_at(monkeypatch, tmp_path)
    legacy.parent.mkdir(parents=True)
    legacy.touch()  # _kw() now refuses a nonexistent path (guidance error)
    assert things_repo._kw()["filepath"] == str(legacy)
    legacy.unlink()
    db = _make_db(tmp_path, "XXXXX")
    assert things_repo._kw()["filepath"] == str(db)
