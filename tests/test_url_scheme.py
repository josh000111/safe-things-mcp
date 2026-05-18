"""URL-scheme builder unit tests.

No network, no Things app, no DB — these run anywhere as any user. Their
job is to lock in:

* The Inbox-only guard. ``build_add_url`` must raise for any non-Inbox
  ``list_id`` until V2 lights up the propose/confirm path. This guard is
  load-bearing safety; the project CLAUDE.md flags it as a hard rule.
* The shape of the generated URL after the callback removal: no
  ``x-success`` / ``x-error`` params, all optional fields properly
  encoded.
"""
from __future__ import annotations

from urllib.parse import parse_qsl, urlparse

import pytest

from things_mcp.services import url_scheme


def _params(url: str) -> dict[str, str]:
    return dict(parse_qsl(urlparse(url).query, keep_blank_values=True))


def test_build_add_url_minimal_inbox():
    url = url_scheme.build_add_url(title="Buy milk", list_id="inbox")
    assert url.startswith("things:///add?")
    params = _params(url)
    assert params == {"title": "Buy milk", "list": "inbox"}


def test_build_add_url_omits_callback_params():
    """Post-callback-removal: no x-success or x-error should appear."""
    url = url_scheme.build_add_url(title="t", list_id="inbox")
    assert "x-success" not in url
    assert "x-error" not in url


def test_build_add_url_full_payload():
    url = url_scheme.build_add_url(
        title="Plan trip",
        list_id="inbox",
        notes="line1\nline2",
        when="tomorrow",
        deadline="2026-12-31",
        tags=["travel", "urgent"],
        checklist_items=["passport", "tickets"],
    )
    params = _params(url)
    assert params["title"] == "Plan trip"
    assert params["list"] == "inbox"
    assert params["notes"] == "line1\nline2"
    assert params["when"] == "tomorrow"
    assert params["deadline"] == "2026-12-31"
    assert params["tags"] == "travel,urgent"
    assert params["checklist-items"] == "passport\ntickets"


def test_build_add_url_inbox_case_insensitive():
    # Inbox guard accepts any casing; lower-cased once inside the params.
    url = url_scheme.build_add_url(title="t", list_id="Inbox")
    assert _params(url)["list"] == "inbox"


@pytest.mark.parametrize("bad_list", ["today", "anytime", "someday", "PROJECT_UUID"])
def test_build_add_url_rejects_non_inbox(bad_list):
    with pytest.raises(ValueError, match="V1 only supports list='inbox'"):
        url_scheme.build_add_url(title="t", list_id=bad_list)
