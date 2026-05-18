"""V2 URL-scheme builder tests.

``build_add_url_v2`` and ``build_update_url`` are pure functions — these
tests pin their behaviour without touching Things or the network.
"""
from __future__ import annotations

from urllib.parse import parse_qsl, urlparse

import pytest

from things_mcp.services import url_scheme


def _params(url: str) -> dict[str, str]:
    return dict(parse_qsl(urlparse(url).query, keep_blank_values=True))


# ---------- build_add_url_v2 ----------


def test_add_v2_inbox_uses_list_keyword():
    url = url_scheme.build_add_url_v2(title="t", list_id="inbox")
    p = _params(url)
    assert p["title"] == "t"
    assert p["list"] == "inbox"
    assert "list-id" not in p


def test_add_v2_today_uses_list_keyword():
    p = _params(url_scheme.build_add_url_v2(title="t", list_id="today"))
    assert p == {"title": "t", "list": "today"}


def test_add_v2_uuid_uses_list_id_param():
    # 22-char Things UUID
    uuid = "8T1gpHZBw2mZFD7q3F2cjn"
    p = _params(url_scheme.build_add_url_v2(title="t", list_id=uuid))
    assert p["list-id"] == uuid
    assert "list" not in p


def test_add_v2_full_payload():
    p = _params(
        url_scheme.build_add_url_v2(
            title="Plan",
            list_id="anytime",
            notes="hi",
            when="tomorrow",
            deadline="2026-12-31",
            tags=["a", "b"],
            checklist_items=["one", "two"],
        )
    )
    assert p["list"] == "anytime"
    assert p["notes"] == "hi"
    assert p["when"] == "tomorrow"
    assert p["deadline"] == "2026-12-31"
    assert p["tags"] == "a,b"
    assert p["checklist-items"] == "one\ntwo"


def test_add_v2_does_not_inbox_guard():
    """V2 builder must NOT raise for non-Inbox lists. The Inbox guard
    lives only on the V1 ``build_add_url`` per CLAUDE.md."""
    url_scheme.build_add_url_v2(title="t", list_id="today")
    url_scheme.build_add_url_v2(title="t", list_id="someday")
    url_scheme.build_add_url_v2(title="t", list_id="PROJECT_UUID")


def test_v1_inbox_guard_still_intact():
    """Regression: the V1 guard must continue to raise. CLAUDE.md hard rule."""
    with pytest.raises(ValueError, match="V1 only supports list='inbox'"):
        url_scheme.build_add_url(title="t", list_id="today")


@pytest.mark.parametrize("bad", ["", None])
def test_add_v2_rejects_empty(bad):
    with pytest.raises(ValueError):
        url_scheme.build_add_url_v2(title=bad or "", list_id="inbox")
    with pytest.raises(ValueError):
        url_scheme.build_add_url_v2(title="t", list_id=bad or "")


# ---------- build_update_url ----------


def test_update_minimal_requires_id_and_token():
    p = _params(url_scheme.build_update_url(id="u1", auth_token="tok"))
    assert p == {"id": "u1", "auth-token": "tok"}


def test_update_completed_canceled_flags():
    p = _params(
        url_scheme.build_update_url(
            id="u1", auth_token="tok", completed=True, canceled=True
        )
    )
    assert p["completed"] == "true"
    assert p["canceled"] == "true"


def test_update_full_payload():
    p = _params(
        url_scheme.build_update_url(
            id="u1",
            auth_token="tok",
            title="new title",
            notes="new notes",
            when="today",
            deadline="2026-06-01",
            tags=["x", "y"],
        )
    )
    assert p["title"] == "new title"
    assert p["notes"] == "new notes"
    assert p["when"] == "today"
    assert p["deadline"] == "2026-06-01"
    assert p["tags"] == "x,y"


def test_update_requires_auth_token():
    with pytest.raises(ValueError, match="auth_token is required"):
        url_scheme.build_update_url(id="u1", auth_token="")


def test_update_requires_id():
    with pytest.raises(ValueError, match="id is required"):
        url_scheme.build_update_url(id="", auth_token="tok")
