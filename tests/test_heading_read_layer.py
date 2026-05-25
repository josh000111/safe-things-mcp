"""Tests for get_project_with_headings and the get_project tool overlay."""
from unittest.mock import patch

from things_mcp.services import things_repo


MOCK_PROJECT = {
    "uuid": "PROJ-1",
    "title": "Test Project",
    "type": "project",
    "items": [
        {"type": "heading", "uuid": "HDG-N1", "title": "Phase 1"},
        {"type": "to-do", "uuid": "TODO-1", "title": "Normal task"},
        {"type": "to-do", "uuid": "HDG-D1", "title": "__DESIGN__"},
        {"type": "to-do", "uuid": "HDG-D2", "title": "__PHASE 2__"},
        {"type": "to-do", "uuid": "TODO-2", "title": "Another task"},
    ],
}


def test_get_project_with_headings_returns_unified_list():
    with patch.object(things_repo, "project", return_value=MOCK_PROJECT):
        result = things_repo.get_project_with_headings("PROJ-1")

    assert result is not None
    headings = result["headings"]
    assert len(headings) == 3  # 1 native + 2 dummy

    native = headings[0]
    assert native["kind"] == "native"
    assert native["id"] == "HDG-N1"
    assert native["name"] == "Phase 1"
    assert native["position"] == 0

    dummy1 = headings[1]
    assert dummy1["kind"] == "dummy"
    assert dummy1["id"] == "HDG-D1"
    assert dummy1["name"] == "DESIGN"
    assert dummy1["position"] == 2

    dummy2 = headings[2]
    assert dummy2["kind"] == "dummy"
    assert dummy2["name"] == "PHASE 2"
    assert dummy2["position"] == 3


def test_get_project_with_headings_no_project():
    with patch.object(things_repo, "project", return_value=None):
        result = things_repo.get_project_with_headings("MISSING")
    assert result is None


def test_get_project_with_headings_empty_project():
    proj = {"uuid": "PROJ-2", "title": "Empty", "type": "project", "items": []}
    with patch.object(things_repo, "project", return_value=proj):
        result = things_repo.get_project_with_headings("PROJ-2")
    assert result["headings"] == []


def test_get_project_with_headings_no_headings():
    """Project with only regular to-dos — headings list is empty."""
    proj = {
        "uuid": "PROJ-3",
        "title": "No Headings",
        "type": "project",
        "items": [
            {"type": "to-do", "uuid": "T1", "title": "Task A"},
            {"type": "to-do", "uuid": "T2", "title": "Task B"},
        ],
    }
    with patch.object(things_repo, "project", return_value=proj):
        result = things_repo.get_project_with_headings("PROJ-3")
    assert result["headings"] == []


def test_items_list_preserved():
    """items stays intact; headings is an additive overlay."""
    with patch.object(things_repo, "project", return_value=MOCK_PROJECT):
        result = things_repo.get_project_with_headings("PROJ-1")
    assert result["items"] == MOCK_PROJECT["items"]
