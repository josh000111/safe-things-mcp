"""Things URL scheme builder + launcher.

V1 only exposes the `add` action with `list=inbox` hard-coded. Any attempt to
build an `add` URL for a non-Inbox list raises before launch.
"""
from __future__ import annotations

import asyncio
import json
import subprocess
from typing import Any
from urllib.parse import quote, urlencode


def validate_tags(requested: list[str] | None) -> None:
    """Raise ValueError with actionable message if any tag doesn't exist in Things."""
    if not requested:
        return
    from . import things_repo
    known = things_repo.get_tag_names()
    unknown = [t for t in requested if t not in known]
    if unknown:
        raise ValueError(
            f"Unknown tag(s): {unknown}. "
            f"Available tags: {sorted(known)}. "
            "Create the tag in Things first, then retry."
        )


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


def build_add_project_url(
    *,
    title: str,
    area: str | None = None,
    area_id: str | None = None,
    when: str | None = None,
    deadline: str | None = None,
    notes: str | None = None,
    tags: list[str] | None = None,
    headings: list[str] | None = None,
) -> str:
    """V2 ``things:///add-project`` URL builder.

    Two code paths:

    * ``headings`` empty / None → ``things:///add-project?title=...&...``.
      No auth token needed (add-project is unauthenticated).
    * ``headings`` non-empty → ``things:///json?data=<url-encoded JSON>``.
      The JSON endpoint is the ONLY URL-scheme mechanism that creates
      native section headings inside a *new* project. See arch doc §5.3.

    ``area`` is an **existing** area NAME; the URL scheme does **not** create
    areas (the handler validates existence before calling this). ``area_id``
    is an existing area UUID. Pass at most one.

    Computed views (Upcoming, Logbook, Trash) aren't relevant for projects
    so no view-rejection is needed here.
    """
    if not title:
        raise ValueError("title is required")

    if headings:
        return _build_add_project_json_url(
            title=title,
            area=area,
            area_id=area_id,
            when=when,
            deadline=deadline,
            notes=notes,
            tags=tags,
            headings=headings,
        )

    params: list[tuple[str, str]] = [("title", title)]
    if area:
        params.append(("area", area))
    if area_id:
        params.append(("area-id", area_id))
    if when:
        params.append(("when", when))
    if deadline:
        params.append(("deadline", deadline))
    if notes:
        params.append(("notes", notes))
    if tags:
        params.append(("tags", ",".join(tags)))

    return "things:///add-project?" + urlencode(params, quote_via=quote)


def _build_add_project_json_url(
    *,
    title: str,
    area: str | None,
    area_id: str | None,
    when: str | None,
    deadline: str | None,
    notes: str | None,
    tags: list[str] | None,
    headings: list[str],
) -> str:
    """Encode an add-project + native-headings payload as ``things:///json``.

    Things' JSON URL scheme wraps everything in an ``attributes`` object;
    headings are sibling items under ``items`` (Things creates them in the
    listed order at project birth).

    ``area`` is an **existing** area NAME (validated by the handler before
    this is called). ``area_id`` is an existing area UUID. Pass at most one.
    """
    project_attrs: dict[str, Any] = {"title": title}
    if area:
        project_attrs["area"] = area
    if area_id:
        project_attrs["area-id"] = area_id
    if when:
        project_attrs["when"] = when
    if deadline:
        project_attrs["deadline"] = deadline
    if notes:
        project_attrs["notes"] = notes
    if tags:
        project_attrs["tags"] = list(tags)

    project_attrs["items"] = [
        {"type": "heading", "attributes": {"title": h}} for h in headings
    ]

    payload = [{"type": "project", "attributes": project_attrs}]
    encoded = quote(json.dumps(payload, ensure_ascii=False), safe="")
    return "things:///json?data=" + encoded


def build_update_project_url(
    *,
    id: str,
    auth_token: str,
    title: str | None = None,
    notes: str | None = None,
    when: str | None = None,
    deadline: str | None = None,
    tags: list[str] | None = None,
    area_id: str | None = None,
    completed: bool | None = None,
    canceled: bool | None = None,
) -> str:
    """V2 ``things:///update-project`` URL. Requires ``auth_token``.

    Mirrors :func:`build_update_url` for to-dos; the parameter names that
    differ on the URL-scheme side (``area-id``) are translated here.

    ``completed=True, canceled=True`` together is the cancel-to-Logbook shape the
    ``add_project`` undo path relies on (analogous to the to-do cancel-to-Logbook path).
    """
    if not id:
        raise ValueError("id is required")
    if not auth_token:
        raise ValueError(
            "auth_token is required for things:///update-project. Generate "
            "it in Things → Settings → General → Enable Things URLs → "
            "Manage, then set THINGS_AUTH_TOKEN."
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
    if area_id is not None:
        params.append(("area-id", area_id))

    return "things:///update-project?" + urlencode(params, quote_via=quote)


def build_append_checklist_url(
    *, todo_id: str, items: list[str], auth_token: str
) -> str:
    if not todo_id:
        raise ValueError("todo_id is required")
    if not auth_token:
        raise ValueError("auth_token is required")
    params: list[tuple[str, str]] = [
        ("id", todo_id),
        ("auth-token", auth_token),
        ("append-checklist-items", "\n".join(items)),
    ]
    return "things:///update?" + urlencode(params, quote_via=quote)


def build_prepend_checklist_url(
    *, todo_id: str, items: list[str], auth_token: str
) -> str:
    if not todo_id:
        raise ValueError("todo_id is required")
    if not auth_token:
        raise ValueError("auth_token is required")
    params: list[tuple[str, str]] = [
        ("id", todo_id),
        ("auth-token", auth_token),
        ("prepend-checklist-items", "\n".join(items)),
    ]
    return "things:///update?" + urlencode(params, quote_via=quote)


def build_replace_checklist_url(
    *, todo_id: str, items: list[str], auth_token: str
) -> str:
    if not todo_id:
        raise ValueError("todo_id is required")
    if not auth_token:
        raise ValueError("auth_token is required")
    params: list[tuple[str, str]] = [
        ("id", todo_id),
        ("auth-token", auth_token),
        ("checklist-items", "\n".join(items)),
    ]
    return "things:///update?" + urlencode(params, quote_via=quote)


async def launch(url: str) -> None:
    """Hand the URL to macOS via `open`. Non-blocking on the event loop."""
    await asyncio.to_thread(
        subprocess.run,
        ["open", url],
        check=True,
        capture_output=True,
    )
