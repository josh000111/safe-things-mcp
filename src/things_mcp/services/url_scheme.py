"""Things URL scheme builder + launcher.

V1 only exposes the `add` action with `list=inbox` hard-coded. Any attempt to
build an `add` URL for a non-Inbox list raises before launch.
"""
from __future__ import annotations

import asyncio
import subprocess
from urllib.parse import quote, urlencode


def build_add_url(
    *,
    title: str,
    list_id: str,
    notes: str | None = None,
    when: str | None = None,
    deadline: str | None = None,
    tags: list[str] | None = None,
    checklist_items: list[str] | None = None,
) -> str:
    if list_id.lower() != "inbox":
        raise ValueError(
            f"V1 only supports list='inbox'. Got list={list_id!r}. "
            "Non-Inbox writes will arrive in V2 via the propose/confirm pattern."
        )

    params: list[tuple[str, str]] = [("title", title), ("list", "inbox")]
    if notes:
        params.append(("notes", notes))
    if when:
        params.append(("when", when))
    if deadline:
        params.append(("deadline", deadline))
    if tags:
        params.append(("tags", ",".join(tags)))
    if checklist_items:
        params.append(("checklist-items", "\n".join(checklist_items)))

    return "things:///add?" + urlencode(params, quote_via=quote)


# ---------- V2 builders (no Inbox-only guard) ----------
#
# CLAUDE.md hard rule: ``build_add_url`` above must continue to raise for
# any non-Inbox list_id. V2 lives in separate functions so the V1 guard
# stays in place as a tripwire.

_V2_LIST_KEYWORDS = {"inbox", "today", "anytime", "someday", "upcoming"}


def build_add_url_v2(
    *,
    title: str,
    list_id: str,
    notes: str | None = None,
    when: str | None = None,
    deadline: str | None = None,
    tags: list[str] | None = None,
    checklist_items: list[str] | None = None,
) -> str:
    """V2 ``things:///add`` URL builder. Routes to ``list=`` for reserved
    keywords (inbox/today/anytime/someday/upcoming) and ``list-id=`` for
    project/area UUIDs."""
    if not title:
        raise ValueError("title is required")
    if not list_id:
        raise ValueError("list_id is required")

    params: list[tuple[str, str]] = [("title", title)]
    if list_id.lower() in _V2_LIST_KEYWORDS:
        params.append(("list", list_id.lower()))
    else:
        params.append(("list-id", list_id))

    if notes:
        params.append(("notes", notes))
    if when:
        params.append(("when", when))
    if deadline:
        params.append(("deadline", deadline))
    if tags:
        params.append(("tags", ",".join(tags)))
    if checklist_items:
        params.append(("checklist-items", "\n".join(checklist_items)))

    return "things:///add?" + urlencode(params, quote_via=quote)


def build_update_url(
    *,
    id: str,
    auth_token: str,
    completed: bool | None = None,
    canceled: bool | None = None,
    title: str | None = None,
    notes: str | None = None,
    when: str | None = None,
    deadline: str | None = None,
    tags: list[str] | None = None,
) -> str:
    """V2 ``things:///update`` URL. Requires ``auth_token`` (see Things →
    Settings → General → Enable Things URLs → Manage)."""
    if not id:
        raise ValueError("id is required")
    if not auth_token:
        raise ValueError(
            "auth_token is required for things:///update. Generate it in "
            "Things → Settings → General → Enable Things URLs → Manage, "
            "then set THINGS_AUTH_TOKEN."
        )

    params: list[tuple[str, str]] = [("id", id), ("auth-token", auth_token)]
    if completed is not None:
        params.append(("completed", "true" if completed else "false"))
    if canceled is not None:
        params.append(("canceled", "true" if canceled else "false"))
    if title is not None:
        params.append(("title", title))
    if notes is not None:
        params.append(("notes", notes))
    if when is not None:
        params.append(("when", when))
    if deadline is not None:
        params.append(("deadline", deadline))
    if tags is not None:
        params.append(("tags", ",".join(tags)))

    return "things:///update?" + urlencode(params, quote_via=quote)


async def launch(url: str) -> None:
    """Hand the URL to macOS via `open`. Non-blocking on the event loop."""
    await asyncio.to_thread(
        subprocess.run,
        ["open", url],
        check=True,
        capture_output=True,
    )
