"""Pydantic input models for brain-mcp tools."""

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from brain_mcp.vault import (
    find_note_by_title,
    resolve_path,
)


class SearchNotesInput(BaseModel):
    """Input for full-text search across the vault."""

    model_config = ConfigDict(str_strip_whitespace=True)

    query: str = Field(
        ...,
        description=("Search string to match against note contents"),
        min_length=1,
        max_length=500,
    )
    folder: Optional[str] = Field(
        default=None,
        description=("Vault-relative folder to scope the search (e.g., 'Projects')"),
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
        description=(
            "Vault-relative folder path (e.g., 'Projects'). Omit for entire vault."
        ),
    )
    note_type: Optional[str] = Field(
        default=None,
        description=(
            "Filter by frontmatter type: moc, project, area, resource, archive"
        ),
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
        description=("Vault-relative path (e.g., 'Projects/delian-overview.md')"),
    )
    title: Optional[str] = Field(
        default=None,
        description=(
            "Note title (filename without .md). Used if path is not provided."
        ),
    )

    async def resolve(self) -> Path:
        if self.path:
            return resolve_path(self.path)
        if self.title:
            p = await find_note_by_title(self.title)
            if p:
                return p
            raise FileNotFoundError(f"No note found with title: {self.title}")
        raise ValueError("Provide either 'path' or 'title'")


class CreateNoteInput(BaseModel):
    """Input for creating a new note.

    Notes are created in Notes/ by default.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(
        ...,
        description=(
            "Note title (becomes the filename, e.g., '2026-03-12 - My Topic')"
        ),
        min_length=1,
        max_length=200,
    )
    content: str = Field(
        ...,
        description=(
            "Full markdown content including frontmatter (use --- delimiters)"
        ),
    )
    folder: str = Field(
        default="Notes",
        description=("Vault-relative folder. Defaults to Notes/ per vault workflow."),
    )


class UpdateNoteInput(BaseModel):
    """Input for updating an existing note."""

    model_config = ConfigDict(str_strip_whitespace=True)

    path: Optional[str] = Field(
        default=None,
        description="Vault-relative path to the note",
    )
    title: Optional[str] = Field(
        default=None,
        description="Note title to find",
    )
    content: str = Field(
        ...,
        description=("Complete new content for the note (replaces existing)"),
    )
    update_date: bool = Field(
        default=True,
        description=("Automatically set 'updated' frontmatter to today"),
    )

    async def resolve(self) -> Path:
        if self.path:
            return resolve_path(self.path)
        if self.title:
            p = await find_note_by_title(self.title)
            if p:
                return p
            raise FileNotFoundError(f"No note found with title: {self.title}")
        raise ValueError("Provide either 'path' or 'title'")


class MoveNoteInput(BaseModel):
    """Input for moving/promoting a note."""

    model_config = ConfigDict(str_strip_whitespace=True)

    source: str = Field(
        ...,
        description=("Vault-relative source path (e.g., 'Notes/my-note.md')"),
    )
    destination_folder: str = Field(
        ...,
        description=("Vault-relative destination folder (e.g., 'Projects')"),
    )


class AppendToNoteInput(BaseModel):
    """Input for appending text to an existing note."""

    model_config = ConfigDict(str_strip_whitespace=True)

    path: Optional[str] = Field(
        default=None,
        description="Vault-relative path to the note",
    )
    title: Optional[str] = Field(
        default=None,
        description="Note title to find",
    )
    text: str = Field(
        ...,
        description="Text to append to the note",
        min_length=1,
    )
    update_date: bool = Field(
        default=True,
        description="Automatically set 'updated' frontmatter to today",
    )

    async def resolve(self) -> Path:
        if self.path:
            return resolve_path(self.path)
        if self.title:
            p = await find_note_by_title(self.title)
            if p:
                return p
            raise FileNotFoundError(f"No note found with title: {self.title}")
        raise ValueError("Provide either 'path' or 'title'")


class SearchFrontmatterInput(BaseModel):
    """Input for searching notes by frontmatter fields."""

    model_config = ConfigDict(str_strip_whitespace=True)

    field: str = Field(
        ...,
        description=("Frontmatter field to search (e.g., 'status', 'type', 'tags')"),
        min_length=1,
    )
    value: Optional[str] = Field(
        default=None,
        description=("Value to match. Omit to find all notes where the field exists."),
    )
    folder: Optional[str] = Field(
        default=None,
        description="Vault-relative folder to scope the search",
    )
    limit: int = Field(default=50, ge=1, le=200)


class GetRecentInput(BaseModel):
    """Input for getting recently modified notes."""

    model_config = ConfigDict(str_strip_whitespace=True)

    limit: int = Field(
        default=10,
        description="Maximum number of recent notes to return",
        ge=1,
        le=100,
    )
    folder: Optional[str] = Field(
        default=None,
        description="Vault-relative folder to scope the search",
    )


class GetTagsInput(BaseModel):
    """Input for getting all unique tags from the vault."""

    model_config = ConfigDict(str_strip_whitespace=True)

    folder: Optional[str] = Field(
        default=None,
        description="Vault-relative folder to scope the search",
    )


class BacklinksInput(BaseModel):
    """Input for finding backlinks to a note."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(
        ...,
        description=(
            "Note title to find backlinks for (e.g., 'Vault Structure Standard')"
        ),
        min_length=1,
    )
