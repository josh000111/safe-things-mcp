# things-mcp

Local [Model Context Protocol](https://modelcontextprotocol.io) server for
[Cultured Code's Things 3](https://culturedcode.com/things/) on macOS. Lets any
MCP-capable agent (Claude Desktop, Claude Code, Codex, Cursor, …) read your
entire Things database and create to-dos in your Inbox.

> **V1 scope.** Reads are full-coverage. Writes are **quarantined to the
> Inbox** — the agent cannot touch your existing projects, areas, or tasks
> until V2 ships full propose/confirm + undo.

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

Read-only tools work immediately. Any mutating tool (update / move / delete / project ops) needs an auth token:

1. Things → Settings → General → **Enable Things URLs** (toggle on if not already).
2. Click **Manage**, copy the token.
3. Add it to your MCP client's env block as `THINGS_AUTH_TOKEN`.
4. Restart the client.

Verify with: ask the agent *"call health()"* → `url_scheme_auth_token_set: true`.

## Tools (V1)

**Read** — `list_inbox`, `list_today`, `list_upcoming`, `list_anytime`,
`list_someday`, `list_logbook`, `list_trash`, `get_areas`, `get_projects`,
`get_project`, `get_todo`, `get_tags`, `search`.

**Write** — `add_inbox_todo(title, notes?, when?, deadline?, tags?, checklist?)`.
List is hard-coded to Inbox.

**Meta** — `health`, `recent_undo_log`.

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
        "THINGS_AUTH_TOKEN": "paste-token-here"
      }
    }
  }
}
```

### Claude Code — `~/.config/claude-code/mcp.json` (or `claude mcp add`)

```bash
claude mcp add things -e THINGS_AUTH_TOKEN=paste-token-here -- uv --directory /absolute/path/to/things-mcp run things-mcp
```

### Cursor — Settings → MCP → Add Server

Use the same command/args as Claude Desktop, and add an `env` block with `THINGS_AUTH_TOKEN` set to your token.

## Environment

| Var | Default | Purpose |
| --- | --- | --- |
| `THINGS_DB_PATH` | Things default path | Override read DB location. |
| `THINGS_MCP_STATE_DIR` | `~/.things-mcp` | Where `state.db` lives. |
| `THINGS_MCP_CALLBACK_TIMEOUT` | `5` | Seconds to wait for the URL-scheme callback. |
| `THINGS_AUTH_TOKEN` | unset | Required for every mutating tool (update / move / delete / project ops / bulk_*). Read tools and add_inbox_todo / add_today_todo / add_anytime_todo / add_someday_todo don't need it. See First-run setup above. |

## Architecture

See `plans/` (private) for the full design. Short version:

- Reads go through `things.py` (a read-only SQLite wrapper) via
  `services/things_repo.py` — single swap-point if the schema moves.
- Writes go through the Things URL scheme. An ephemeral aiohttp listener on
  `127.0.0.1` captures the `x-callback-url` response and the new task's UUID.
- Local SQLite state lives at `~/.things-mcp/state.db` (`pending_actions`,
  `undo_log` — both scaffolded for V2).

## Status

V1 done = read + Inbox-create end-to-end. V2 chunks A–E have shipped behind
propose/confirm + undo: direct shortcuts (`add_today/anytime/someday_todo`,
`complete_todo`), `propose_update_todo`, `propose_move_todo`,
`propose_delete_todo`, `propose_add_project`, `propose_update_project`, and the
`propose_bulk_*` family. Chunks D and E are awaiting Round-4 manual
verification on the Test user. Remaining: opt-in AppleScript layer for
hard-delete / reorder and native heading support. See
`docs/things-mcp-V2-technical-architecture-and-implementation-plan.md` §0 for
the authoritative status table.
