"""MCP tool registrations for the Brain vault."""

import logging
from datetime import date
from typing import Optional

import anyio
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations

from brain_mcp.models import (
    AppendToNoteInput,
    BacklinksInput,
    CreateNoteInput,
    GetRecentInput,
    GetTagsInput,
    ListNotesInput,
    MoveNoteInput,
    ReadNoteInput,
    SearchFrontmatterInput,
    SearchNotesInput,
    UpdateNoteInput,
)
from brain_mcp.outputs import (
    AppendResult,
    BacklinkEntry,
    BacklinksResult,
    CreateNoteResult,
    FrontmatterMatch,
    GetRecentResult,
    GetTagsResult,
    ListFoldersResult,
    ListNotesResult,
    MoveNoteResult,
    NoteMatch,
    NoteSummary,
    ReadNoteResult,
    RecentNote,
    SearchFrontmatterResult,
    SearchResult,
    UpdateNoteResult,
    VaultStructure,
)
from brain_mcp.vault import (
    append_to_note,
    collect_notes,
    create_note,
    extract_wikilinks,
    find_backlinks,
    get_all_tags,
    get_recent_notes,
    get_structure,
    list_folders,
    move_note,
    parse_frontmatter,
    search_content,
    search_frontmatter,
    update_note,
    vault_relative,
)

logger = logging.getLogger("brain_mcp.tools")


