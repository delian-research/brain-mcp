#!/usr/bin/env python3
"""
MCP Server for the Brain Obsidian Knowledge Base.

Provides tools for navigating, searching, structuring, and updating
an Obsidian vault with flat domain-based organization.

Vault layout:
    Notes/              — Capture: fleeting notes, KB Updates
    APIs/               — External API references
    Infrastructure/     — Servers, databases, networking
    Personal/           — Personal notes
    Projects/           — Active project trackers
    Repositories/       — Code repository references
    Tooling/            — AI tool configuration
    Workflows/          — Standards and processes
    _Templates/         — Note templates
"""

import json
import logging
import os
import re
import sys
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field, field_validator, ConfigDict

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

VAULT_PATH = os.environ.get(
    "BRAIN_VAULT_PATH",
    "/Users/aklingler/Documents/Projects/Obsidian/Brain",
)

VAULT_ROOT = Path(VAULT_PATH)

CANONICAL_FOLDERS = [
    "Notes",
    "APIs",
    "Infrastructure",
    "Personal",
    "Projects",
    "Repositories",
    "Tooling",
    "Workflows",
]

NOTE_TYPES = ["moc", "project", "area", "resource", "archive"]

# Logging — stderr only (stdio transport)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("brain_mcp")

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

mcp = FastMCP("brain_mcp")

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def _resolve_path(relative: str) -> Path:
    """Resolve a vault-relative path, preventing directory traversal."""
    cleaned = relative.lstrip("/").lstrip("\\")
    full = (VAULT_ROOT / cleaned).resolve()
    if not str(full).startswith(str(VAULT_ROOT.resolve())):
        raise ValueError(f"Path escapes vault root: {relative}")
    return full


def _vault_relative(absolute: Path) -> str:
    """Return vault-relative path string."""
    try:
        return str(absolute.resolve().relative_to(VAULT_ROOT.resolve()))
    except ValueError:
        return str(absolute)


