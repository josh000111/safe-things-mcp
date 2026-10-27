"""Pure functions for the propose_reorder_todos algorithm.

No I/O, no imports of things_repo. All functions are deterministic.
"""
from __future__ import annotations

_LIST_MAP = {
    "inbox": "Inbox", "today": "Today", "anytime": "Anytime",
    "someday": "Someday", "upcoming": "Upcoming",
    "logbook": "Logbook", "trash": "Trash",
}


def resolve_container(container: str) -> tuple[str, str]:
    """Return (container_type, container_id).

    Built-in list names (case-insensitive) → ("list", "TitleCase").
    Anything else → ("project", container).
    """
    canonical = _LIST_MAP.get(container.lower())
    if canonical:
        return ("list", canonical)
    return ("project", container)


def build_master_order(current_uuids: list[str], requested_new_order: list[str]) -> list[str]:
    """Merge a (possibly partial) requested order into the current UUID list.

    Algorithm — stable-sort at original positions:
    1. Validate all requested UUIDs exist in current_uuids; raise ValueError if not.
    2. Find original indices of the requested UUIDs.
    3. Sort those indices ascending → these are the "slots".
    4. Assign requested[i] → slots[i].
    5. Non-requested UUIDs stay at their original positions.
    Result: a complete list with the same length as current_uuids.
    """
    if not requested_new_order:
        return list(current_uuids)

    current_set = set(current_uuids)
    for uuid in requested_new_order:
        if uuid not in current_set:
            raise ValueError(
                f"{uuid!r} not found in current container. "
                "Re-read the container and retry with valid UUIDs."
            )

    requested_set = set(requested_new_order)
    slots = sorted(i for i, u in enumerate(current_uuids) if u in requested_set)

    result = list(current_uuids)
    for slot, new_uuid in zip(slots, requested_new_order):
        result[slot] = new_uuid

    return result


def detect_native_headings_in_project(proj: dict | None) -> list[dict]:
    """Return native headings with their todo-list-relative insertion positions.

    Returns [] for None (list containers don't have headings).

    Each entry: {id, name, todo_position}
    todo_position = number of to-do items seen before this heading in proj["items"].
    """
    if proj is None:
        return []

    headings = []
    todo_count = 0
    for item in (proj.get("items") or []):
        item_type = item.get("type", "")
        if item_type == "heading":
            headings.append({
                "id": item["uuid"],
                "name": item.get("title", ""),
                "todo_position": todo_count,
            })
        elif item_type == "to-do":
            todo_count += 1

    return headings
