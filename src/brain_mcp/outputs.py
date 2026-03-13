"""Pydantic output models for brain-mcp tool results."""

from typing import Any

from pydantic import BaseModel, Field


class NoteMatch(BaseModel):
    """A single search result."""

    path: str
    title: str
    type: str
    match_count: int
    snippets: list[str]


class SearchResult(BaseModel):
    """Result of a vault search."""

    total: int
    showing: int
    results: list[NoteMatch]


class NoteSummary(BaseModel):
    """Summary metadata for a note."""

    path: str
    title: str
    type: str
    updated: str
    status: str = ""


class ListNotesResult(BaseModel):
    """Result of listing notes."""

    total: int
    showing: int
    notes: list[NoteSummary]


class ReadNoteResult(BaseModel):
    """Result of reading a single note."""

    path: str
    title: str
    frontmatter: dict[str, Any]
    wikilinks: list[str]
    content: str


class CreateNoteResult(BaseModel):
    """Result of creating a note."""

    status: str = "created"
    path: str
    title: str


class UpdateNoteResult(BaseModel):
    """Result of updating a note."""

    status: str = "updated"
    path: str
    title: str
    updated_date: str


class MoveNoteResult(BaseModel):
    """Result of moving a note."""

    status: str = "moved"
    from_path: str = Field(serialization_alias="from")
    to_path: str = Field(serialization_alias="to")


class BacklinkEntry(BaseModel):
    """A single backlink reference."""

    path: str
    title: str
    type: str


class BacklinksResult(BaseModel):
    """Result of finding backlinks."""

    target: str
    backlink_count: int
    backlinks: list[BacklinkEntry]


class FolderInfo(BaseModel):
    """A folder with its note count."""

    name: str
    note_count: int


class VaultStructure(BaseModel):
    """High-level vault structure."""

    vault_path: str
    total_notes: int
    folders: dict[str, int]
    moc_home: str


class AppendResult(BaseModel):
    """Result of appending to a note."""

    status: str = "appended"
    path: str
    title: str


class FrontmatterMatch(BaseModel):
    """A single frontmatter search result."""

    path: str
    title: str
    type: str
    field: str
    field_value: Any


class SearchFrontmatterResult(BaseModel):
    """Result of a frontmatter search."""

    total: int
    showing: int
    field: str
    results: list[FrontmatterMatch]


class RecentNote(BaseModel):
    """A recently modified note."""

    path: str
    title: str
    type: str
    modified: str


class GetRecentResult(BaseModel):
    """Result of getting recent notes."""

    total: int
    showing: int
    notes: list[RecentNote]


class GetTagsResult(BaseModel):
    """Result of getting all tags."""

    total: int
    tags: list[str]


class ListFoldersResult(BaseModel):
    """Result of listing folders."""

    parent: str
    folders: list[FolderInfo]
