# Handoff — Build Step 5B (propose_reorder_todos)

Working directory: `/Users/Shared/things-mcp`. Branch: `main`.
Run all commands as `joshsmith`.

---

## Context

Step 5C was closed and verified (Round 9 — 2026-05-30). Suite is at **354 tests**.

Step 5B is the final unbuilt step: `propose_reorder_todos` with native-heading
auto-conversion. The test file has already been written and confirmed RED.

**Do not write any production code until you have read this entire document.**

---

## What was done in the previous session

1. `tests/test_step5b_reorder.py` — written and confirmed RED (import error:
   `reorder` module missing). All test names and assertions are final.
2. Architecture doc at
   `docs/things-mcp-V2-technical-architecture-and-implementation-plan.md` is the
   authoritative spec (§5.3 + the status table at line 23).
3. A detailed implementation plan exists at
   `/Users/joshsmith/.claude/plans/review-docs-things-mcp-v2-technical-arch-declarative-hennessy.md`
   — the **5B section (lines ~80–108)** is the source of truth for algorithm
   and data-flow decisions.

---

## Files to create / modify

```
src/things_mcp/
├── services/
│   ├── reorder.py                       NEW
│   ├── things_repo.py                   MODIFY — add get_container_todo_uuids()
│   └── handlers/
│       ├── __init__.py                  MODIFY — import + register reorder_todos
│       └── reorder_todos.py             NEW
└── tools/
    └── propose.py                       MODIFY — add propose_reorder_todos() + register
```

No new model in `models.py` needed — the payload is a plain dict.

---

## Implementation spec

### `services/reorder.py` (NEW)

Three pure functions — no I/O, no imports of things_repo:

```python
def resolve_container(container: str) -> tuple[str, str]:
    """Return (container_type, container_id).

    Built-in list names (case-insensitive) → ("list", "TitleCase").
    Anything else → ("project", container).
    """
    _LIST_MAP = {
        "inbox": "Inbox", "today": "Today", "anytime": "Anytime",
        "someday": "Someday", "upcoming": "Upcoming",
        "logbook": "Logbook", "trash": "Trash",
    }
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

    Full reorder (len(requested) == len(current)) is handled naturally:
    every position is a slot, so the result equals requested_new_order exactly.
    """

def detect_native_headings_in_project(proj: dict | None) -> list[dict]:
    """Return native headings with their todo-list-relative insertion positions.

    Returns [] for None (list containers don't have headings).

    Each entry: {id, name, todo_position}
    todo_position = number of to-do items seen before this heading in proj["items"].
    This is the insertion index in the todo-only UUID list where the dummy
    should be spliced in at execute time.
    """
```

### `services/things_repo.py` — add `get_container_todo_uuids()`

```python
def get_container_todo_uuids(container_type: str, container_id: str) -> list[str]:
    """Return ordered list of to-do UUIDs in the container.

    For built-in lists: calls the appropriate list function (today(), inbox(), etc.)
    and returns UUIDs in Things' current display order.
    For projects: returns UUIDs of items with type=="to-do" only
    (native headings are excluded — they're handled separately).
    Raises ValueError for unknown list names or missing projects.
    """
    if container_type == "project":
        proj = project(container_id)
        if proj is None:
            raise ValueError(f"No project found with id={container_id!r}.")
        return [item["uuid"] for item in (proj.get("items") or [])
                if item.get("type") == "to-do"]
    # list branch
    _LIST_FN = {
        "Inbox": inbox, "Today": today, "Anytime": anytime,
        "Someday": someday, "Upcoming": upcoming,
        "Logbook": logbook, "Trash": trash,
    }
    fn = _LIST_FN.get(container_id)
    if fn is None:
        raise ValueError(f"Unknown list: {container_id!r}")
    return [t["uuid"] for t in fn()]
```

### `services/handlers/reorder_todos.py` (NEW)

```
KIND = "reorder_todos"
```

**make_preview(payload)**:
- Mention container name + count of todos being reordered
- If `dummy_creation_plan` is non-empty: warn that N native headings will be
  auto-converted to dummy headings at their original positions, and that the
  original empty native headings will appear at the project bottom after reorder.
  Also note that **undo cannot reinstate native heading positions**.

**execute(payload)**:
```
payload keys:
  container_type: "list" | "project"
  container_id: str
  master_order: list[str]       # desired final UUID order (todos only)
  dummy_creation_plan: list[{name: str, todo_position: int}]
  original_order: list[str]     # for undo
  created_dummy_uuids: list[str]  # populated during execute, stored in undo_log
```

