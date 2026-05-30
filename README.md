# things-mcp

Local [Model Context Protocol](https://modelcontextprotocol.io) server for
[Cultured Code's Things 3](https://culturedcode.com/things/) on macOS. Lets any
MCP-capable agent (Claude Desktop, Claude Code, Codex, Cursor, …) read and
write your entire Things database — tasks, projects, headings, checklists, and
more.

> **V2 complete.** Reads are full-coverage. V2 full write parity has shipped,
> with propose/confirm + undo protecting all mutating operations.

## Requirements

- macOS with Things 3 installed and running
- Python 3.11+
- [`uv`](https://github.com/astral-sh/uv) (recommended) or `pip`
- Things URL scheme enabled: **Things → Settings → General → Enable Things URLs**

## Install

```bash
git clone <this repo> things-mcp
cd things-mcp
uv venv
uv sync
```

Sanity check:

```bash
uv run things-mcp --help    # FastMCP help, or stdio if no flags
```

## First-run setup

Read tools work immediately with no configuration. Steps 1–2 below are only
needed for mutating tools (any `propose_*` tool or direct write other than
`add_inbox_todo`).

1. Things → Settings → General → **Enable Things URLs** (toggle on if not already).
2. Click **Manage**, copy the token.
3. Add it to your MCP client's env block as `THINGS_AUTH_TOKEN`.
4. If you want delete and other advanced operations, also add
   `THINGS_MCP_ALLOW_APPLESCRIPT=1` to the same env block.
5. Restart the client.

Verify with: ask the agent *"call health()"* → `url_scheme_auth_token_set: true`.

> **macOS permission prompt:** the first time a delete or advanced operation
> runs, macOS will ask *"things-mcp wants to control Things 3 — Allow?"*.
> Click Allow. This prompt appears once and is not shown again.

## Tools

### Read (no auth needed)

| Tool | What it does |
| --- | --- |
| `list_inbox` | All to-dos in your Inbox |
| `list_today` | To-dos scheduled for Today |
| `list_upcoming` | Upcoming scheduled to-dos (default: next 7 days) |
| `list_anytime` | To-dos in the Anytime list |
| `list_someday` | To-dos in the Someday list |
| `list_logbook` | Recently completed to-dos (default: last 7 days) |
| `list_trash` | Items currently in the Things Trash |
| `get_areas` | All top-level Areas |
| `get_projects` | All projects, optionally filtered by Area |
| `get_project` | A single project with its to-dos and headings |
| `get_todo` | A single to-do including checklist items and tags |
| `get_tags` | All tags |
| `get_checklist_items` | Checklist items for a to-do, with completion state |
| `search` | Full-text search across titles and notes |

### Direct writes (no propose/confirm)

These execute immediately without a confirmation step. Require `THINGS_AUTH_TOKEN`
except `add_inbox_todo`. All except `add_inbox_todo` are undoable via `undo`.

| Tool | What it does |
| --- | --- |
| `add_inbox_todo` | Create a new to-do in the Inbox (no auth token needed) |
| `add_today_todo` | Create a new to-do scheduled for Today |
| `add_anytime_todo` | Create a new to-do in Anytime |
| `add_someday_todo` | Create a new to-do in Someday |
| `complete_todo` | Mark a to-do as done — moves it to the Logbook |

### Propose/confirm writes

All require `THINGS_AUTH_TOKEN` unless noted. Each `propose_*` call returns a
preview for the user to approve before anything is written. See
**Propose/confirm flow** below.

> **Complete vs Cancel vs Delete**
> - **Complete** — marks a task done. Moves to the Things **Logbook**.
> - **Cancel** — marks a task as not happening. Also moves to the **Logbook**.
> - **Delete** — moves a task or project to Things **Trash**. Trash
>   auto-empties after 30 days. Requires `THINGS_MCP_ALLOW_APPLESCRIPT=1`.
>
> Use Cancel when something won't be done but you want to keep a record.
> Use Delete when you want it gone.

**To-do ops**

| Tool | What it does |
| --- | --- |
| `propose_add_todo` | Add a to-do to any list or project |
| `propose_update_todo` | Edit a to-do's title, notes, dates, tags, or status |
| `propose_move_todo` | Move a to-do to a different list or project |
| `propose_cancel_todo` | Cancel a to-do — moves it to the Logbook |
| `propose_delete_todo`† | Delete a to-do — moves it to Things Trash |

**Project ops**

| Tool | What it does |
| --- | --- |
| `propose_add_project` | Create a new project, optionally with headings |
| `propose_update_project` | Edit a project's title, notes, dates, or tags |
| `propose_cancel_project` | Cancel a project — moves it to the Logbook |
| `propose_delete_project`† | Delete a project and all its tasks — moves to Trash |

**Heading ops** (dummy headings — see Architecture)

| Tool | What it does |
| --- | --- |
| `propose_add_heading` | Add a section heading to a project |
| `propose_update_heading` | Rename a heading |
| `propose_delete_heading` | Remove a heading (cancels the underlying task) |

**Checklist ops**

| Tool | What it does |
| --- | --- |
| `propose_append_checklist_items` | Add items to the end of a to-do's checklist |
| `propose_prepend_checklist_items` | Add items to the top of a to-do's checklist |
| `propose_replace_checklist` | Replace the entire checklist (always needs explicit confirm) |

**Bulk ops** (always require explicit confirm regardless of `THINGS_MCP_AUTO_CONFIRM`)

| Tool | What it does |
| --- | --- |
| `propose_bulk_complete` | Mark multiple to-dos done in one operation |
| `propose_bulk_cancel` | Cancel multiple to-dos in one operation |
| `propose_bulk_move` | Move multiple to-dos to a different list or project |
| `propose_bulk_update` | Edit fields across multiple to-dos at once |

**Advanced ops** (require `THINGS_MCP_ALLOW_APPLESCRIPT=1`)

Uses AppleScript for operations the Things URL scheme cannot perform.

| Tool | What it does |
| --- | --- |
| `propose_delete_todo`† | Delete a to-do — moves to Things Trash |
| `propose_delete_project`† | Delete a project — moves to Things Trash |

† Moves to Things Trash via AppleScript; requires `THINGS_MCP_ALLOW_APPLESCRIPT=1`.

### Propose/confirm controls

| Tool | What it does |
| --- | --- |
| `confirm_action` | Execute a pending proposed action |
| `cancel_action` | Discard a pending proposed action |
| `list_pending_actions` | Show all actions waiting for confirmation |

### Undo

| Tool | What it does |
| --- | --- |
| `undo` | Reverse the most recent action (or a specific one by ID) |

### Meta

| Tool | What it does |
| --- | --- |
| `health` | Server status: DB path, Things running, auth token set, AppleScript state |
| `recent_undo_log` | List of recent reversible actions |

## Propose/confirm flow

Most mutating tools use a two-phase pattern:

1. Call a `propose_*` tool. It returns a human-readable preview and an
   `action_id` — nothing is written yet.
2. Surface the preview to the user and wait for approval.
3. Call `confirm_action(action_id)` to execute.

**Skipping the confirm round-trip:** set `THINGS_MCP_AUTO_CONFIRM=1` and
`propose_*` tools execute immediately, returning a summary instead of a
preview. Destructive and bulk operations (`propose_delete_todo`,
`propose_delete_project`, `propose_delete_heading`, `propose_bulk_complete`,
`propose_bulk_cancel`, `propose_bulk_move`, `propose_bulk_update`,
`propose_replace_checklist`) always require an explicit `confirm_action()` call
regardless of this flag.

**Cancelling a pending action:** call `cancel_action(action_id)`, or simply
ignore it — pending actions expire after 5 minutes.

## Client config

The server speaks MCP over stdio. Point any client at
`uv --directory /absolute/path/to/things-mcp run things-mcp`.

### Claude Desktop — `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "things": {
      "command": "uv",
      "args": ["--directory", "/absolute/path/to/things-mcp", "run", "things-mcp"],
      "env": {
        "THINGS_AUTH_TOKEN": "paste-token-here",
        "THINGS_MCP_ALLOW_APPLESCRIPT": "1"
      }
    }
  }
}
```

### Claude Code — `~/.config/claude-code/mcp.json` (or `claude mcp add`)

```bash
claude mcp add things \
  -e THINGS_AUTH_TOKEN=paste-token-here \
  -e THINGS_MCP_ALLOW_APPLESCRIPT=1 \
  -- uv --directory /absolute/path/to/things-mcp run things-mcp
