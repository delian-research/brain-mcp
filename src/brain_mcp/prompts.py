"""MCP prompt registrations for the Brain vault."""

from datetime import date

from mcp.server.fastmcp import FastMCP

from brain_mcp.vault import collect_notes


def register_prompts(mcp: FastMCP) -> None:
    """Register all Brain vault prompts on the MCP server."""

    @mcp.prompt()
    async def vault_review() -> str:
        """Review inbox for notes ready to be promoted."""
        notes = await collect_notes("Notes", recursive=True)

        if not notes:
            return "The inbox is empty -- no notes pending review."

        lines = [
            "# Vault Inbox Review",
            "",
            "The following notes are in `Notes/` and may be ready for promotion.",
            "",
            "## Promotion Criteria",
            "A note is ready when: all template sections "
            "are filled, content is verified,",
            "and it is no longer actively being worked on.",
            "",
            "## Promotion Targets",
            "- **APIs** (`APIs/`): External API references",
            "- **Infrastructure** (`Infrastructure/`): Servers, databases, networking",
            "- **Projects** (`Projects/`): Active project trackers",
            "- **Repositories** (`Repositories/`): Code repository references",
            "- **Tooling** (`Tooling/`): AI tool configuration",
            "- **Workflows** (`Workflows/`): Standards and processes",
            "",
            "## Notes Pending Review",
            "",
        ]

        for note in notes:
            lines.append(f"### {note['title']}")
            lines.append(f"- **Path**: `{note['path']}`")
            lines.append(f"- **Type**: {note['type']}")
            lines.append(f"- **Updated**: {note['updated']}")
            lines.append("")

        lines.extend(
            [
                "## Instructions",
                "",
                "For each note above:",
                "1. Use `brain_read_note` to review its content",
                "2. Determine if it meets promotion criteria",
                "3. If ready, use `brain_move_note` "
                "to move it to the appropriate folder",
                "4. After moving, ensure it is linked from at least one MOC",
            ]
        )

        return "\n".join(lines)

    @mcp.prompt()
    def kb_update(
        task_name: str,
        context_reviewed: str = "",
        what_changed: str = "",
    ) -> str:
        """Create a KB Update note documenting a session."""
        today = date.today().isoformat()
        ctx = context_reviewed or ("(list [[wikilinks]] to notes consulted)")
        chg = what_changed or "(describe changes made)"
        return f"""Create a KB Update note using \
`brain_create_note` with:

**Title**: `{today} - {task_name}`
**Folder**: `Notes` (default)

Use this template for the content:

```markdown
---
type: resource
updated: {today}
---

# {today} - {task_name}

Date: {today}
Task: {task_name}

## Context Reviewed

- {ctx}

## What Changed

- {chg}

## Why

- (explain the reasoning)

## Impact/Risk

- (note any risks or downstream effects)

## Verification

- Commands/tests/checks run:
- Outcome:

## Next Steps

- (what should happen next)

## Related

- (link related notes with [[wikilinks]])
```

After creating, confirm the file path in the response."""

    @mcp.prompt()
    def daily_capture(topic: str = "") -> str:
        """Quick-capture a fleeting note to the inbox."""
        today = date.today().isoformat()
        title = f"{today} - {topic}" if topic else f"{today} - Quick Capture"
        return f"""Create a quick fleeting note using \
`brain_create_note`:

**Title**: `{title}`
**Folder**: `Notes`

Template:
```markdown
---
type: resource
updated: {today}
---

# {title}

## Notes

- (capture the idea or information here)

## Related

-
```

Keep it brief -- fleeting notes are meant for quick capture.
They'll be reviewed and promoted during vault maintenance."""

    @mcp.prompt()
    async def project_status() -> str:
        """Get a status overview of all active projects."""
        projects = await collect_notes("Projects", note_type="project", recursive=True)

        if not projects:
            return (
                "No project notes found. "
                "Use `brain_list_notes` with "
                "folder='Projects' to see all notes "
                "in the projects folder."
            )

        lines = [
            "# Active Projects Status",
            "",
            "Review these project notes for current status:",
            "",
        ]

        for p in projects:
            status_badge = f" [{p['status']}]" if p["status"] else ""
            lines.append(f"## {p['title']}{status_badge}")
            lines.append(f"- **Path**: `{p['path']}`")
            lines.append(f"- **Updated**: {p['updated']}")
            lines.append("")

        lines.extend(
            [
                "## Instructions",
                "",
                "For each project, use `brain_read_note` to get full details.",
                "Focus on: goal, current status, blockers, and next steps.",
            ]
        )

        return "\n".join(lines)

    @mcp.prompt()
    def find_related(topic: str) -> str:
        """Find and map all notes related to a topic."""
        return f"""Investigate how '{topic}' is covered \
across the Brain vault:

1. **Search**: Use `brain_search_notes` with \
query='{topic}' to find all mentions
2. **Structure**: Use `brain_get_structure` to see the \
vault layout and MOC - Home
3. **Backlinks**: For key notes found, use \
`brain_find_backlinks` to map connections
4. **Read**: Use `brain_read_note` on the most relevant \
2-3 notes for full context

Synthesize findings into:
- **Coverage summary**: What exists about {topic}
- **Key notes**: The most important references
- **Gaps**: What's missing or could be added
- **Connections**: How {topic} relates to other \
vault content"""
