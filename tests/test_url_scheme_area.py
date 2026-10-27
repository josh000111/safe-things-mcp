"""Tests for area-by-NAME support in project URL-scheme builders.

Covers:
* ``build_add_project_url`` with ``area`` (name) — plain path.
* ``build_add_project_url`` with ``area_id`` — unchanged behaviour.
* ``_build_add_project_json_url`` (via headings) with ``area`` (name).
* ``ProposeAddProjectInput`` mutual-exclusion validator.
* ``add_project`` handler threads ``area`` through to the URL builder.
"""
from __future__ import annotations

import json
from urllib.parse import parse_qs, unquote, urlparse

import pytest

from safe_things_mcp.models import ProposeAddProjectInput
from safe_things_mcp.services import url_scheme
from safe_things_mcp.services import things_repo
from safe_things_mcp.services.handlers import add_project


# ---------- build_add_project_url — plain path (no headings) ----------


def test_add_project_area_name_plain_path():
    """area='Work' produces area=Work in the query params (no auth token)."""
    url = url_scheme.build_add_project_url(title="My Project", area="Work")
    assert url.startswith("things:///add-project?")
    params = parse_qs(urlparse(url).query)
    assert params["area"] == ["Work"]
    assert params["title"] == ["My Project"]
    assert "auth-token" not in params


def test_add_project_area_name_encoded():
    """Spaces and special chars in area name are percent-encoded."""
    url = url_scheme.build_add_project_url(title="T", area="Home & Garden")
    assert "area=" in url
    # The value should be URL-encoded; parse_qs decodes it back for us.
    params = parse_qs(urlparse(url).query)
    assert params["area"] == ["Home & Garden"]


def test_add_project_area_id_still_works():
    """Existing area_id kwarg is unchanged."""
    url = url_scheme.build_add_project_url(title="T", area_id="uuid-123")
    assert url.startswith("things:///add-project?")
    params = parse_qs(urlparse(url).query)
    assert params["area-id"] == ["uuid-123"]
    assert "area" not in params


def test_add_project_area_absent_by_default():
    """Neither area nor area-id appears when neither is passed."""
    url = url_scheme.build_add_project_url(title="T")
    params = parse_qs(urlparse(url).query)
    assert "area" not in params
    assert "area-id" not in params


# ---------- build_add_project_url — JSON path (with headings) ----------


def _parse_json_data(url: str) -> list:
    assert url.startswith("things:///json?data=")
    payload = url.removeprefix("things:///json?data=")
    return json.loads(unquote(payload))


def test_add_project_json_with_area_name():
    """``area`` (name) is included in JSON attributes when headings present."""
    url = url_scheme.build_add_project_url(
        title="Q4 Launch",
        area="Engineering",
        headings=["Planning", "Execution"],
    )
    assert url.startswith("things:///json?")
    data = _parse_json_data(url)
    attrs = data[0]["attributes"]
    assert attrs["area"] == "Engineering"
    assert "area-id" not in attrs


def test_add_project_json_with_area_id():
    """``area_id`` (UUID) still works on the JSON path."""
    url = url_scheme.build_add_project_url(
        title="Proj",
        area_id="uuid-abc",
        headings=["H1"],
    )
    data = _parse_json_data(url)
    attrs = data[0]["attributes"]
    assert attrs["area-id"] == "uuid-abc"
    assert "area" not in attrs


def test_add_project_json_no_area_by_default():
    """Neither area key appears when neither is supplied to the JSON path."""
    url = url_scheme.build_add_project_url(title="Proj", headings=["H1"])
    data = _parse_json_data(url)
    attrs = data[0]["attributes"]
    assert "area" not in attrs
    assert "area-id" not in attrs


# ---------- ProposeAddProjectInput mutual exclusion ----------


def test_model_area_alone_is_valid():
    m = ProposeAddProjectInput(title="T", area="Work")
    assert m.area == "Work"
    assert m.area_id is None


def test_model_area_id_alone_is_valid():
    m = ProposeAddProjectInput(title="T", area_id="uuid-xyz")
    assert m.area_id == "uuid-xyz"
    assert m.area is None


def test_model_area_and_area_id_together_raise():
    with pytest.raises(ValueError, match="mutually exclusive"):
        ProposeAddProjectInput(title="T", area="Work", area_id="uuid-xyz")


def test_model_area_empty_string_rejected():
    """min_length=1 on area means empty string should fail."""
    with pytest.raises(Exception):
        ProposeAddProjectInput(title="T", area="")


# ---------- handler threads area through ----------


pytestmark = pytest.mark.usefixtures("isolated_state_db")


@pytest.fixture
def fast_polling(monkeypatch):
    from safe_things_mcp import config
    monkeypatch.setattr(config, "WRITE_POLL_TIMEOUT_SECONDS", 1.0)
    monkeypatch.setattr(config, "WRITE_POLL_INTERVAL_SECONDS", 0.01)


@pytest.fixture
def captured_launches(monkeypatch):
    launches: list[str] = []

    async def fake_launch(url: str) -> None:
        launches.append(url)

    monkeypatch.setattr(url_scheme, "launch", fake_launch)
    return launches


def _stub_project(uuid: str = "proj-1", title: str = "t") -> dict:
    return {
        "uuid": uuid,
        "type": "project",
        "title": title,
        "status": "incomplete",
        "created": "2026-06-22 10:00:00",
    }


async def test_handler_passes_area_name_to_url(
    fast_polling, captured_launches, monkeypatch
):
    """execute() with area='Work' produces a URL containing area=Work."""
    monkeypatch.setattr(
        things_repo, "find_recent_project_by_title",
        lambda title, created_after: _stub_project(title=title),
    )
    monkeypatch.setattr(things_repo, "areas", lambda **kw: [{"title": "Work"}])

    await add_project.execute({"title": "New Project", "area": "Work"})

    assert len(captured_launches) == 1
    url = captured_launches[0]
    assert url.startswith("things:///add-project?")
    params = parse_qs(urlparse(url).query)
    assert params["area"] == ["Work"]
    assert "area-id" not in params


async def test_handler_area_name_with_headings_json_path(
    fast_polling, captured_launches, monkeypatch
):
    """execute() with area + headings produces JSON URL with area key."""
    monkeypatch.setattr(
        things_repo, "find_recent_project_by_title",
        lambda title, created_after: _stub_project(title=title),
    )
    monkeypatch.setattr(things_repo, "areas", lambda **kw: [{"title": "Engineering"}])

    await add_project.execute({
        "title": "Headings Project",
        "area": "Engineering",
        "headings": ["Phase 1", "Phase 2"],
    })

    assert len(captured_launches) == 1
    url = captured_launches[0]
    assert url.startswith("things:///json?data=")
    data = _parse_json_data(url)
    attrs = data[0]["attributes"]
    assert attrs["area"] == "Engineering"
