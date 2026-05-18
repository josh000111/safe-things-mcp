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
      "args": ["--directory", "/absolute/path/to/things-mcp", "run", "things-mcp"]
    }
  }
}
```

### Claude Code — `~/.config/claude-code/mcp.json` (or `claude mcp add`)

```bash
claude mcp add things -- uv --directory /absolute/path/to/things-mcp run things-mcp
```

### Cursor — Settings → MCP → Add Server

Use the same command/args as Claude Desktop.

## Environment

| Var | Default | Purpose |
| --- | --- | --- |
| `THINGS_DB_PATH` | Things default path | Override read DB location. |
| `THINGS_MCP_STATE_DIR` | `~/.things-mcp` | Where `state.db` lives. |
| `THINGS_MCP_CALLBACK_TIMEOUT` | `5` | Seconds to wait for the URL-scheme callback. |
| `THINGS_AUTH_TOKEN` | unset | V2 only (mutating updates). |

## Architecture

See `plans/` (private) for the full design. Short version:

- Reads go through `things.py` (a read-only SQLite wrapper) via
  `services/things_repo.py` — single swap-point if the schema moves.
- Writes go through the Things URL scheme. An ephemeral aiohttp listener on
  `127.0.0.1` captures the `x-callback-url` response and the new task's UUID.
- Local SQLite state lives at `~/.things-mcp/state.db` (`pending_actions`,
  `undo_log` — both scaffolded for V2).

## Status

V1 done = read + Inbox-create end-to-end. V2 = full-parity writes behind a
two-phase propose/confirm gate with an undo log.
