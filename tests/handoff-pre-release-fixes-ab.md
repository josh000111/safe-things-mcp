# Handoff: Pre-release fixes A & B — implementation session

## Context

Working directory: `/Users/Shared/things-mcp`
Run all commands with `uv run …` (never bare `python`).
Push directly to `main` — no branches or PRs.

This session implements two correctness fixes that must ship before public release. Both are self-contained and touch no propose/confirm plumbing.

**Automated suite at handoff: 227 tests passing.**

Spec: `docs/things-mcp-V2-technical-architecture-and-implementation-plan.md` §11 (Fix A p.445, Fix B p.489).

---

## Fix A — Tag pre-validation for write tools

### Problem
All write tools that accept a `tags` parameter silently succeed even when a tag name doesn't exist in Things. The URL scheme drops unknown tags with no error signal. Users lose tags without knowing.

### Root cause
The URL scheme itself — the fix must live in things-mcp as a pre-flight validation step.

### Implementation

**Step 1 — add `get_tag_names()` to `services/things_repo.py`**

```python
def get_tag_names() -> set[str]:
    """Return the set of all tag names currently in Things (case-sensitive)."""
    return {t["title"] for t in things.tags(**_kw())}
```

**Step 2 — add `validate_tags()` in `services/url_scheme.py`** (or a new `services/validators.py` if it fits better)

```python
def validate_tags(requested: list[str]) -> None:
    """Raise ValueError with actionable message if any tag doesn't exist in Things."""
    if not requested:
        return
    known = things_repo.get_tag_names()
    unknown = [t for t in requested if t not in known]
    if unknown:
        raise ValueError(
            f"Unknown tag(s): {unknown}. "
            f"Available tags: {sorted(known)}. "
            "Create the tag in Things first, then retry."
        )
```

**Step 3 — wire `validate_tags` into every write tool that accepts `tags`**

Call it **before** the URL is built. For `propose_*` tools, validate at propose time (not confirm time) so the error surfaces immediately.

Tools to update (grep `tags: list[str]` to find all call sites):

| Tool / handler | File |
|---|---|
| `add_inbox_todo`, `add_today_todo`, `add_anytime_todo`, `add_someday_todo` | `tools/write.py` |
| `propose_add_todo` → handler | `services/handlers/add_todo.py` |
| `propose_update_todo` → handler | `services/handlers/update_todo.py` |
| `propose_bulk_update` → handler | `services/handlers/bulk_update.py` |
| `propose_add_project` → handler | `services/handlers/add_project.py` |
| `propose_update_project` → handler | `services/handlers/update_project.py` |