Execute flow (in order):
1. Guard: `ALLOW_APPLESCRIPT` → raise RuntimeError("… THINGS_MCP_ALLOW_APPLESCRIPT …")
2. Guard: `ALLOW_EXPERIMENTAL_REORDER` → raise RuntimeError("… THINGS_MCP_ALLOW_EXPERIMENTAL_REORDER …")
3. For each entry in `dummy_creation_plan`:
   - Build a dummy title via `dummy_heading.make_dummy_title(entry["name"])`
   - Launch URL scheme: `build_add_url_v2(title=dummy_title, list_id=container_id)`
     (only works for projects; list containers have no dummy_creation_plan)
   - Poll via `find_recent_by_title(dummy_title, created_after)` (same pattern as add_heading.py)
   - Collect the new UUID; track in `created_dummy_uuids`
4. Splice newly-created dummy UUIDs into `master_order` at their `todo_position` indices:
   - Iterate dummy_creation_plan entries in reverse order (so earlier inserts don't
     shift later positions): `master_order.insert(entry["todo_position"], dummy_uuid)`
5. **Race-window check**: re-read `things_repo.get_container_todo_uuids(container_type, container_id)`.
   Compute unexpected = (current_set − set(original_order) − set(created_dummy_uuids)).
   If unexpected is non-empty → raise RuntimeError("stale: … re-propose required")
6. **Write undo_log BEFORE AppleScript** (V2 acceptance gate):
   ```python
   entry_id = undo_log.record(
       action_kind=KIND,
       target_uuid=None,
       before_state={
           "container_type": container_type,
           "container_id": container_id,
           "original_order": original_order,
           "created_dummy_uuids": created_dummy_uuids,
       },
       after_state=None,
   )
   ```
7. Build and run AppleScript:
   - List: `_private_experimental_ reorder to dos in list "<escape(container_id)>" with ids "<uuid1,uuid2,...>"`
   - Project: `_private_experimental_ reorder to dos in project id "<escape(container_id)>" with ids "..."`
   - UUIDs joined with commas; each UUID escaped via `applescript.escape()`
   - Wrap in `tell application "Things3" … end tell`
8. Return `{action_kind: KIND, undo_id: entry_id, container_type, container_id, new_order: final_order}`

**undo(undo_entry)**:
1. Guard: ALLOW_APPLESCRIPT + ALLOW_EXPERIMENTAL_REORDER
2. Read before_state from undo_entry
3. For each uuid in `created_dummy_uuids` (reverse order is fine):
   - Launch URL scheme soft-delete: `build_update_url(id=uuid, auth_token=..., completed=True, canceled=True)`
   - (no polling required — best-effort)