```

### Cursor — Settings → MCP → Add Server

Use the same command/args as Claude Desktop, and add an `env` block with `THINGS_AUTH_TOKEN` set to your token.

## Environment

| Var | Default | Purpose |
| --- | --- | --- |
| `THINGS_DB_PATH` | Things default | Override read DB location. |
| `THINGS_MCP_STATE_DIR` | `~/.things-mcp` | Where `state.db` lives. |
| `THINGS_MCP_CALLBACK_TIMEOUT` | `5` | Seconds to wait for URL-scheme write confirmation. |
| `THINGS_AUTH_TOKEN` | unset | Required for all mutating tools (`propose_*` and direct writes other than `add_inbox_todo`). Read tools and `add_inbox_todo` work without it. See First-run setup. |
| `THINGS_MCP_ALLOW_APPLESCRIPT` | unset | Set to `1` to enable AppleScript-backed operations: delete to Trash (`propose_delete_todo`, `propose_delete_project`) and certain advanced task management operations. Off by default — the first AppleScript call triggers a one-time macOS Automation permission prompt for Things 3. Set alongside `THINGS_AUTH_TOKEN`. |
| `THINGS_MCP_AUTO_CONFIRM` | unset | Set to `1` to skip the confirm round-trip for `propose_*` tools — they execute immediately and return a summary. Destructive and bulk operations always require explicit `confirm_action()` regardless. |

## Architecture

See `docs/things-mcp-V2-technical-architecture-and-implementation-plan.md` for
the full design. Short version:

- Reads go through `things.py` (a read-only SQLite wrapper) via
  `services/things_repo.py` — single swap-point if the schema moves.
- Writes go through the Things URL scheme. An ephemeral aiohttp listener on
  `127.0.0.1` captures the `x-callback-url` response and the new task's UUID.
- Local SQLite state lives at `~/.things-mcp/state.db` (`pending_actions`,
  `undo_log` — both scaffolded for V2).

## Status

V1 (read + Inbox-create) and V2 (full write parity) are complete. All
operations go through propose/confirm + undo. The tool surface covers to-dos,
projects, headings, checklists, and bulk operations. AppleScript-backed
operations (delete to Trash, advanced task management) require
`THINGS_MCP_ALLOW_APPLESCRIPT=1`. See
`docs/things-mcp-V2-technical-architecture-and-implementation-plan.md` §0 for
the detailed implementation history.
