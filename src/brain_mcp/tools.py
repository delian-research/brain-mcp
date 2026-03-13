"""MCP tool registrations for the Brain vault."""

import json
import logging
from datetime import date
from typing import Optional

from mcp.server.fastmcp import FastMCP

from brain_mcp.models import (
    BacklinksInput,
    CreateNoteInput,
    ListNotesInput,
    MoveNoteInput,
    ReadNoteInput,
    SearchNotesInput,
    UpdateNoteInput,
)
from brain_mcp.vault import (
    collect_notes,
    create_note,
    extract_wikilinks,
    find_backlinks,
    get_structure,
    list_folders,
    move_note,
    parse_frontmatter,
    search_content,
    update_note,
    vault_relative,
)

logger = logging.getLogger("brain_mcp.tools")


def register_tools(mcp: FastMCP) -> None:
    """Register all Brain vault tools on the given MCP server."""

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
        notes with context snippets.
        """
        try:
            results = search_content(params.query, params.folder)
            if not results:
                return f"No notes found matching '{params.query}'"

            trimmed = results[: params.limit]
            return json.dumps(
                {"total": len(results), "showing": len(trimmed), "results": trimmed},
                indent=2,
            )
        except ValueError as e:
            return f"Error: {e}"
        except OSError:
            logger.exception("Failed to search vault")
            return "Error reading vault"

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
        """List notes in a vault folder with optional filtering by type."""
        try:
            notes = collect_notes(params.folder, params.note_type, params.recursive)
            trimmed = notes[: params.limit]
            return json.dumps(
                {"total": len(notes), "showing": len(trimmed), "notes": trimmed},
                indent=2,
            )
        except ValueError as e:
            return f"Error: {e}"
        except OSError:
            logger.exception("Failed to list notes")
            return "Error reading vault"

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
        """Read the full content of a specific note by path or title."""
        try:
            p = params.resolve()
            if not p.exists():
                return f"Error: Note not found at {vault_relative(p)}"

            text = p.read_text(encoding="utf-8", errors="replace")
            meta = parse_frontmatter(text)
            links = extract_wikilinks(text)

            return json.dumps(
                {
                    "path": vault_relative(p),
                    "title": p.stem,
                    "frontmatter": meta,
                    "wikilinks": links,
                    "content": text,
                },
                indent=2,
            )
        except (FileNotFoundError, ValueError) as e:
            return f"Error: {e}"
        except OSError:
            logger.exception("Failed to read note")
            return "Error reading note"

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
        """Create a new note in the vault. Defaults to Notes/ per workflow."""
        try:
            target = create_note(params.folder, params.title, params.content)
            return json.dumps(
                {
                    "status": "created",
                    "path": vault_relative(target),
                    "title": target.stem,
                },
                indent=2,
            )
        except (ValueError, FileExistsError) as e:
            return f"Error: {e}"
        except OSError:
            logger.exception("Failed to create note")
            return "Error creating note"

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
        """Update the content of an existing note."""
        try:
            p = params.resolve()
            update_note(p, params.content, params.update_date)
            return json.dumps(
                {
                    "status": "updated",
                    "path": vault_relative(p),
                    "title": p.stem,
                    "updated_date": date.today().isoformat(),
                },
                indent=2,
            )
        except (FileNotFoundError, ValueError) as e:
            return f"Error: {e}"
        except OSError:
            logger.exception("Failed to update note")
            return "Error updating note"

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
        """Move a note from one folder to another (e.g., promote from inbox)."""
        try:
            old, new = move_note(params.source, params.destination_folder)
            return json.dumps(
                {"status": "moved", "from": old, "to": new},
                indent=2,
            )
        except (ValueError, FileNotFoundError, FileExistsError) as e:
            return f"Error: {e}"
        except OSError:
            logger.exception("Failed to move note")
            return "Error moving note"

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
        """Find all notes that link to a given note via [[wikilinks]]."""
        try:
            backlinks = find_backlinks(params.title)
            if not backlinks:
                return f"No backlinks found for '{params.title}'"

            return json.dumps(
                {
                    "target": params.title,
                    "backlink_count": len(backlinks),
                    "backlinks": backlinks,
                },
                indent=2,
            )
        except OSError:
            logger.exception("Failed to scan vault for backlinks")
            return "Error scanning vault"

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
        """Get a high-level overview of the vault structure."""
        try:
            return json.dumps(get_structure(), indent=2)
        except OSError:
            logger.exception("Failed to read vault structure")
            return "Error reading vault structure"

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
    async def brain_list_folders(folder: Optional[str] = None) -> str:
        """List subfolders within a vault directory."""
        try:
            return json.dumps(list_folders(folder), indent=2)
        except (ValueError, NotADirectoryError) as e:
            return f"Error: {e}"
        except OSError:
            logger.exception("Failed to list folders")
            return "Error listing folders"