4. Run AppleScript reorder with `original_order` UUIDs
   (note: original_order does NOT include the dummy UUIDs; they're being deleted)
5. `undo_log.delete(undo_entry["id"])`
6. Return `{undone: True, action_kind: KIND}`

### `tools/propose.py` — add `propose_reorder_todos()`

```python
async def propose_reorder_todos(container: str, new_order: list[str]) -> dict:
    """Propose reordering to-dos in a list or project.

    container: built-in list name ("inbox", "today", "anytime", "someday")
               or a project UUID.
    new_order: list of to-do UUIDs in the desired order. May be a complete
               list (full reorder) or a partial list (partial reorder —
               specified UUIDs are placed in the given relative order at
               their original sorted positions; other todos keep relative
               positions).

    Requires THINGS_MCP_ALLOW_APPLESCRIPT=1 and
    THINGS_MCP_ALLOW_EXPERIMENTAL_REORDER=1.

    Projects with native headings: native headings are auto-converted to
    dummy heading tasks at their original positions before reorder. The
    original empty native headings appear at the project bottom and must
    be deleted manually. Undo cannot reinstate native heading positions.
    """
    if not new_order:
        raise ValueError("new_order must contain at least one UUID.")

    from ..services.reorder import resolve_container, build_master_order, detect_native_headings_in_project

    container_type, container_id = resolve_container(container)
    current_uuids = things_repo.get_container_todo_uuids(container_type, container_id)
    # raises ValueError if any UUID in new_order not in current_uuids:
    master_order = build_master_order(current_uuids, new_order)

    proj_row = things_repo.project(container_id) if container_type == "project" else None
    native_headings = detect_native_headings_in_project(proj_row)
    dummy_creation_plan = [
        {"name": h["name"], "todo_position": h["todo_position"]}
        for h in native_headings
    ]

    payload = {
        "container_type": container_type,
        "container_id": container_id,
        "master_order": master_order,
        "dummy_creation_plan": dummy_creation_plan,
        "original_order": current_uuids,
        "created_dummy_uuids": [],
    }

    from ..services.handlers import reorder_todos as _reorder_todos
    preview = _reorder_todos.make_preview(payload)
    return await _enqueue_and_maybe_auto_confirm(
        kind=_reorder_todos.KIND, payload=payload, preview=preview
    )
```

Add `mcp.tool()(propose_reorder_todos)` to the `register()` function.

---

## Test file

Already written at `tests/test_step5b_reorder.py`. Do not modify the test
assertions — they are the spec. You may add `@pytest.mark.asyncio` markers
or fixtures if pytest-asyncio needs them.

Check the conftest for `isolated_state_db` fixture — it's used by all handler tests.

---

## TDD discipline

Follow strictly:
1. Run `uv run pytest tests/test_step5b_reorder.py -x -q` after each file is created.
2. Watch tests go from RED to GREEN one class at a time.
3. Do NOT modify test assertions to make tests pass — fix the implementation.

---

## Acceptance checklist (before declaring build done)

- [ ] `uv run pytest -q --ignore=tests/test_step5a_live.py --ignore=tests/test_step5e_live.py`
      — all pass (expect 354 + new tests)
- [ ] `uv run things-mcp --help` — exits 0
- [ ] No test assertions were modified (only implementation written)
- [ ] Handler is registered in `services/handlers/__init__.py`
- [ ] Tool is registered in `tools/propose.py::register()`
- [ ] `reorder_todos.KIND` is NOT in `config.NEVER_BYPASS_KINDS`

## Flag simplification — do this BEFORE implementing

Merge `THINGS_MCP_ALLOW_EXPERIMENTAL_REORDER` into `THINGS_MCP_ALLOW_APPLESCRIPT`.
The separate flag was an extra safety gate for the undocumented reorder command,
but the propose/confirm flow already provides that gate. Two flags = unnecessary
setup friction for users.

Changes required:
1. `config.py` — remove `ALLOW_EXPERIMENTAL_REORDER`. The reorder handler should
   check only `ALLOW_APPLESCRIPT`.
2. `tools/meta.py` — remove `experimental_reorder_enabled` and
   `reorder_command_available` from `HealthReport` / `health()`, OR keep them but
   derive `experimental_reorder_enabled` from `ALLOW_APPLESCRIPT`.
3. `models.py` — remove or alias `experimental_reorder_enabled` in `HealthReport`.
4. `tests/` — update any tests that reference `ALLOW_EXPERIMENTAL_REORDER` to use
   `ALLOW_APPLESCRIPT` only.
5. In `test_step5b_reorder.py`, the `with_applescript` fixture already sets both —
   after the merge it only needs to set `ALLOW_APPLESCRIPT`.

Also — README update required:
Add `THINGS_MCP_ALLOW_APPLESCRIPT` to the env var table in README.md (currently
only `THINGS_AUTH_TOKEN` is documented there). The new row should explain:
- What it enables (hard-delete via AppleScript, reorder via hidden AppleScript command)
- Why it's off by default (triggers macOS Automation permission; explicit opt-in)
- How to set it (same `env` block in the MCP client config as THINGS_AUTH_TOKEN)
- Example claude_desktop_config.json snippet showing both vars together

---

## After build is green

This step requires a manual Test-user verification session (same pattern as
Step 5A Round 7 and Step 5E Round 8). Do NOT mark the architecture doc as
verified until that session completes. Write a handoff doc for the manual
session following the same pattern as `tests/handoff-step-5c-close-and-next.md`.

Manual test items to run (from the plan at
`/Users/joshsmith/.claude/plans/review-docs-things-mcp-v2-technical-arch-declarative-hennessy.md`
lines 190–208):
- 5B no-headings: reorder 5 todos in Today (partial swap 2), verify others keep positions
- 5B no-headings: reorder todos in a project without native headings
- 5B no-headings: undo — verify original order restored
- 5B no-headings: race-window — add task in Things while propose pending, then confirm → expect stale error
- 5B native headings: full reorder in project with 2 native headings — verify dummies created at correct positions, native headings at bottom
- 5B native headings: undo — verify order restored, dummies soft-deleted
