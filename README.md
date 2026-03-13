# brain-mcp

MCP server for the Brain. Provides tools for navigating, searching, structuring, and updating notes.

## Setup

```bash
cd brain-mcp
uv sync
```

## Run

```bash
uv run python brain_mcp.py
```

The server uses stdio transport (default for local integrations).

## Configure in Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "brain": {
      "command": "uv",
      "args": ["run", "--directory", "/Users/aklingler/Documents/Projects/Obsidian/Brain/brain-mcp", "python", "brain_mcp.py"],
      "env": {
        "BRAIN_VAULT_PATH": "/Users/aklingler/Documents/Projects/Obsidian/Brain"
      }
    }
  }
}
```

## Configure in Claude Code

```bash
claude mcp add brain -- uv run --directory /Users/aklingler/Documents/Projects/Obsidian/Brain/brain-mcp python brain_mcp.py
```

Or add to `~/.claude.json`:

```json
{
  "mcpServers": {
    "brain": {
      "command": "uv",
      "args": ["run", "--directory", "/Users/aklingler/Documents/Projects/Obsidian/Brain/brain-mcp", "python", "brain_mcp.py"],
      "env": {
        "BRAIN_VAULT_PATH": "/Users/aklingler/Documents/Projects/Obsidian/Brain"
      }
    }
  }
}
```

## Tools

| Tool | Description |
|------|-------------|
| `brain_search_notes` | Full-text search across Brain notes with context snippets |
| `brain_list_notes` | List notes in a folder, filterable by frontmatter type |
| `brain_read_note` | Read a note by path or title |
| `brain_create_note` | Create a new note (defaults to inbox per workflow) |
| `brain_update_note` | Replace content of an existing note |
| `brain_move_note` | Move/promote a note between folders |
| `brain_find_backlinks` | Find all notes linking to a given note via wikilinks |
| `brain_get_structure` | Brain overview with folder stats and _Index |
| `brain_list_folders` | List subdirectories with note counts |

## Prompts

| Prompt | Description |
|--------|-------------|
| `vault_review` | Review inbox notes for promotion readiness |
| `kb_update` | Generate a KB Update note from a work session |
| `daily_capture` | Quick-capture a fleeting note |
| `project_status` | Status overview of all active projects |
| `find_related` | Map all Brain content related to a topic |

## Environment Variables

- `BRAIN_VAULT_PATH` — Absolute path to the Brain (defaults to `/Users/aklingler/Documents/Projects/Obsidian/Brain`)