def _parse_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter from a markdown string."""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        return {}
    try:
        raw = yaml.safe_load(match.group(1)) or {}
        # Convert date objects to strings for JSON compatibility
        return {k: str(v) if isinstance(v, date) else v for k, v in raw.items()}
    except yaml.YAMLError:
        return {}


def _extract_wikilinks(text: str) -> list[str]:
    """Extract [[wikilink]] targets from markdown text."""
    return re.findall(r"\[\[([^\]|]+?)(?:\|[^\]]*?)?\]\]", text)


def _build_frontmatter(meta: dict) -> str:
    """Build a YAML frontmatter block string."""
    lines = ["---"]
    for key, value in meta.items():
        lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


def _find_note_by_title(title: str) -> Optional[Path]:
    """Find a note by its title (filename without .md), case-insensitive."""
    title_lower = title.lower().strip()
    for p in VAULT_ROOT.rglob("*.md"):
        if p.stem.lower() == title_lower:
            return p
    return None


def _collect_notes(
    folder: Optional[str] = None,
    note_type: Optional[str] = None,
    recursive: bool = True,
) -> list[dict]:
    """Collect note metadata from the vault."""
    root = _resolve_path(folder) if folder else VAULT_ROOT
    if not root.is_dir():
        return []

    pattern = "**/*.md" if recursive else "*.md"
    results = []
    for p in root.glob(pattern):
        if ".obsidian" in p.parts:
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        meta = _parse_frontmatter(text)
        if note_type and meta.get("type") != note_type:
            continue
        results.append({
            "path": _vault_relative(p),
            "title": p.stem,
            "type": meta.get("type", "unknown"),
            "updated": str(meta.get("updated", "")),
            "status": meta.get("status", ""),
        })
    results.sort(key=lambda n: n["path"])
    return results


def _search_content(
    query: str,
    folder: Optional[str] = None,
    case_sensitive: bool = False,
) -> list[dict]:
    """Full-text search across vault notes, returning matching snippets."""
    root = _resolve_path(folder) if folder else VAULT_ROOT
    flags = 0 if case_sensitive else re.IGNORECASE
    pattern = re.compile(re.escape(query), flags)
    results = []

    for p in root.rglob("*.md"):
        if ".obsidian" in p.parts:
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        matches = list(pattern.finditer(text))
        if not matches:
            continue

        lines = text.splitlines()
        snippets = []
        for m in matches[:5]:  # cap snippets per file
            # find the line number
            line_start = text.count("\n", 0, m.start())
            context_start = max(0, line_start - 1)
            context_end = min(len(lines), line_start + 2)
            snippet = "\n".join(lines[context_start:context_end])
            snippets.append(snippet.strip())

        meta = _parse_frontmatter(text)
        results.append({
            "path": _vault_relative(p),
            "title": p.stem,
            "type": meta.get("type", "unknown"),
            "match_count": len(matches),
            "snippets": snippets,
        })

    results.sort(key=lambda r: r["match_count"], reverse=True)
    return results


# ---------------------------------------------------------------------------
# Pydantic Input Models
# ---------------------------------------------------------------------------


class SearchNotesInput(BaseModel):
    """Input for full-text search across the vault."""
    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(
        ...,
        description="Search string to match against note contents",
        min_length=1,
        max_length=500,
    )
    folder: Optional[str] = Field(
        default=None,
        description="Vault-relative folder to scope the search (e.g., 'Projects')",
    )
    limit: int = Field(
        default=20,
        description="Maximum results to return",
        ge=1,
        le=100,
    )


class ListNotesInput(BaseModel):
    """Input for listing notes in a folder."""
    model_config = ConfigDict(str_strip_whitespace=True)

    folder: Optional[str] = Field(
        default=None,
        description="Vault-relative folder path (e.g., 'Projects'). Omit for entire vault.",
    )
    note_type: Optional[str] = Field(
        default=None,
        description="Filter by frontmatter type: moc, project, area, resource, archive",
    )
    recursive: bool = Field(
        default=True,
        description="Include notes in subfolders",
    )
    limit: int = Field(default=50, ge=1, le=200)


class ReadNoteInput(BaseModel):
    """Input for reading a single note."""
    model_config = ConfigDict(str_strip_whitespace=True)

    path: Optional[str] = Field(
        default=None,
        description="Vault-relative path (e.g., 'Projects/delian-overview.md')",
    )
    title: Optional[str] = Field(
        default=None,
        description="Note title (filename without .md). Used if path is not provided.",
    )

    @field_validator("path", "title")
    @classmethod
    def at_least_one(cls, v: Optional[str], info) -> Optional[str]:
        return v  # cross-field validation below

    def resolve(self) -> Path:
        if self.path:
            return _resolve_path(self.path)
        if self.title:
            p = _find_note_by_title(self.title)
            if p:
                return p
            raise FileNotFoundError(f"No note found with title: {self.title}")
        raise ValueError("Provide either 'path' or 'title'")


class CreateNoteInput(BaseModel):
    """Input for creating a new note. Notes are created in Notes/ by default."""
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(
        ...,
        description="Note title (becomes the filename, e.g., '2026-03-12 - My Topic')",
        min_length=1,
        max_length=200,
    )
    content: str = Field(
        ...,
        description="Full markdown content including frontmatter (use --- delimiters)",
    )
    folder: str = Field(
        default="Notes",
        description="Vault-relative folder. Defaults to Notes/ per vault workflow.",
    )


class UpdateNoteInput(BaseModel):
    """Input for updating an existing note."""
    model_config = ConfigDict(str_strip_whitespace=True)

    path: Optional[str] = Field(default=None, description="Vault-relative path to the note")
    title: Optional[str] = Field(default=None, description="Note title to find")
    content: str = Field(..., description="Complete new content for the note (replaces existing)")
    update_date: bool = Field(
        default=True,
        description="Automatically set 'updated' frontmatter to today",
    )

    def resolve(self) -> Path:
        if self.path:
            return _resolve_path(self.path)
        if self.title:
            p = _find_note_by_title(self.title)
            if p:
                return p
            raise FileNotFoundError(f"No note found with title: {self.title}")
        raise ValueError("Provide either 'path' or 'title'")


class MoveNoteInput(BaseModel):
    """Input for moving/promoting a note to a new location."""
    model_config = ConfigDict(str_strip_whitespace=True)

    source: str = Field(
        ...,
        description="Vault-relative source path (e.g., 'Notes/my-note.md')",
    )
    destination_folder: str = Field(
        ...,
        description="Vault-relative destination folder (e.g., 'Projects')",
    )


class BacklinksInput(BaseModel):
    """Input for finding backlinks to a note."""
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(
        ...,
        description="Note title to find backlinks for (e.g., 'Vault Structure Standard')",
        min_length=1,
    )


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool(
    name="brain_search_notes",
    annotations={
        "title": "Search Brain Vault",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def brain_search_notes(params: SearchNotesInput) -> str:
    """Full-text search across the Brain Obsidian vault.

    Searches note content for the given query string and returns matching
    notes with context snippets. Useful for finding notes about a topic,
    locating references, or discovering related content.

    Args:
        params: Search parameters including query, optional folder scope, and limit.

    Returns:
        JSON with matching notes, each containing path, title, type, match count,
        and context snippets. Returns an error message if no results found.
    """
    try:
        results = _search_content(params.query, params.folder)
        if not results:
            return f"No notes found matching '{params.query}'"

        trimmed = results[: params.limit]
        return json.dumps({
            "total": len(results),
            "showing": len(trimmed),
            "results": trimmed,
        }, indent=2)
    except ValueError as e:
        return f"Error: {e}"
    except OSError as e:
        return f"Error reading vault: {e}"


@mcp.tool(
    name="brain_list_notes",
    annotations={
        "title": "List Notes in Vault",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def brain_list_notes(params: ListNotesInput) -> str:
    """List notes in a vault folder with optional filtering by type.

    Returns metadata for notes including path, title, type, updated date,
    and status. Useful for browsing a folder, reviewing inbox contents,
    or finding all notes of a specific type.

    Args:
        params: List parameters including folder, note_type filter, recursive flag, limit.

    Returns:
        JSON with note metadata list. Filterable by frontmatter type
        (moc, project, area, resource, archive).
    """
    try:
        notes = _collect_notes(params.folder, params.note_type, params.recursive)
        trimmed = notes[: params.limit]
        return json.dumps({
            "total": len(notes),
            "showing": len(trimmed),
            "notes": trimmed,
        }, indent=2)
    except ValueError as e:
        return f"Error: {e}"
    except OSError as e:
        return f"Error reading vault: {e}"


@mcp.tool(
    name="brain_read_note",
    annotations={
        "title": "Read a Note",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def brain_read_note(params: ReadNoteInput) -> str:
    """Read the full content of a specific note by path or title.

    Returns the complete markdown content including frontmatter, plus
    extracted metadata (type, wikilinks, updated date).

    Args:
        params: Either a vault-relative path or a note title.

    Returns:
        JSON with content, frontmatter metadata, and extracted wikilinks.
    """
    try:
        p = params.resolve()
        if not p.exists():
            return f"Error: Note not found at {_vault_relative(p)}"

        text = p.read_text(encoding="utf-8", errors="replace")
        meta = _parse_frontmatter(text)
        links = _extract_wikilinks(text)

        return json.dumps({
            "path": _vault_relative(p),
            "title": p.stem,
            "frontmatter": meta,
            "wikilinks": links,
            "content": text,
        }, indent=2)
    except (FileNotFoundError, ValueError) as e:
        return f"Error: {e}"
    except OSError as e:
        return f"Error reading note: {e}"


@mcp.tool(
    name="brain_create_note",
    annotations={
        "title": "Create a New Note",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def brain_create_note(params: CreateNoteInput) -> str:
    """Create a new note in the vault.

    By default notes are created in Notes/ per the vault workflow standard.
    Agent-created notes should always go to Notes/ first; promotion happens
    during manual vault review.

    Args:
        params: Title, content (full markdown with frontmatter), and target folder.

    Returns:
        Confirmation with the path of the created note, or an error if the
        note already exists.
    """
    try:
        folder = _resolve_path(params.folder)
        folder.mkdir(parents=True, exist_ok=True)

        filename = params.title if params.title.endswith(".md") else f"{params.title}.md"
        target = folder / filename

        if target.exists():
            return f"Error: Note already exists at {_vault_relative(target)}. Use brain_update_note to modify it."

        target.write_text(params.content, encoding="utf-8")
        logger.info("Created note: %s", _vault_relative(target))

        return json.dumps({
            "status": "created",
            "path": _vault_relative(target),
            "title": target.stem,
        }, indent=2)
    except ValueError as e:
        return f"Error: {e}"
    except OSError as e:
        return f"Error creating note: {e}"


@mcp.tool(
    name="brain_update_note",
    annotations={
        "title": "Update an Existing Note",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def brain_update_note(params: UpdateNoteInput) -> str:
    """Update the content of an existing note.

    Replaces the full content. If update_date is True (default), the
    'updated' field in frontmatter is set to today's date.

    Args:
        params: Note path or title, new content, and update_date flag.

    Returns:
        Confirmation with the updated path, or an error if not found.
    """
    try:
        p = params.resolve()
        if not p.exists():
            return f"Error: Note not found at {_vault_relative(p)}"

        content = params.content

        if params.update_date:
            meta = _parse_frontmatter(content)
            if meta:
                today = date.today().isoformat()
                content = re.sub(
                    r"(updated:\s*)[\d-]+",
                    f"\\g<1>{today}",
                    content,
                    count=1,
                )

        p.write_text(content, encoding="utf-8")
        logger.info("Updated note: %s", _vault_relative(p))

        return json.dumps({
            "status": "updated",
            "path": _vault_relative(p),
            "title": p.stem,
            "updated_date": date.today().isoformat(),
        }, indent=2)
    except (FileNotFoundError, ValueError) as e:
        return f"Error: {e}"
    except OSError as e:
        return f"Error updating note: {e}"


@mcp.tool(
    name="brain_move_note",
    annotations={
        "title": "Move / Promote a Note",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": False,
    },
)
async def brain_move_note(params: MoveNoteInput) -> str:
    """Move a note from one folder to another (e.g., promote from inbox).

    Commonly used to promote notes from Notes/ to their final location
    in a domain folder (Projects, Infrastructure, APIs, etc.).

    Args:
        params: Source path and destination folder.

    Returns:
        Confirmation with old and new paths, or an error.
    """
    try:
        source = _resolve_path(params.source)
        if not source.exists():
            return f"Error: Source not found at {params.source}"

        dest_dir = _resolve_path(params.destination_folder)
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / source.name

        if dest.exists():
            return f"Error: A note with the same name already exists at {_vault_relative(dest)}"

        source.rename(dest)
        logger.info("Moved note: %s -> %s", _vault_relative(source), _vault_relative(dest))

        return json.dumps({
            "status": "moved",
            "from": params.source,
            "to": _vault_relative(dest),
        }, indent=2)
    except ValueError as e:
        return f"Error: {e}"
    except OSError as e:
        return f"Error moving note: {e}"


@mcp.tool(
    name="brain_find_backlinks",
    annotations={
        "title": "Find Backlinks",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def brain_find_backlinks(params: BacklinksInput) -> str:
    """Find all notes that link to a given note via [[wikilinks]].

    Useful for understanding how a note is referenced across the vault,
    checking if a note is properly linked from MOCs, or mapping
    relationships between concepts.

    Args:
        params: Title of the note to find backlinks for.

    Returns:
        JSON list of notes that contain [[title]] wikilinks.
    """
    try:
        title_lower = params.title.lower()
        backlinks = []

        for p in VAULT_ROOT.rglob("*.md"):
            if ".obsidian" in p.parts:
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            links = _extract_wikilinks(text)
            if any(link.lower() == title_lower for link in links):
                meta = _parse_frontmatter(text)
                backlinks.append({
                    "path": _vault_relative(p),
                    "title": p.stem,
                    "type": meta.get("type", "unknown"),
                })

        if not backlinks:
            return f"No backlinks found for '{params.title}'"

        return json.dumps({
            "target": params.title,
            "backlink_count": len(backlinks),
            "backlinks": sorted(backlinks, key=lambda b: b["path"]),
        }, indent=2)
    except OSError as e:
        return f"Error scanning vault: {e}"


@mcp.tool(
    name="brain_get_structure",
    annotations={
        "title": "Get Vault Structure",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def brain_get_structure() -> str:
    """Get a high-level overview of the vault structure.

    Returns the canonical folder layout, note counts per folder, and
    the contents of MOC - Home for navigation. Use this as a starting
    point for exploring the vault.

    Returns:
        JSON with folder statistics, total note count, and MOC - Home content.
    """
    try:
        folders = {}
        total = 0

        for folder_name in CANONICAL_FOLDERS:
            folder_path = VAULT_ROOT / folder_name
            if folder_path.is_dir():
                count = sum(1 for _ in folder_path.rglob("*.md"))
                folders[folder_name] = count
                total += count

        # Read MOC - Home for navigation
        moc_home = VAULT_ROOT / "MOC - Home.md"
        moc_content = ""
        if moc_home.exists():
            moc_content = moc_home.read_text(encoding="utf-8", errors="replace")

        return json.dumps({
            "vault_path": str(VAULT_ROOT),
            "total_notes": total,
            "folders": folders,
            "moc_home": moc_content,
        }, indent=2)
    except OSError as e:
        return f"Error reading vault structure: {e}"


@mcp.tool(
    name="brain_list_folders",
    annotations={
        "title": "List Vault Folders",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def brain_list_folders(
    folder: Optional[str] = None,
) -> str:
    """List subfolders within a vault directory.

    Returns immediate subdirectories and their note counts.
    Useful for exploring the vault hierarchy before reading specific notes.

    Args:
        folder: Optional vault-relative path. Omit for vault root.

    Returns:
        JSON list of subdirectories with note counts.
    """
    try:
        root = _resolve_path(folder) if folder else VAULT_ROOT
        if not root.is_dir():
            return f"Error: Not a directory: {folder}"

        dirs = []
        for item in sorted(root.iterdir()):
            if item.is_dir() and item.name != ".obsidian" and not item.name.startswith("."):
                count = sum(1 for _ in item.rglob("*.md"))
                dirs.append({"name": item.name, "note_count": count})

        return json.dumps({"parent": folder or "/", "folders": dirs}, indent=2)
    except ValueError as e:
        return f"Error: {e}"
    except OSError as e:
        return f"Error listing folders: {e}"


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------


@mcp.prompt()
def vault_review() -> str:
    """Review inbox for notes ready to be promoted.

    Lists all notes currently in Notes/ with their metadata,
    and provides guidance on the promotion workflow per the Vault Structure
    Standard.
    """
    notes = _collect_notes("Notes", recursive=True)

    if not notes:
        return "The inbox is empty — no notes pending review."

    lines = [
        "# Vault Inbox Review",
        "",
        "The following notes are in `Notes/` and may be ready for promotion.",
        "",
        "## Promotion Criteria",
        "A note is ready when: all template sections are filled, content is verified,",
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

    lines.extend([
        "## Instructions",
        "",
        "For each note above:",
        "1. Use `brain_read_note` to review its content",
        "2. Determine if it meets promotion criteria",
        "3. If ready, use `brain_move_note` to move it to the appropriate folder",
        "4. After moving, ensure it is linked from at least one MOC",
    ])

    return "\n".join(lines)


@mcp.prompt()
def kb_update(task_name: str, context_reviewed: str = "", what_changed: str = "") -> str:
    """Create a KB Update note documenting a work session.

    Generates a pre-filled KB Update using the vault template format.
    The note will be created in Notes/ per the workflow standard.

    Args:
        task_name: Short name for the task (e.g., 'Delian Database Migration')
        context_reviewed: Notes consulted during the task (wikilinks)
        what_changed: Summary of what was done
    """
    today = date.today().isoformat()
    return f"""Create a KB Update note using `brain_create_note` with:

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

