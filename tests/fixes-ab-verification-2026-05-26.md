# Pre-release fixes A & B — manual verification (Round 6)

Date: 2026-05-26  
Tester: Test user (macOS `Test` account)  
Commit: `78a5f32` on `main`  
Automated suite: 245 tests, all green.

---

## Pre-flight

| Check | Result |
|-------|--------|
| `whoami` → `Test` | ✅ |
| Commit `78a5f32` present in `git log` | ✅ |
| `uv run pytest -q` → 245 passed | ✅ (1 cache-write warning, benign) |
| `uv run things-mcp --help` | ✅ |
| `health()` → `things_app_running=true`, `state_db_exists=true`, `url_scheme_auth_token_set=true` | ✅ |
| Tags available in Test account | ✅ (Errand, Home, Office, Important, Pending) |
| `list_pending_actions()` empty at start | ✅ |

---

## Results

### Fix A — Tag pre-validation

| # | What | Result | Notes |
|---|------|--------|-------|
| 123 | Unknown tag rejected (`add_inbox_todo`, tag=`NonExistentTag999`) | ✅ | `ValueError: Unknown tag(s): ['NonExistentTag999']. Available tags: ['Errand', 'Home', 'Important', 'Office', 'Pending']. Create the tag in Things first, then retry.` Nothing created in Inbox. |
| 124 | Known tag accepted (`add_inbox_todo`, tag=`Errand`) | ✅ | Task created in Inbox (UUID `4bBgVeGsyR36GtGbpj1uBV`). `get_todo` confirmed `"tags": ["Errand"]`. |
| 125 | Propose-time rejection (`propose_update_todo`, tag=`GhostTag`) | ✅ | `ValueError` raised before enqueue. `list_pending_actions()` still empty. |
| 126 | `propose_bulk_update` with mixed tags (`Errand` + `GhostTag`) | ✅ | `ValueError: Unknown tag(s): ['GhostTag']`. No pending action created. |

**Fix A verdict: PASS** — all four items green.

---

### Fix B — Tags in read responses

| # | What | Result | Notes |
|---|------|--------|-------|
| 127 | `get_todo` returns `tags` for tagged task | ✅ | UUID `4bBgVeGsyR36GtGbpj1uBV` (tagged `Errand`): response includes `"tags": ["Errand"]`. |
| 128 | `get_todo` returns `tags: []` for untagged task | ❌ | UUID `XsMjRWd8m1BWLNDGXarynv` (no tags): `tags` key **absent** from response (not `"tags": []`). |
| 129 | `get_project` returns `tags` for tagged project | ✅ | UUID `Dj2A8GQVJjAkXBMBXh2saH` (tagged `Important`): response includes `"tags": ["Important"]`. |
| 130 | `get_project` returns `tags: []` for untagged project | ❌ | UUID `QDreuLWLoDsQo9KbhViYBE` (`4b-empty`, no tags): `tags` key **absent** from response (not `"tags": []`). |

**Fix B verdict: PARTIAL PASS** — tagged paths work (127 ✅, 129 ✅); untagged paths omit the key entirely (128 ❌, 130 ❌).

---

## Root cause (items 128, 130)

`things.tasks()` from the `things-py` library omits the `tags` key when an item has no tags — it does not return `"tags": []`. The `todo()` and `project()` functions in `src/things_mcp/services/things_repo.py` return the raw dict without normalising the missing key to an empty list.

**Fix needed** (both functions, same pattern):

```python
# things_repo.py — todo() and project()
# After: row = things.tasks(...)
row.setdefault("tags", [])   # normalise: absent → []
return row if isinstance(row, dict) else None
```

See `tests/bug-handoff-fix-b-untagged-key-absent.md` for full handoff.

---

## Load-bearing items check

| Item | Required | Result |
|------|----------|--------|
| 123 | ✅ required | ✅ |
| 124 | ✅ required | ✅ |
| 127 | ✅ required | ✅ |

All three load-bearing items pass.

---

## Round 6 closure status

- [x] Items 123–130 walked and recorded
- [x] Load-bearing items 123, 124, 127 all ✅
- [ ] Fix B fully verified — **blocked** on items 128, 130 (bug handoff filed)
- [ ] Results doc committed and pushed
- [ ] Architecture plan §0 updated

**Fix A** is ready to mark verified.  
**Fix B** needs a one-line patch before it can be marked verified. The fix is trivial; see bug handoff.
