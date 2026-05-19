"""Unit tests for the project URL-scheme builders.

Covers:
* ``build_add_project_url`` — both the plain ``add-project`` form and
  the ``things:///json`` form (used when ``headings`` is non-empty).
* ``build_update_project_url`` — auth-gated update form, including the
  soft-delete shape used by the ``add_project`` undo path.
"""
from __future__ import annotations

import json
from urllib.parse import parse_qs, unquote, urlparse

import pytest

from things_mcp.services import url_scheme


# ---------- build_add_project_url (plain) ----------


def test_add_project_minimal():
    url = url_scheme.build_add_project_url(title="Quarterly review")
    assert url.startswith("things:///add-project?")
    params = parse_qs(urlparse(url).query)
    assert params["title"] == ["Quarterly review"]
    # No other params present
    assert set(params.keys()) == {"title"}


def test_add_project_with_all_optional_fields():
    url = url_scheme.build_add_project_url(
        title="Q3 launch",
        area_id="area-abc-123",
        when="anytime",
        deadline="2026-09-30",
        notes="Cross-team coordination",
        tags=["work", "high-priority"],
    )
    params = parse_qs(urlparse(url).query)
    assert params["title"] == ["Q3 launch"]
    assert params["area-id"] == ["area-abc-123"]
    assert params["when"] == ["anytime"]
    assert params["deadline"] == ["2026-09-30"]
    assert params["notes"] == ["Cross-team coordination"]
    assert params["tags"] == ["work,high-priority"]


def test_add_project_requires_title():
    with pytest.raises(ValueError, match="title is required"):
        url_scheme.build_add_project_url(title="")


# ---------- build_add_project_url (JSON path with headings) ----------


def _parse_json_data(url: str) -> list:
    assert url.startswith("things:///json?data=")
    payload = url.removeprefix("things:///json?data=")
    return json.loads(unquote(payload))


def test_add_project_with_headings_routes_through_json():
    url = url_scheme.build_add_project_url(
        title="New launch",
        headings=["Design", "Dev", "QA"],
    )
    assert url.startswith("things:///json?")
    data = _parse_json_data(url)
    assert isinstance(data, list) and len(data) == 1
    project = data[0]
    assert project["type"] == "project"
    attrs = project["attributes"]
    assert attrs["title"] == "New launch"
    items = attrs["items"]
    assert [i["type"] for i in items] == ["heading", "heading", "heading"]
    assert [i["attributes"]["title"] for i in items] == ["Design", "Dev", "QA"]


def test_add_project_json_includes_optional_fields():
    url = url_scheme.build_add_project_url(
        title="Q4",
        area_id="area-1",
        when="anytime",
        deadline="2026-12-31",
        notes="big quarter",
        tags=["work"],
        headings=["Planning", "Execution"],
    )
    data = _parse_json_data(url)
    attrs = data[0]["attributes"]
    assert attrs["title"] == "Q4"
    assert attrs["area-id"] == "area-1"
    assert attrs["when"] == "anytime"
    assert attrs["deadline"] == "2026-12-31"
    assert attrs["notes"] == "big quarter"
    assert attrs["tags"] == ["work"]
    assert len(attrs["items"]) == 2


def test_add_project_json_handles_unicode_in_heading():
    url = url_scheme.build_add_project_url(
        title="Équipe",
        headings=["Conception", "Développement"],
    )
    data = _parse_json_data(url)
    assert data[0]["attributes"]["title"] == "Équipe"
    assert data[0]["attributes"]["items"][1]["attributes"]["title"] == "Développement"


def test_empty_headings_list_uses_plain_add_project():
    """Empty list (vs None) should NOT route through json — there are no
    headings to create."""
    url = url_scheme.build_add_project_url(title="No-headings", headings=[])
    assert url.startswith("things:///add-project?")


# ---------- build_update_project_url ----------


def test_update_project_requires_id():
    with pytest.raises(ValueError, match="id is required"):
        url_scheme.build_update_project_url(id="", auth_token="tok")


def test_update_project_requires_auth_token():
    with pytest.raises(ValueError, match="auth_token is required"):
        url_scheme.build_update_project_url(id="abc", auth_token="")


def test_update_project_passes_through_fields():
    url = url_scheme.build_update_project_url(
        id="proj-123",
        auth_token="tok-xyz",
        title="Renamed",
        notes="updated",
        when="today",
        deadline="2026-08-01",
        tags=["a", "b"],
        area_id="area-9",
    )
    params = parse_qs(urlparse(url).query)
    assert params["id"] == ["proj-123"]
    assert params["auth-token"] == ["tok-xyz"]
    assert params["title"] == ["Renamed"]
    assert params["notes"] == ["updated"]
    assert params["when"] == ["today"]
    assert params["deadline"] == ["2026-08-01"]
    assert params["tags"] == ["a,b"]
    assert params["area-id"] == ["area-9"]


def test_update_project_soft_delete_shape():
    """The shape ``add_project`` undo relies on."""
    url = url_scheme.build_update_project_url(
        id="proj-1",
        auth_token="tok",
        completed=True,
        canceled=True,
    )
    params = parse_qs(urlparse(url).query)
    assert params["completed"] == ["true"]
    assert params["canceled"] == ["true"]


def test_update_project_clears_strings_with_empty():
    """Empty string for a string field is sent as the literal empty
    string (not dropped) — that's how Things' URL scheme signals 'clear'."""
    url = url_scheme.build_update_project_url(
        id="p", auth_token="tok", notes="", deadline="", area_id="",
    )
    # We can't reliably parse `notes=` etc with parse_qs (it drops empty
    # values by default) so check the raw query string instead.
    raw_query = urlparse(url).query
    assert "notes=" in raw_query
    assert "deadline=" in raw_query
    assert "area-id=" in raw_query


def test_update_project_clears_tags_with_empty_list():
    url = url_scheme.build_update_project_url(
        id="p", auth_token="tok", tags=[],
    )
    raw_query = urlparse(url).query
    assert "tags=" in raw_query
