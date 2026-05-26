# Bug handoff: Fix B — `tags` key absent for untagged items (items 128, 130)

Discovered during Round 6 manual verification, 2026-05-26.

---

## Symptoms

`get_todo` and `get_project` return the `tags` field correctly when an item has tags (`"tags": ["Errand"]`), but the key is **entirely absent** from the response when the item has no tags. The expected result is `"tags": []`.

Affected items: **128** (`get_todo` untagged), **130** (`get_project` untagged).

Example — untagged todo UUID `XsMjRWd8m1BWLNDGXarynv`:
```json
{
  "uuid": "XsMjRWd8m1BWLNDGXarynv",
  "title": "Test item 128 — untagged round6",
  "status": "incomplete",
  "notes": "",
  "start": "Inbox",
  ...
  // ← "tags" key missing entirely
}
```

Expected:
```json
{
  ...
  "tags": []
}
```

---

## Root cause

`things.tasks()` from the `things-py` library omits the `tags` key from its return dict when an item has no tags. The `todo()` and `project()` functions in `src/things_mcp/services/things_repo.py` return the raw dict without normalising the absent key to an empty list.

```python
# things_repo.py — current (broken)
def todo(todo_id: str) -> dict[str, Any] | None:
    try:
        row = things.tasks(todo_id, **_kw())
    except ValueError:
        return None
    return row if isinstance(row, dict) else None  # ← tags key may be absent
```

---

## Fix

In `src/things_mcp/services/things_repo.py`, add `row.setdefault("tags", [])` before the return in both `todo()` and `project()`:

```python
def todo(todo_id: str) -> dict[str, Any] | None:
    try:
        row = things.tasks(todo_id, **_kw())
    except ValueError:
        return None
    if isinstance(row, dict):
        row.setdefault("tags", [])
        return row
    return None


def project(project_id: str) -> dict[str, Any] | None:
    row = things.tasks(project_id, type="project", **_kw())
    if isinstance(row, dict):
        row.setdefault("tags", [])
        return row
    return None
```

Also add/update test cases in `tests/test_tag_read.py` to assert the `tags` key is present and equals `[]` for untagged items.

---

## Verification after fix

1. `uv run pytest -q` — all tests green (including updated `test_tag_read.py`).
2. Re-run item 128: `get_todo(<untagged-uuid>)` → response contains `"tags": []`.
3. Re-run item 130: `get_project(<untagged-project-uuid>)` → response contains `"tags": []`.
4. Regression: re-run item 127 (`get_todo` tagged) and item 129 (`get_project` tagged) — confirm `tags` list still populated correctly.
