# Safe Things MCP

Local [Model Context Protocol](https://modelcontextprotocol.io) server for [Cultured Code's Things 3](https://culturedcode.com/things/) on macOS. Lets any MCP-capable agent (Claude Desktop, Claude Code, Cursor, Codex, and others) read and write your entire Things database -- tasks, projects, headings, checklists, tags, and more.

> **V2 complete.** Full read coverage plus full write parity: propose/confirm safety on every mutation, a complete undo system, bulk operations, and an AI-assisted tagging and sorting workflow.

---

## What sets this apart

Most Things MCP servers offer basic reads and direct URL-scheme writes. This one goes further in ways that matter when an AI agent has write access to your task list.

| Feature | this repo | [hald/things-mcp](https://github.com/hald/things-mcp) | [soycanopa/SupaThings-MCP](https://github.com/soycanopa/SupaThings-MCP) | [drjforrest/mcp-things3](https://github.com/drjforrest/mcp-things3) |
|---|:---:|:---:|:---:|:---:|
| Propose/confirm safety layer | yes | no | no | no |
| Full undo (including group undo) | yes | no | no | no |
| AI-assisted tagging + sort workflow | yes | no | no | no |
| Bulk operations (complete, cancel, move, update) | yes | no | no | no |
| Checklist management | yes | partial | no | no |
| Project heading management | yes | no | no | no |
| Reorder to-dos | yes | no | no | no |
| Delete to Trash (not just cancel) | yes | yes | partial | no |
| Claude Desktop extension as a signed app (macOS data permission sticks, no Full Disk Access) | yes | no | no | no |
| Total tools | 62 | ~25 | 37 | ~10 |

**Propose/confirm** -- every write previews what will change before anything is executed. You see what the agent is about to do and approve or reject it. Destructive and bulk operations can never be auto-confirmed.

**Undo** -- every confirmed action logs its inverse before mutating. Call `undo()` to reverse the last action. Call `undo_group(group_id)` to reverse an entire multi-step sort atomically in the correct reverse order.

**AI tagging** -- a full tagging and sorting workflow where the agent flags uncertain tasks rather than guessing. Ambiguous tasks get a `*Unclear*` tag instead of a potentially wrong destination. The flag persists until you resolve it.

---

## Requirements

- macOS 12 or later, with [Things 3 for Mac](https://culturedcode.com/things/mac/) installed and opened at least once
- [`uv`](https://docs.astral.sh/uv/)
- For the Claude Desktop extension: Xcode Command Line Tools (`xcode-select --install`) and Node.js (for `npx`)
- For writes: **Things > Settings > General > Enable Things URLs**

---

## Install

Choose the path for the app you use:

| Your app | How to install | Where you grant the macOS permission |
|---|---|---|
| **Claude Desktop** (Chat and Code tabs) | [Extension](#claude-desktop-extension), built on your Mac | **SafeThingsMCP** |
| **Claude Code CLI, Cursor, VS Code, Codex, other MCP clients** | [`uvx` config](#other-mcp-clients-uvx) | The app that launches the server (your terminal, editor, etc.) |

### Claude Desktop extension

```bash
git clone https://github.com/josh000111/safe-things-mcp
cd safe-things-mcp
./build_tools/build_mcpb.sh
```

The script freezes the server, wraps it in a small signed app called **SafeThingsMCP**, and writes `dist_mcpb/safe-things-mcp.mcpb`. The app is signed with a certificate the script creates on your Mac the first time it runs. The key never leaves your machine.

1. In Claude Desktop, open **Settings > Extensions** and drag in `dist_mcpb/safe-things-mcp.mcpb`. Paste your Things auth token when asked (see [First-run setup](#first-run-setup)).
2. Ask Claude *"What's in my Things inbox?"*. The first read fails with a message saying macOS is blocking access. That's expected: macOS never shows a popup for this permission.
3. Open **System Settings > Privacy & Security > Files & Folders**, find **SafeThingsMCP**, and turn on **Data shared by Things and affiliated apps**.
4. Ask again. It works from now on.

One install covers both the Chat and Code tabs. If you also add a manual config inside Claude Desktop, give it a different name: two servers with the same name collide, and only one of them answers.

**Updating:** `git pull`, re-run `./build_tools/build_mcpb.sh`, and drag the new file in. The permission carries over as long as you build on the same Mac, because macOS ties it to the app's ID and your Mac's signing certificate.

**Why build it yourself?** A ready-made download would need an Apple Developer ID and notarization to get past Gatekeeper. Building locally avoids that and keeps the signing key on your own Mac.

### Other MCP clients (uvx)

uv fetches, builds and runs the server straight from this repo:

```json
{
  "mcpServers": {
    "safe-things-mcp": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/josh000111/safe-things-mcp", "safe-things-mcp"],
      "env": {
        "THINGS_AUTH_TOKEN": "paste-token-here",
        "SAFE_THINGS_MCP_ALLOW_APPLESCRIPT": "1"
      }
    }
  }
}
```

Claude Code CLI:

```bash
claude mcp add safe-things-mcp -e THINGS_AUTH_TOKEN=paste-token-here -e SAFE_THINGS_MCP_ALLOW_APPLESCRIPT=1 -- uvx --from git+https://github.com/josh000111/safe-things-mcp safe-things-mcp
```

Add `--refresh` right after `uvx` to pull the latest code on every launch (costs a few seconds at startup).

**Permission:** with this setup macOS gives the Things-data permission to the app that launched the server, such as Terminal, iTerm, Cursor or VS Code. After the first (failed) read, turn on **Data shared by Things and affiliated apps** under that app in **System Settings > Privacy & Security > Files & Folders**. Note that the app then has access to Things data for everything it runs, which is one reason to prefer the extension on Claude Desktop. (Tested with Claude Desktop's Code tab, where the entry is called "claude". Other apps follow the same macOS rule but haven't each been tested.)

<details>
<summary><strong>Always-on agent apps (Claude Duet, ChatGPT Dots, Meta Muse, xAI Grok Bot) -- not supported</strong></summary>

These run on their own remote cloud VM, not on your Mac, and none of them currently supports attaching a local stdio MCP server -- the only bridge any of them documents to your own machine is GUI/computer-use screen automation, not the MCP protocol safe-things-mcp uses. OpenAI states this explicitly for Dots ("Can I connect to a local MCP server? Not directly."); Anthropic scopes local MCP/plugin support to Claude Desktop (Chat tab), Claude Code, and Cowork sessions run on your own machine -- Duet isn't in that list. "Your connectors carry over" claims for these products cover remote/cloud connectors already on your account, not local servers like this one. Use one of the install paths above instead.

</details>

---

## First-run setup

Reads only need the macOS permission from [Install](#install). Writes (any `propose_*` tool, or a direct write other than `add_inbox_todo`) also need the Things auth token:

1. Things > Settings > General > **Enable Things URLs** (toggle on if not already).
2. Click **Manage** and copy the auth token.
3. Paste it into the extension's install form, or set it as `THINGS_AUTH_TOKEN` in your client's `env` block (then restart the client).
4. For delete, reorder and AI tagging, turn on **Allow AppleScript operations** in the extension's settings, or set `SAFE_THINGS_MCP_ALLOW_APPLESCRIPT=1`.
5. Pre-create the AI flag tags (once, idempotent): ask the agent to call `ensure_ai_tags()`. This creates the `AI` parent tag and the five abstain flags (`*Unclear*`, `*Ambiguous Home*`, etc.) if any are missing.

Verify: ask the agent to *"call health()"*. `things_db_access` should be `"ok"` and `url_scheme_auth_token_set` should be `true`.

<details>
<summary><strong>macOS permissions -- what to expect</strong></summary>

**1. Things data: "Data shared by Things and affiliated apps"**

The server reads the Things database from Things' protected App Group folder. Recent macOS versions guard that folder with their own permission (behavior below confirmed on macOS 27). It is *not* Full Disk Access, and you don't need Full Disk Access.

- **No popup.** For servers launched by an MCP client, macOS silently blocks the first read and adds an entry to **System Settings > Privacy & Security > Files & Folders**. The server replies with a message pointing you there. Turn on **Data shared by Things and affiliated apps** for that entry. No restart is needed.
- **Which entry.** Claude Desktop launches each extension as its own process, so the permission belongs to the extension: **SafeThingsMCP**. Other clients start the server inside their own app, so the permission belongs to that app (Terminal, Cursor, "claude", ...).
- **Why an app.** macOS only keeps this switch on for a signed app with a stable ID. For a plain command-line program, the switch flips straight back off. That's why the extension ships the server inside a small signed app instead of as a bare program.

Troubleshooting:

- *The switch flips back off:* you're running an extension built before v0.2.0, which shipped a bare program. Rebuild with `./build_tools/build_mcpb.sh` and reinstall. You can then remove the old `safe-things-mcp` entry: select it in Files & Folders and click **–**.
- *The switch is on but reads are still blocked:* the app was rebuilt with a different certificate (for example on another Mac, or after deleting both `build_tools/selfsign_*` and the `safe-things-mcp-selfsigned` certificate in your keychain). Select **SafeThingsMCP** in Files & Folders and click **–** to remove the stale entry, use the server once so it reappears, then turn the switch on again.
- `health()` reports the current state in `things_db_access`.

**2. Automation: "... wants access to control Things 3"**

Appears the first time an AppleScript-backed operation runs (requires `SAFE_THINGS_MCP_ALLOW_APPLESCRIPT=1`). It names the same app as above. Click **Allow** once; this grant persists.

</details>

---

## Tools

### Read (no auth needed)

| Tool | What it does |
|---|---|
| `list_inbox` | All to-dos in your Inbox |
| `list_today` | To-dos scheduled for Today |
| `list_upcoming` | Upcoming scheduled to-dos (default: next 7 days) |
| `list_anytime` | To-dos in the Anytime list |
| `list_someday` | To-dos in the Someday list |
| `list_logbook` | Recently completed to-dos (default: last 7 days) |
| `list_trash` | Items currently in Things Trash |
| `get_areas` | All top-level Areas |
| `get_projects` | All projects, optionally filtered by Area |
| `get_project` | A single project with its to-dos and headings |
| `get_todo` | A single to-do including checklist items and tags |
| `get_tags` | All tags |
| `get_checklist_items` | Checklist items for a to-do, with completion state |
| `search` | Full-text search across titles and notes |
| `list_ai_tags` | All AI-managed tags with tasks and proposed routing destinations |

### Direct writes

These execute immediately without a confirmation step. Require `THINGS_AUTH_TOKEN` except `add_inbox_todo`. All except `add_inbox_todo` are undoable via `undo`.

| Tool | What it does |
|---|---|
| `add_inbox_todo` | Create a to-do in the Inbox (no auth token needed) |
| `add_today_todo` | Create a to-do scheduled for Today |
| `add_anytime_todo` | Create a to-do in Anytime |
| `add_someday_todo` | Create a to-do in Someday |
| `complete_todo` | Mark a to-do done, moves it to the Logbook |

### Propose/confirm writes

Each `propose_*` call returns a preview for you to approve before anything is written. Requires `THINGS_AUTH_TOKEN`. See [Propose/confirm flow](#proposeconfirm-flow) below.

> **Complete vs Cancel vs Delete**
>
> - **Complete** -- marks a task done. Moves to the Things Logbook.
> - **Cancel** -- marks a task as not happening. Also moves to the Logbook. Use when something won't be done but you want to keep a record.
> - **Delete** -- moves a task or project to Things Trash. Trash auto-empties after 30 days. Use when you want it gone. Requires `SAFE_THINGS_MCP_ALLOW_APPLESCRIPT=1`.

**To-do operations**

| Tool | What it does |
|---|---|
| `propose_add_todo` | Add a to-do to any list or project |
| `propose_update_todo` | Edit a to-do's title, notes, dates, tags, or status |
| `propose_move_todo` | Move a to-do to a different list or project |
| `propose_cancel_todo` | Cancel a to-do, moves it to the Logbook |
| `propose_delete_todo` † | Delete a to-do, moves to Things Trash |

**Project operations**

| Tool | What it does |
|---|---|
| `propose_add_project` | Create a new project, optionally with headings |
| `propose_update_project` | Edit a project's title, notes, dates, or tags |
| `propose_cancel_project` | Cancel a project, moves it to the Logbook |
| `propose_delete_project` † | Delete a project and all its tasks, moves to Trash |

**Heading operations**

| Tool | What it does |
|---|---|
| `propose_add_heading` | Add a section heading to a project |
| `propose_update_heading` | Rename a heading |
| `propose_delete_heading` | Remove a heading |

**Checklist operations**

| Tool | What it does |
|---|---|
| `propose_append_checklist_items` | Add items to the end of a to-do's checklist |
| `propose_prepend_checklist_items` | Add items to the top of a to-do's checklist |
| `propose_replace_checklist` | Replace the entire checklist (always requires explicit confirm) |

**Reorder operations**

| Tool | What it does |
|---|---|
| `propose_reorder_todos` † | Reorder to-dos within a list or project |

**Bulk operations** (always require explicit confirm, regardless of `SAFE_THINGS_MCP_AUTO_CONFIRM`)

| Tool | What it does |
|---|---|
| `propose_bulk_add_todo` | Add multiple to-dos to a single destination in one operation |
| `propose_bulk_complete` | Mark multiple to-dos done in one operation |
| `propose_bulk_cancel` | Cancel multiple to-dos in one operation |
| `propose_bulk_delete_todo` † | Delete multiple to-dos, moves all to Things Trash |
| `propose_bulk_move` | Move multiple to-dos to a different list or project |
| `propose_bulk_update` | Edit fields across multiple to-dos at once |

**Bulk heading operations** (always require explicit confirm)

| Tool | What it does |
|---|---|
| `propose_bulk_delete_heading` | Soft-delete multiple dummy headings from a project in one operation |

**AI tagging operations** (require `SAFE_THINGS_MCP_ALLOW_APPLESCRIPT=1` -- see [AI Tagging](#ai-tagging))

| Tool | What it does |
|---|---|
| `propose_create_ai_tag` | Create an AI-managed tag under the `AI` parent |
| `propose_apply_ai_tags` | Apply AI tags to tasks (merge model -- never clobbers user tags) |
| `propose_cleanup_ai_tags` | Strip transient routing tags after a confirmed sort |
| `propose_manage_ai_tag` | Rename or reparent an AI tag |
| `propose_delete_ai_tag` †† | Delete an AI tag, removes it from all tasks |
| `undo_group` | Reverse an entire multi-step sort atomically in correct reverse order |

† Requires `SAFE_THINGS_MCP_ALLOW_APPLESCRIPT=1`. Uses AppleScript because the Things URL scheme has no delete operation.

†† Always requires explicit `confirm_action()` -- never auto-confirmed.

### Propose/confirm controls

| Tool | What it does |
|---|---|
| `confirm_action` | Execute a pending proposed action |
| `cancel_action` | Discard a pending proposed action |
| `list_pending_actions` | Show all actions waiting for confirmation |

### Undo

| Tool | What it does |
|---|---|
| `undo` | Reverse the most recent action, or a specific one by ID |
| `undo_group` | Reverse all actions in a group in correct reverse order |

### Meta

| Tool | What it does |
|---|---|
| `health` | Server status: DB path, Things running, auth token set, AppleScript state |
| `recent_undo_log` | List of recent reversible actions |

---

## Propose/confirm flow

Most write tools use a two-phase pattern:

1. Call a `propose_*` tool. It returns a human-readable preview and an `action_id`. Nothing is written yet.
2. The agent surfaces the preview to you and waits for approval.
3. Call `confirm_action(action_id)` to execute, or `cancel_action(action_id)` to discard.

Pending actions expire after 5 minutes.

**Skipping the confirm round-trip:** set `SAFE_THINGS_MCP_AUTO_CONFIRM=1` in the env block. `propose_*` tools will execute immediately and return a summary instead of a preview. The following operations always require an explicit `confirm_action()` regardless of this flag:

- `propose_delete_project` — cascades to all tasks inside the project
- `propose_bulk_complete`, `propose_bulk_cancel`, `propose_bulk_move`, `propose_bulk_update`
- `propose_bulk_delete_todo`, `propose_bulk_delete_heading` — multi-target deletes
- `propose_replace_checklist`
- `propose_delete_ai_tag`
- `propose_move_under_ai_heading`

`propose_delete_todo` and `propose_delete_heading` **do** respect `AUTO_CONFIRM=1` — single-item deletes go to Things Trash and are reversible via `undo()`, so explicit confirmation is not forced when the user has already named the item. `propose_bulk_add_todo` also respects `AUTO_CONFIRM=1` (additive, low risk).

---

## Reducing permission prompts

Two **separate** prompt systems sit in front of the write tools. They are unrelated and have different fixes — most friction comes from not realising they are distinct:

**1. Your MCP client's per-tool approval** — *"Allow Claude to use Propose add project?"*. This comes from the client (Claude Desktop, Claude Code, Cursor…), not from safe-things-mcp. Every MCP tool is gated until you approve it.

- **Claude Code / Cursor / VS Code** — allow-list the whole server once. In Claude Code, add to `.claude/settings.json`:
  ```json
  { "permissions": { "allow": ["mcp__things__*"] } }
  ```
  (replace `things` with the server name in your config). Or enable accept-all / auto-accept mode for the session.
- **Claude Desktop** — click **Allow always** the first time each tool runs (one approval per tool, then it stops). Desktop has no wildcard allow-list today, so `AUTO_CONFIRM` below matters more here because it reduces the *number* of distinct tools the agent has to call.

**2. safe-things-mcp's own confirm step** — the `propose_*` → `confirm_action` round-trip. Set `SAFE_THINGS_MCP_AUTO_CONFIRM=1` so `propose_*` tools execute immediately (see [Propose/confirm flow](#proposeconfirm-flow)). The genuinely destructive bulk/delete operations listed above still require an explicit `confirm_action()` regardless — that is the intended safety floor.

**For the smoothest experience, combine both:** allow-list the server (or turn on auto-accept) **and** set `SAFE_THINGS_MCP_AUTO_CONFIRM=1`. You then run friction-free for everyday adds/updates/moves while keeping a hard confirmation on the dangerous bulk operations.

> The macOS **"Data shared by Things and affiliated apps"** switch is a *third*, OS-level permission -- see [macOS permissions](#first-run-setup) above. Neither auto-accept nor `AUTO_CONFIRM` affects it; you turn it on once in System Settings.

---

## AI Tagging

safe-things-mcp includes a tagging system designed for AI agents sorting large task lists. The core principle is **abstain-and-flag**: when the agent's confidence falls below roughly 90%, it applies a persistent flag tag rather than guessing at a destination. One ambiguous task never blocks the rest of the batch.

All AI tagging tools require `SAFE_THINGS_MCP_ALLOW_APPLESCRIPT=1`. The first call triggers a one-time macOS Automation permission prompt -- click Allow once.

### How AI tags look in Things

AI-created tags are **asterisk-wrapped** (`*Do Taxes*`, `*Errand*`) and grouped under an `AI` parent folder in Things' Tags window. This keeps them visually distinct from your own tags.

```
Tags window:
  AI/
    *Ambiguous Home*
    *Do Taxes*
    *Errand*
    *Unclear*
  (your own tags)
  Home
  Work
```

### Flag tag vocabulary

When the agent cannot confidently sort a task, it applies one of these persistent tags instead of guessing:

| Flag tag | When it is applied |
|---|---|
| `*Unclear*` | Generic "I don't know" -- review this task |
| `*Duplicate?*` | Looks like a near-duplicate; needs human dedup |
| `*No Time Signal*` | Scheduling was requested but no date/time evidence exists |
| `*Ambiguous Home*` | Multiple equally-plausible projects or areas |
| `*Review Delete?*` | Bulk-delete criteria are uncertain; tagged rather than deleted |

Flag tags **persist** until you resolve them. They are never automatically removed by sort cleanup.

### Sorting workflow

1. **Tag** -- `propose_apply_ai_tags` applies a routing tag to each task encoding the proposed destination. Ambiguous tasks get `*Unclear*` instead. Tags are merged with any existing tags -- existing user tags are never touched.
2. **Review** -- `list_ai_tags` shows each proposed routing destination. Adjust before committing.
3. **Move** -- `propose_bulk_move` moves tasks to their destinations.
4. **Clean** -- `propose_cleanup_ai_tags` strips the transient routing tags. Flag tags like `*Unclear*` are never removed.

To undo the entire sort in one command: `undo_group(group_id)` where `group_id` is the shared ID returned by `propose_apply_ai_tags`. This reverses all three steps atomically in the correct reverse order, even if other actions happened in between.

<details>
<summary><strong>Duplicate list names and disambiguation</strong></summary>

Every Things project, area, and task has a stable unique UUID. The routing system records destination UUIDs, not names -- two lists both named "Shopping" are never confused.

During the review step, any destination with a duplicate name is shown with disambiguating context:

- A project inside an Area: *"Shopping -- in Area 'Home'"*
- A project not inside any Area: *"Shopping -- a standalone project (not in any Area)"*

This wording appears in `list_ai_tags` output and in proposal previews so you can confirm the right destination before moving anything.

</details>

<details>
<summary><strong>Existing-list matching</strong></summary>

When asked to sort tasks into projects or areas, the agent reads your existing structure first (`get_projects`, `get_areas`) and proposes the best existing destination per task. A new list is only proposed where nothing in your current structure fits, and new lists are only created with explicit approval.

Default bias: reuse existing lists. Avoid creating clutter.

</details>

<details>
<summary><strong>Guidance document</strong></summary>

The agent-side reference ships inside the server (its MCP instructions and the `help_docs()` tool), so every client gets it automatically. It covers:

- The 90% soft confidence anchor (criteria-based, not a numeric gate)
- Abstain criteria checklist
- Naming convention: 2-3 words, actionable imperative, Title Case, asterisk-wrapped, under `AI`
- Partial-execution pattern (act on the confident set, flag the rest, never block)
- The full sort workflow and undo procedure
- Disambiguation terminology

</details>

---

## Undo

Every confirmed write -- direct writes and confirmed `propose_*` actions alike -- records its inverse state to `undo_log` before executing the mutation. If something goes wrong or you change your mind, undo is always available. You can also just say **"undo that"** — the agent knows what to call.

```
# Reverse the most recent action
undo()

# Reverse a specific action by ID
undo(undo_id="abc123")

# Reverse an entire multi-step sort atomically (correct LIFO order)
undo_group(group_id="sort-xyz")
```

`undo_group` is designed for the AI sorting workflow: a full sort produces three undo_log entries (`apply_ai_tags`, `bulk_move`, `cleanup_ai_tags`) that share a `group_id`. Passing that ID to `undo_group` reverses all three in the correct order, regardless of other actions that may have happened since.

**Retention:** by default, undo entries are kept for 7 days or up to 200 rows, whichever limit is hit first. Both limits are configurable via environment variables.

---

## Routines / scheduled workflows

safe-things-mcp is a stdio MCP server — it can't self-schedule. Routines are **user-run prompt recipes**: you send a prompt, the agent reads and sorts your tasks, you confirm, done. For unattended scheduling use OS-level tools (launchd, cron) or Claude Code's `/schedule` command to fire the same prompts automatically.

**Example prompts to run as routines:**

- **Process Inbox** — *"Sort everything in my Inbox: route tasks to the right projects or areas, flag anything ambiguous, and show me a summary before moving anything."*
- **Clear Today** — *"Review my Today list: complete anything that's done, move anything I can't realistically finish today back to Anytime, and flag anything that needs rescheduling."*
- **Organise Projects** — *"Look at all my active projects. Identify any that have no open tasks (stalled) or that have tasks that belong somewhere else, and propose moves."*

Tip: after any routine finishes, you can undo the entire run with a single `undo_group(group_id)` call — the agent reports the `group_id` at the end of every sort.

---

## Environment

| Variable | Default | Purpose |
|---|---|---|
| `THINGS_DB_PATH` | Things default | Override the read DB location |
| `SAFE_THINGS_MCP_STATE_DIR` | `~/.safe-things-mcp` | Directory where `state.db` lives |
| `SAFE_THINGS_MCP_CALLBACK_TIMEOUT` | `5` | Seconds to wait for URL-scheme write confirmation |
| `THINGS_AUTH_TOKEN` | unset | Required for all mutating tools. Read tools and `add_inbox_todo` work without it. |
| `SAFE_THINGS_MCP_ALLOW_APPLESCRIPT` | unset | Set to `1` to enable: delete to Trash, reorder todos, and all AI tagging operations. The first call triggers a one-time macOS Automation permission prompt. |
| `SAFE_THINGS_MCP_AI_TAG_PARENT` | `AI` | Name of the parent tag that groups all AI-created tags in the Things Tags window |
| `SAFE_THINGS_MCP_UNDO_MAX_ROWS` | `200` | Maximum number of undo entries to retain |
| `SAFE_THINGS_MCP_UNDO_MAX_AGE_DAYS` | `7` | Maximum age in days of undo entries. Pruning triggers when either limit is hit first. |
| `SAFE_THINGS_MCP_AUTO_CONFIRM` | unset | Set to `1` to skip the confirm round-trip for `propose_*` tools. Destructive and bulk operations always require explicit `confirm_action()` regardless. |

---

## Architecture

<details>
<summary><strong>How it works</strong></summary>

**Reads** go through `things.py` (a read-only SQLite wrapper maintained by the `things.py` project) via `services/things_repo.py`. This is a single swap-point if the Things schema changes.

**Writes** go through the Things URL scheme. An ephemeral aiohttp HTTP listener on `127.0.0.1` captures the `x-callback-url` response and the new task's UUID after each write.

**State** is kept in a local SQLite database at `~/.safe-things-mcp/state.db`. Three tables:
- `pending_actions` -- proposed actions awaiting confirmation (expire after 5 minutes)
- `undo_log` -- reversible action history with before/after state snapshots and `group_id` for atomic multi-step undo
- `ai_tag_routing` -- maps AI routing tags to their proposed destination UUIDs and transient/persistent status

**AppleScript** operations (delete to Trash, reorder, all AI tagging) are handled by `services/applescript.py`, which provides hardened string escaping, the `SAFE_THINGS_MCP_ALLOW_APPLESCRIPT` gate, and an auth probe. The Things URL scheme has no delete or tag-create operations, so AppleScript is the only channel for these.

**AI tag invariants** are enforced server-side: the asterisk wrapper (`*…*`) and parent-tag assignment are structural rules validated in the handler code, not relying on the agent to remember them. The agent is responsible for confidence judgments; the server is responsible for structural correctness.

</details>

---

## Status

V1 (read + Inbox-create) and V2 (full write parity) are complete, including AI-assisted tagging and sorting with abstain-and-flag safety. All mutating operations go through propose/confirm with full undo support.

**Tool surface covers:**
- All Things lists (Inbox, Today, Upcoming, Anytime, Someday, Logbook, Trash)
- Areas, projects, headings, to-dos, checklist items, tags
- Bulk operations (complete, cancel, move, update)
- AI tagging with abstain-and-flag, routing workflow, group undo
- Meta: health check, undo log

**AppleScript-backed operations** (require `SAFE_THINGS_MCP_ALLOW_APPLESCRIPT=1`): delete to Trash, reorder, and all AI tagging.

For implementation details, see [Architecture](#architecture) above.

---

## License

MIT -- see [LICENSE](LICENSE).
