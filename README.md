# brain-mcp

MCP server for the Brain Obsidian knowledge base. Provides tools for navigating, searching, creating, and updating notes.

## Installation

```bash
uv sync
```

## Usage

### Run directly

```bash
uv run brain-mcp
```

### Configure in Claude Code

```bash
claude mcp add brain -- uv run --directory /path/to/brain-mcp brain-mcp
```

Or add to `~/.claude.json`:

```json
{
  "mcpServers": {
    "brain": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/brain-mcp", "brain-mcp"],
      "env": {
        "BRAIN_VAULT_PATH": "/path/to/your/obsidian/vault"
      }
    }
  }
}
```

### Configure in Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "brain": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/brain-mcp", "brain-mcp"],
      "env": {
        "BRAIN_VAULT_PATH": "/path/to/your/obsidian/vault"
      }
    }
  }
}
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `BRAIN_VAULT_PATH` | Absolute path to the Obsidian vault | `~/Documents/Projects/Obsidian/Brain` |

## Tools

| Tool | Description |
|------|-------------|
| `brain_search_notes` | Full-text search across notes with context snippets |
| `brain_list_notes` | List notes in a folder, filterable by frontmatter type |
| `brain_read_note` | Read a note by path or title |
| `brain_create_note` | Create a new note (defaults to Notes/ per workflow) |
| `brain_update_note` | Replace content of an existing note |
| `brain_move_note` | Move/promote a note between folders |
| `brain_find_backlinks` | Find all notes linking to a given note via wikilinks |
| `brain_get_structure` | Vault overview with folder stats and MOC - Home |
| `brain_list_folders` | List subdirectories with note counts |

## Prompts

| Prompt | Description |
|--------|-------------|
| `vault_review` | Review inbox notes for promotion readiness |
| `kb_update` | Generate a KB Update note from a work session |
| `daily_capture` | Quick-capture a fleeting note |
| `project_status` | Status overview of all active projects |
| `find_related` | Map all Brain content related to a topic |

## Vault Structure

The server expects an Obsidian vault with these canonical folders:

```
Brain/
├── Notes/           ← Inbox: fleeting notes, KB Updates
├── APIs/            ← External API references
├── Infrastructure/  ← Servers, databases, networking
├── Personal/        ← Personal notes
├── Projects/        ← Active project trackers
├── Repositories/    ← Code repository references
├── Tooling/         ← AI tool configuration
├── Workflows/       ← Standards and processes
└── _Templates/      ← Note templates
```

## Development

```bash
# Install with dev dependencies
uv sync --group dev

# Run tests
uv run pytest

# Lint & format
uv run ruff check .
uv run ruff format .
```

## License

MIT
