# Bug handoff: heading name-resolution broken (items 108, 110, 112, 114)

Discovered during step 4b manual verification, 2026-05-25.

---

## Symptoms

`propose_update_heading` and `propose_delete_heading` fail at confirm time when `heading_id_or_name` is a **name string** (not a UUID):

```
Error: No such task uuid found: 'Design'
```

Propose succeeds (returns action_id). Confirm fails before any mutation. The "rename by UUID" and "delete by UUID" paths work correctly.

Affected items: **108, 110, 112, 114**.

---

## Root cause

`things.tasks(uuid)` in the things-py library raises `ValueError("No such task uuid found: '<arg>'")` when given any string that is not a valid Things UUID.

`things_repo.get_todo()` called this without a try/except:

```python
# BEFORE (things_repo.py)
def get_todo(uuid: str) -> dict[str, Any] | None:
    row = things.tasks(uuid, **_kw())
    return row if isinstance(row, dict) else None
```

When called with a name string like `'Design'`, `things.tasks` raised immediately — the `isinstance` guard was never reached, and the `ValueError` propagated up through `_resolve_heading_uuid` in both `update_heading.py` and `delete_heading.py`, bypassing the name-scanning fallback at line 178 of `update_heading.py`.

---

## Fix

Added a `try/except ValueError` in `things_repo.get_todo` so it returns `None` on invalid-UUID inputs, matching its declared `dict | None` return type. The name-scanning fallback then proceeds normally.

```python
# AFTER (things_repo.py)
def get_todo(uuid: str) -> dict[str, Any] | None:
    try:
        row = things.tasks(uuid, **_kw())
    except ValueError:
        return None
    return row if isinstance(row, dict) else None
```

**Applied in this session.** 225 tests still pass. The fix is in the working tree — **needs commit and server restart** before items 108/110/112/114 can be re-verified.

---

## Verification after fix + restart

Re-run in order:

1. **Item 108** — `propose_update_heading(project_id, heading_id_or_name='Design', new_name='UX')` → confirm → `__DESIGN__` in project becomes `__UX__`. Check `get_project` shows updated name.
2. **Item 110** — `propose_update_heading(project_id, heading_id_or_name='NonExistent', new_name='Foo')` → confirm → expect `ValueError: No heading named 'NonExistent' found in project ...`
3. **Item 112** — Complex setup:
   - Create project with native heading 'Planning' via `propose_add_project('4b-ambig', headings=['Planning'])`
   - Add dummy `propose_add_heading(project_id, 'Planning')`
   - `propose_update_heading(project_id, 'Planning', 'NewName')` → confirm → expect `ValueError` listing both candidates (native UUID + dummy UUID)
4. **Item 114** — `propose_delete_heading(project_id, heading_id_or_name='UX')` → confirm → `__UX__` soft-deleted.

---

## Related

- Same `get_todo` fix also covers a latent risk in `update_todo` and `delete_todo` handlers if they ever call `get_todo` with a name argument (they currently don't, but the fix makes the contract explicit).
- Bug A (deferred validation in `make_preview`) is a separate issue — see `V2-step-4b-verification-2026-05-25.md` § Bug A.