- {context_reviewed or '(list [[wikilinks]] to notes consulted)'}

## What Changed

- {what_changed or '(describe changes made)'}

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
    """Quick-capture a fleeting note to the inbox.

    Creates a minimal note for rapid idea capture. The note goes to
    Notes/ and can be expanded or promoted later.

    Args:
        topic: Optional topic or title hint for the note
    """
    today = date.today().isoformat()
    title = f"{today} - {topic}" if topic else f"{today} - Quick Capture"
    return f"""Create a quick fleeting note using `brain_create_note`:

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

Keep it brief — fleeting notes are meant for quick capture.
They'll be reviewed and promoted during vault maintenance."""


@mcp.prompt()
def project_status() -> str:
    """Get a status overview of all active projects.

    Reads the Projects folder and summarizes active projects with their
    status, recent updates, and key links.
    """
    projects = _collect_notes("Projects", note_type="project", recursive=True)

    if not projects:
        return (
            "No project notes found. Use `brain_list_notes` with folder='Projects' "
            "to see all notes in the projects folder."
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

    lines.extend([
        "## Instructions",
        "",
        "For each project, use `brain_read_note` to get full details.",
        "Focus on: goal, current status, blockers, and next steps.",
    ])

    return "\n".join(lines)


@mcp.prompt()
def find_related(topic: str) -> str:
    """Find and map all notes related to a topic.

    Combines search, backlinks, and MOC navigation to build a
    comprehensive picture of how a topic is covered in the vault.

    Args:
        topic: The topic to investigate (e.g., 'Delian', 'authentication')
    """
    return f"""Investigate how '{topic}' is covered across the Brain vault:

1. **Search**: Use `brain_search_notes` with query='{topic}' to find all mentions
2. **Structure**: Use `brain_get_structure` to see the vault layout and MOC - Home
3. **Backlinks**: For key notes found, use `brain_find_backlinks` to map connections
4. **Read**: Use `brain_read_note` on the most relevant 2-3 notes for full context

Synthesize findings into:
- **Coverage summary**: What exists about {topic}
- **Key notes**: The most important references
- **Gaps**: What's missing or could be added
- **Connections**: How {topic} relates to other vault content"""


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