def register_tools(mcp: FastMCP) -> None:
    """Register all Brain vault tools on the MCP server."""

    @mcp.tool(
        name="brain_search_notes",
        annotations=ToolAnnotations(
            title="Search Brain Vault",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def brain_search_notes(
        params: SearchNotesInput,
    ) -> SearchResult:
        """Full-text search across the Brain vault.

        Searches note content for the given query string
        and returns matching notes with context snippets.
        """
        try:
            results = await search_content(params.query, params.folder)
            trimmed = results[: params.limit]
            return SearchResult(
                total=len(results),
                showing=len(trimmed),
                results=[NoteMatch(**r) for r in trimmed],
            )
        except ValueError as e:
            raise ToolError(str(e)) from e
        except OSError:
            logger.exception("Failed to search vault")
            raise ToolError("Error reading vault")

    @mcp.tool(
        name="brain_list_notes",
        annotations=ToolAnnotations(
            title="List Notes in Vault",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def brain_list_notes(
        params: ListNotesInput,
    ) -> ListNotesResult:
        """List notes with optional type filtering."""
        try:
            notes = await collect_notes(
                params.folder,
                params.note_type,
                params.recursive,
            )
            trimmed = notes[: params.limit]
            return ListNotesResult(
                total=len(notes),
                showing=len(trimmed),
                notes=[NoteSummary(**n) for n in trimmed],
            )
        except ValueError as e:
            raise ToolError(str(e)) from e
        except OSError:
            logger.exception("Failed to list notes")
            raise ToolError("Error reading vault")

    @mcp.tool(
        name="brain_read_note",
        annotations=ToolAnnotations(
            title="Read a Note",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def brain_read_note(
        params: ReadNoteInput,
    ) -> ReadNoteResult:
        """Read the full content of a note."""
        try:
            p = await params.resolve()
            if not await anyio.Path(p).exists():
                raise ToolError(f"Note not found at {vault_relative(p)}")

            text = await anyio.Path(p).read_text(encoding="utf-8", errors="replace")
            meta = parse_frontmatter(text)
            links = extract_wikilinks(text)

            return ReadNoteResult(
                path=vault_relative(p),
                title=p.stem,
                frontmatter=meta,
                wikilinks=links,
                content=text,
            )
        except (FileNotFoundError, ValueError) as e:
            raise ToolError(str(e)) from e
        except OSError:
            logger.exception("Failed to read note")
            raise ToolError("Error reading note")

    @mcp.tool(
        name="brain_create_note",
        annotations=ToolAnnotations(
            title="Create a New Note",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def brain_create_note(
        params: CreateNoteInput,
    ) -> CreateNoteResult:
        """Create a new note in the vault.

        Defaults to Notes/ per workflow.
        """
        try:
            target = await create_note(
                params.folder,
                params.title,
                params.content,
            )
            return CreateNoteResult(
                path=vault_relative(target),
                title=target.stem,
            )
        except (ValueError, FileExistsError) as e:
            raise ToolError(str(e)) from e
        except OSError:
            logger.exception("Failed to create note")
            raise ToolError("Error creating note")

    @mcp.tool(
        name="brain_update_note",
        annotations=ToolAnnotations(
            title="Update an Existing Note",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def brain_update_note(
        params: UpdateNoteInput,
    ) -> UpdateNoteResult:
        """Update the content of an existing note."""
        try:
            p = await params.resolve()
            await update_note(p, params.content, params.update_date)
            return UpdateNoteResult(
                path=vault_relative(p),
                title=p.stem,
                updated_date=date.today().isoformat(),
            )
        except (FileNotFoundError, ValueError) as e:
            raise ToolError(str(e)) from e
        except OSError:
            logger.exception("Failed to update note")
            raise ToolError("Error updating note")

    @mcp.tool(
        name="brain_move_note",
        annotations=ToolAnnotations(
            title="Move / Promote a Note",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def brain_move_note(
        params: MoveNoteInput,
    ) -> MoveNoteResult:
        """Move a note between folders (e.g., promote)."""
        try:
            old, new = await move_note(
                params.source,
                params.destination_folder,
            )
            return MoveNoteResult(
                from_path=old,
                to_path=new,
            )
        except (
            ValueError,
            FileNotFoundError,
            FileExistsError,
        ) as e:
            raise ToolError(str(e)) from e
        except OSError:
            logger.exception("Failed to move note")
            raise ToolError("Error moving note")

    @mcp.tool(
        name="brain_find_backlinks",
        annotations=ToolAnnotations(
            title="Find Backlinks",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def brain_find_backlinks(
        params: BacklinksInput,
    ) -> BacklinksResult:
        """Find notes linking to a note via [[wikilinks]]."""
        try:
            backlinks = await find_backlinks(params.title)
            return BacklinksResult(
                target=params.title,
                backlink_count=len(backlinks),
                backlinks=[BacklinkEntry(**b) for b in backlinks],
            )
        except OSError:
            logger.exception("Failed to scan vault for backlinks")
            raise ToolError("Error scanning vault")

    @mcp.tool(
        name="brain_get_structure",
        annotations=ToolAnnotations(
            title="Get Vault Structure",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def brain_get_structure() -> VaultStructure:
        """Get a high-level overview of vault structure."""
        try:
            data = await get_structure()
            return VaultStructure(**data)
        except OSError:
            logger.exception("Failed to read vault structure")
            raise ToolError("Error reading vault structure")

    @mcp.tool(
        name="brain_list_folders",
        annotations=ToolAnnotations(
            title="List Vault Folders",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def brain_list_folders(
        folder: Optional[str] = None,
    ) -> ListFoldersResult:
        """List subfolders within a vault directory."""
        try:
            data = await list_folders(folder)
            return ListFoldersResult(**data)
        except (ValueError, NotADirectoryError) as e:
            raise ToolError(str(e)) from e
        except OSError:
            logger.exception("Failed to list folders")
            raise ToolError("Error listing folders")

    @mcp.tool(
        name="brain_append_to_note",
        annotations=ToolAnnotations(
            title="Append to a Note",
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def brain_append_to_note(
        params: AppendToNoteInput,
    ) -> AppendResult:
        """Append text to an existing note without overwriting.

        Adds content to the end of the note. Useful for logs,
        journal entries, or incremental updates.
        """
        try:
            p = await params.resolve()
            await append_to_note(p, params.text, params.update_date)
            return AppendResult(
                path=vault_relative(p),
                title=p.stem,
            )
        except (FileNotFoundError, ValueError) as e:
            raise ToolError(str(e)) from e
        except OSError:
            logger.exception("Failed to append to note")
            raise ToolError("Error appending to note")

    @mcp.tool(
        name="brain_search_frontmatter",
        annotations=ToolAnnotations(
            title="Search by Frontmatter",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def brain_search_frontmatter(
        params: SearchFrontmatterInput,
    ) -> SearchFrontmatterResult:
        """Search notes by frontmatter field and optional value.

        Find notes with specific metadata, e.g., all notes with
        status: active, or all notes that have a 'tags' field.
        """
        try:
            results = await search_frontmatter(
                params.field, params.value, params.folder
            )
            trimmed = results[: params.limit]
            return SearchFrontmatterResult(
                total=len(results),
                showing=len(trimmed),
                field=params.field,
                results=[FrontmatterMatch(**r) for r in trimmed],
            )
        except ValueError as e:
            raise ToolError(str(e)) from e
        except OSError:
            logger.exception("Failed to search frontmatter")
            raise ToolError("Error searching frontmatter")

    @mcp.tool(
        name="brain_get_recent",
        annotations=ToolAnnotations(
            title="Get Recent Notes",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def brain_get_recent(
        params: GetRecentInput,
    ) -> GetRecentResult:
        """Get recently modified notes sorted by modification time.

        Uses filesystem timestamps for accuracy.
        """
        try:
            results = await get_recent_notes(params.limit, params.folder)
            return GetRecentResult(
                total=len(results),
                showing=len(results),
                notes=[RecentNote(**r) for r in results],
            )
        except ValueError as e:
            raise ToolError(str(e)) from e
        except OSError:
            logger.exception("Failed to get recent notes")
            raise ToolError("Error getting recent notes")

    @mcp.tool(
        name="brain_get_tags",
        annotations=ToolAnnotations(
            title="Get All Tags",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def brain_get_tags(
        params: GetTagsInput,
    ) -> GetTagsResult:
        """Get all unique tags from frontmatter across the vault.

        Useful for discovering tag taxonomy and finding
        notes to explore.
        """
        try:
            tags = await get_all_tags(params.folder)
            return GetTagsResult(
                total=len(tags),
                tags=tags,
            )
        except ValueError as e:
            raise ToolError(str(e)) from e
        except OSError:
            logger.exception("Failed to get tags")
            raise ToolError("Error getting tags")
