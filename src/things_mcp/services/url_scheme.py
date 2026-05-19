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

# Built-in list keywords that route via ``when=`` (not ``list=``).
# The Things URL scheme ``list`` parameter only accepts project/area names;
# built-in scheduling targets must use ``when=``.
# ``inbox`` is the default destination when neither ``when`` nor ``list-id``
# is present, so it needs no extra parameter at all.
_V2_WHEN_KEYWORDS = {"today", "anytime", "someday"}

# Computed views in Things that are NOT valid write destinations.
# Surfacing a clear error beats silently emitting ``list-id=upcoming``
# (which would be interpreted as a project UUID lookup and fail).
_V2_COMPUTED_VIEWS = {"upcoming", "logbook", "trash"}


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
    """V2 ``things:///add`` URL builder.

    Routing rules (per Things URL scheme docs):
    - ``inbox``            → no extra param (Things default destination)
    - ``today`` / ``anytime`` / ``someday`` → ``when=<value>``
    - any other string     → ``list-id=<value>`` (project or area UUID)
    """
    if not title:
        raise ValueError("title is required")
    if not list_id:
        raise ValueError("list_id is required")

    params: list[tuple[str, str]] = [("title", title)]
    list_id_lower = list_id.lower()
    if list_id_lower in _V2_COMPUTED_VIEWS:
        raise ValueError(
            f"list_id={list_id!r} is a computed view in Things, not a write "
            "destination. To schedule a task for a future date that appears in "
            "Upcoming, use `when='<YYYY-MM-DD>'` (e.g. when='2026-05-25'). "
            "Logbook and Trash are read-only."
        )
    if list_id_lower == "inbox":
        pass  # default destination — no parameter needed
    elif list_id_lower in _V2_WHEN_KEYWORDS:
        # Explicit ``when`` arg overrides list_id routing (it's more specific).
        if not when:
            params.append(("when", list_id_lower))
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
    list_id: str | None = None,
) -> str:
    """V2 ``things:///update`` URL. Requires ``auth_token`` (see Things →
    Settings → General → Enable Things URLs → Manage).

    ``list_id`` moves the task into a project/area by UUID. Pass ``""``
    (empty string) to clear project/area membership (best-effort — Things
    behaviour on empty ``list-id`` is documented as a follow-up gap).
    """
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
    if list_id is not None:
        params.append(("list-id", list_id))

    return "things:///update?" + urlencode(params, quote_via=quote)


async def launch(url: str) -> None:
    """Hand the URL to macOS via `open`. Non-blocking on the event loop."""
    await asyncio.to_thread(
        subprocess.run,
        ["open", url],
        check=True,
        capture_output=True,
    )