Check each handler — some receive `tags` in a `fields` dict, some as a direct parameter. Validate only when `tags` is not `None` and not `[]` (clearing tags is valid; we don't validate an empty list).

**Step 4 — unit tests in `tests/test_tag_validation.py`** (new file)

- `validate_tags([])` → no-op (no exception).
- `validate_tags(["Errand"])` with `"Errand"` in mocked `get_tag_names()` → no-op.
- `validate_tags(["Errand", "FakeTag"])` with only `"Errand"` known → raises `ValueError` naming `FakeTag` and listing known tags.
- Integration: call `add_inbox_todo` handler (or tool) with `tags=["NonExistent"]` → `ValueError` raised before URL fires. Assert `subprocess.run` / `open` not called.
- Integration: `propose_bulk_update` with a real + fake tag → `ValueError` at propose time, no row in `pending_actions`.

---

## Fix B — Tags missing from `get_todo` / `get_project` read responses

### Root cause (pre-diagnosed — no investigation needed)

`things_repo.todo()` calls `things.get(uuid)` which **omits the `tags` field**.
`things_repo.get_todo()` (used internally by handlers for before-state snapshots) calls `things.tasks(uuid)` which **includes `tags`**.

The public `get_todo` tool calls `things_repo.todo()` → no tags in response.
The public `get_project` tool calls `things_repo.get_project_with_headings()` which internally calls `things_repo.project()` → `things.get(uuid)` → no project-level tags.

### Implementation

**Step 1 — fix `things_repo.todo()` to use `things.tasks()`**

Change the existing `todo()` function in `services/things_repo.py` from:

```python
def todo(todo_id: str) -> dict[str, Any] | None:
    return things.get(todo_id, **_kw())
```

to use the same pattern as `get_todo()` (which already handles the `ValueError` on non-UUID strings and the list-vs-dict return shape):

```python
def todo(todo_id: str) -> dict[str, Any] | None:
    """Return the full to-do row including tags.

    Uses things.tasks() (not things.get()) so the ``tags`` field is
    present in the response.
    """
    try:
        row = things.tasks(todo_id, **_kw())
    except ValueError:
        return None
    return row if isinstance(row, dict) else None
```

After this change `things_repo.get_todo()` (internal) and `things_repo.todo()` (public tool path) are functionally equivalent — consider whether `get_todo()` can now just call `todo()` for DRY-ness, or leave both as-is.

**Step 2 — fix `things_repo.project()` to use `things.tasks()`**

Change `project()` from:

```python
def project(project_id: str) -> dict[str, Any] | None:
    return things.get(project_id, **_kw())
```

to:

```python
def project(project_id: str) -> dict[str, Any] | None:
    """Return the full project row including tags."""
    row = things.tasks(project_id, type="project", **_kw())
    return row if isinstance(row, dict) else None
```

This matches the existing `get_project_row()` pattern. Check whether `get_project_row()` is now redundant and can delegate to `project()`.

**Step 3 — verify item-level tags in `get_project_with_headings`**

`get_project_with_headings` builds from `proj.get("items")` which comes from the project row returned by `project()`. After Step 2, the project row comes from `things.tasks()` — check whether the `items` sub-list within that row also carries per-item `tags` fields.

- If yes: tags on individual to-dos inside a project are already included — no further work.
- If no: per-item tag lookups would require either per-UUID `things.tasks()` calls (N+1) or a supplementary SQLite join (see §11 Fix B "Outcome B" in the spec). Assess the cost at implementation time; a note in the response doc is acceptable if the fix is out of scope for this session.

**Step 4 — unit tests in `tests/test_tag_read.py`** (new file)

- Mock `things.tasks(uuid)` to return a dict with `tags: ["Errand", "Home"]` → assert `things_repo.todo(uuid)` returns `{"tags": ["Errand", "Home"], ...}`.
- Mock returns task with no `tags` key → assert `things_repo.todo()` returns dict where `tags` is either `[]` or the key is absent (note which, so the test doc can tell testers what to expect).
- Mock `things.tasks(uuid, type="project")` with tags → assert `things_repo.project(uuid)` includes them.
- Call `get_todo` MCP tool path with a mocked repo → response includes `tags`.

---

## Finish line

1. `uv run pytest` — all green (note new count).
2. `uv run things-mcp --help` — clean exit.
3. Update `docs/things-mcp-V2-technical-architecture-and-implementation-plan.md` §0 status table: flip both Fix A and Fix B Build column to `✅ Done`.
4. Produce `tests/handoff-fixes-ab-testing.md` (already written — it lives at that path already).
5. Commit: `git add -p` (or name files explicitly), then push to `main`.

Suggested commit message:
```
Pre-release fixes A & B: tag pre-validation + tags in read responses
```

---

## Files touched (expected)

| File | Change |
|---|---|
| `services/things_repo.py` | `get_tag_names()` added; `todo()` and `project()` fixed to use `things.tasks()` |
| `services/url_scheme.py` (or new `services/validators.py`) | `validate_tags()` added |
| `tools/write.py` | `validate_tags()` called in all `add_*_todo` tools |
| `services/handlers/add_todo.py` | `validate_tags()` call |
| `services/handlers/update_todo.py` | `validate_tags()` call |
| `services/handlers/bulk_update.py` | `validate_tags()` call |
| `services/handlers/add_project.py` | `validate_tags()` call (if it accepts tags) |
| `services/handlers/update_project.py` | `validate_tags()` call (if it accepts tags) |
| `tests/test_tag_validation.py` | New — Fix A unit tests |
| `tests/test_tag_read.py` | New — Fix B unit tests |
| `docs/…-plan.md` | §0 status rows updated |
