"""Fix 2A — area existence guard in add_project.execute().

Things cannot create areas via the URL scheme. Passing an unknown area name
must raise ValueError with an actionable message; a known area name must
proceed normally (URL built, no raise).
"""
from __future__ import annotations

import pytest

from things_mcp.services import things_repo, url_scheme
from things_mcp.services.handlers import add_project


pytestmark = pytest.mark.usefixtures("isolated_state_db")


@pytest.fixture
def captured_launches(monkeypatch):
    launches: list[str] = []

    async def fake_launch(url: str) -> None:
        launches.append(url)

    monkeypatch.setattr(url_scheme, "launch", fake_launch)
    return launches


@pytest.fixture
def fake_areas_work(monkeypatch):
    monkeypatch.setattr(things_repo, "areas", lambda **kw: [{"title": "Work"}])


@pytest.fixture
def fake_project_poll(monkeypatch):
    """Return a plausible project row immediately so execute() doesn't time out."""
    monkeypatch.setattr(
        things_repo,
        "find_recent_project_by_title",
        lambda title, created_after: {
            "uuid": "proj-new-1",
            "title": title,
            "status": "incomplete",
            "created": "2026-06-25 10:00:00",
        },
    )


async def test_unknown_area_raises_value_error(monkeypatch, fake_areas_work):
    """Passing an area name that doesn't exist must raise ValueError."""
    with pytest.raises(ValueError, match="does not exist"):
        await add_project.execute({"title": "My Project", "area": "Nope"})


async def test_unknown_area_error_mentions_known_areas(monkeypatch, fake_areas_work):
    """The ValueError must list the known areas so the caller can correct it."""
    with pytest.raises(ValueError, match="Work"):
        await add_project.execute({"title": "My Project", "area": "Nope"})


async def test_known_area_proceeds(
    monkeypatch, fake_areas_work, captured_launches, fake_project_poll
):
    """Passing an area name that exists must proceed without raising."""
    result = await add_project.execute({"title": "My Project", "area": "Work"})

    assert result["id"] == "proj-new-1"
    assert captured_launches, "URL scheme must have been launched"
    assert "area=Work" in captured_launches[0] or "area" in captured_launches[0]


async def test_no_area_skips_guard(
    monkeypatch, captured_launches, fake_project_poll
):
    """When area is not supplied the guard must not query things_repo.areas()."""
    called = []
    monkeypatch.setattr(
        things_repo, "areas", lambda **kw: called.append(True) or []
    )

    result = await add_project.execute({"title": "My Project"})

    assert not called, "areas() must not be called when area param is absent"
    assert result["id"] == "proj-new-1"
