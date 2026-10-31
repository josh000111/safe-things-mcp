"""Actionable guidance when macOS blocks (or Things lacks) the database."""
from __future__ import annotations

import pytest

from safe_things_mcp import config
from safe_things_mcp.services import things_repo


def _point_at(monkeypatch, tmp_path):
    container = tmp_path / "container"
    monkeypatch.delenv("THINGS_DB_PATH", raising=False)
    monkeypatch.setattr(config, "THINGS_GROUP_CONTAINER", container)
    monkeypatch.setattr(config, "THINGS_DB_GLOB", str(container / "ThingsData-*" / "Things Database.thingsdatabase" / "main.sqlite"))
    monkeypatch.setattr(config, "THINGS_DB_LEGACY_PATH", container / "Things Database.thingsdatabase" / "main.sqlite")
    return container


def _make_db(container):
    db = container / "ThingsData-AAAAA" / "Things Database.thingsdatabase" / "main.sqlite"
    db.parent.mkdir(parents=True)
    db.touch()
    return db


def _deny_listdir(monkeypatch):
    def boom(_path):
        raise PermissionError(1, "Operation not permitted")
    monkeypatch.setattr(config.os, "listdir", boom)


def test_readable_db_has_no_problem_and_require_returns_path(monkeypatch, tmp_path):
    container = _point_at(monkeypatch, tmp_path)
    db = _make_db(container)
    assert config.things_db_access_problem() is None
    assert config.require_things_db_path() == db


def test_missing_container_gives_not_found_guidance(monkeypatch, tmp_path):
    _point_at(monkeypatch, tmp_path)
    assert config.things_db_access_problem() == config.NOT_FOUND_GUIDANCE
    with pytest.raises(config.ThingsDBAccessError) as exc:
        config.require_things_db_path()
    assert str(exc.value) == config.NOT_FOUND_GUIDANCE


def test_container_exists_but_no_db_gives_not_found_guidance(monkeypatch, tmp_path):
    container = _point_at(monkeypatch, tmp_path)
    container.mkdir()
    assert config.things_db_access_problem() == config.NOT_FOUND_GUIDANCE


def test_permission_denied_on_listdir_gives_permission_guidance(monkeypatch, tmp_path):
    _point_at(monkeypatch, tmp_path)
    _deny_listdir(monkeypatch)
    assert config.things_db_access_problem() == config.PERMISSION_GUIDANCE
    with pytest.raises(config.ThingsDBAccessError) as exc:
        config.require_things_db_path()
    assert str(exc.value) == config.PERMISSION_GUIDANCE
    assert "Data shared by Things and affiliated apps" in str(exc.value)


def test_permission_denied_on_open_gives_permission_guidance(monkeypatch, tmp_path):
    container = _point_at(monkeypatch, tmp_path)
    _make_db(container)
    real_open = open

    def deny_open(path, *a, **kw):
        if str(path).endswith("main.sqlite"):
            raise PermissionError(1, "Operation not permitted")
        return real_open(path, *a, **kw)

    monkeypatch.setattr("builtins.open", deny_open)
    assert config.things_db_access_problem() == config.PERMISSION_GUIDANCE


def test_env_override_to_missing_file_mentions_it(monkeypatch, tmp_path):
    _point_at(monkeypatch, tmp_path)
    missing = tmp_path / "nope.sqlite"
    monkeypatch.setenv("THINGS_DB_PATH", str(missing))
    problem = config.things_db_access_problem()
    assert str(missing) in problem
    with pytest.raises(config.ThingsDBAccessError, match="nope.sqlite"):
        config.require_things_db_path()


def test_env_override_to_readable_file_is_ok(monkeypatch, tmp_path):
    _point_at(monkeypatch, tmp_path)
    f = tmp_path / "custom.sqlite"
    f.touch()
    monkeypatch.setenv("THINGS_DB_PATH", str(f))
    assert config.things_db_access_problem() is None
    assert config.require_things_db_path() == f


def test_repo_reads_raise_guidance_when_blocked(monkeypatch, tmp_path):
    _point_at(monkeypatch, tmp_path)
    _deny_listdir(monkeypatch)
    with pytest.raises(config.ThingsDBAccessError, match="System Settings"):
        things_repo.inbox()


def _call_health():
    import asyncio
    import json

    from mcp.server.fastmcp import FastMCP

    from safe_things_mcp.tools import meta

    mcp = FastMCP("t")
    meta.register(mcp)
    res = asyncio.run(mcp.call_tool("health", {}))
    if isinstance(res, tuple):
        return res[1]
    return json.loads(res[0].text)


def test_health_reports_permission_problem(monkeypatch, tmp_path):
    _point_at(monkeypatch, tmp_path)
    _deny_listdir(monkeypatch)
    out = _call_health()
    assert out["things_db_access"] == config.PERMISSION_GUIDANCE
    assert out["things_db_exists"] is False


def test_health_reports_ok_when_readable(monkeypatch, tmp_path):
    container = _point_at(monkeypatch, tmp_path)
    _make_db(container)
    out = _call_health()
    assert out["things_db_access"] == "ok"
    assert out["things_db_exists"] is True
