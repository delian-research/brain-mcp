"""Tests for vault filesystem operations."""

from pathlib import Path

import pytest

from brain_mcp.vault import (
    append_to_note,
    collect_notes,
    create_note,
    extract_wikilinks,
    find_backlinks,
    find_note_by_title,
    get_all_tags,
    get_recent_notes,
    get_structure,
    list_folders,
    move_note,
    parse_frontmatter,
    resolve_path,
    search_content,
    search_frontmatter,
    update_note,
    vault_relative,
)

# -------------------------------------------------------------------
# Path resolution (sync)
# -------------------------------------------------------------------


def test_resolve_path_valid(tmp_vault: Path) -> None:
    result = resolve_path("Notes")
    assert result == tmp_vault / "Notes"


def test_resolve_path_strips_leading_slash(
    tmp_vault: Path,
) -> None:
    result = resolve_path("/Notes")
    assert result == tmp_vault / "Notes"


def test_resolve_path_blocks_traversal() -> None:
    with pytest.raises(ValueError, match="escapes vault root"):
        resolve_path("../../etc/passwd")


def test_vault_relative(tmp_vault: Path) -> None:
    full = tmp_vault / "Projects" / "foo.md"
    assert vault_relative(full) == "Projects/foo.md"


# -------------------------------------------------------------------
# Frontmatter parsing (sync)
# -------------------------------------------------------------------


def test_parse_frontmatter_valid() -> None:
    text = "---\ntype: project\nupdated: 2026-03-01\n---\n# Title\n"
    meta = parse_frontmatter(text)
    assert meta["type"] == "project"
    assert meta["updated"] == "2026-03-01"


def test_parse_frontmatter_missing() -> None:
    assert parse_frontmatter("# Just a heading\n") == {}


def test_parse_frontmatter_invalid_yaml() -> None:
    text = "---\n: invalid: yaml: here\n---\n"
    assert parse_frontmatter(text) == {}


# -------------------------------------------------------------------
# Wikilink extraction (sync)
# -------------------------------------------------------------------


def test_extract_wikilinks_simple() -> None:
    text = "See [[Project Alpha]] and [[API Reference]]."
    links = extract_wikilinks(text)
    assert links == ["Project Alpha", "API Reference"]


def test_extract_wikilinks_with_alias() -> None:
    text = "See [[Project Alpha|the project]]."
    links = extract_wikilinks(text)
    assert links == ["Project Alpha"]


def test_extract_wikilinks_none() -> None:
    assert extract_wikilinks("No links here.") == []


# -------------------------------------------------------------------
# Note lookup (async)
# -------------------------------------------------------------------


async def test_find_note_by_title(
    tmp_vault: Path,
) -> None:
    result = await find_note_by_title("Project Alpha")
    assert result is not None
    assert result.stem == "Project Alpha"


async def test_find_note_by_title_case_insensitive(
    tmp_vault: Path,
) -> None:
    result = await find_note_by_title("project alpha")
    assert result is not None


async def test_find_note_by_title_missing() -> None:
    assert await find_note_by_title("nonexistent") is None


# -------------------------------------------------------------------
# Collect notes (async)
# -------------------------------------------------------------------


async def test_collect_notes_all() -> None:
    notes = await collect_notes()
    titles = {n["title"] for n in notes}
    assert "Project Alpha" in titles
    assert "API Reference" in titles


async def test_collect_notes_folder() -> None:
    notes = await collect_notes(folder="Projects")
    assert len(notes) == 1
    assert notes[0]["title"] == "Project Alpha"


async def test_collect_notes_by_type() -> None:
    notes = await collect_notes(note_type="project")
    assert all(n["type"] == "project" for n in notes)


async def test_collect_notes_excludes_obsidian() -> None:
    notes = await collect_notes()
    paths = [n["path"] for n in notes]
    assert not any(".obsidian" in p for p in paths)


# -------------------------------------------------------------------
# Search content (async)
# -------------------------------------------------------------------


async def test_search_content_finds_match() -> None:
    results = await search_content("test project")
    assert len(results) >= 1
    assert any(r["title"] == "Project Alpha" for r in results)


async def test_search_content_case_insensitive() -> None:
    results = await search_content("TEST PROJECT")
    assert len(results) >= 1


async def test_search_content_no_results() -> None:
    assert await search_content("zzz_nonexistent_zzz") == []


async def test_search_content_scoped_folder() -> None:
    results = await search_content("Reference", folder="APIs")
    assert all("APIs" in r["path"] for r in results)


# -------------------------------------------------------------------
# Create note (async)
# -------------------------------------------------------------------


async def test_create_note(tmp_vault: Path) -> None:
    path = await create_note(
        "Notes",
        "Test Note",
        "---\ntype: resource\n---\n# Test\n",
    )
    assert path.exists()
    assert path.stem == "Test Note"


async def test_create_note_duplicate_raises(
    tmp_vault: Path,
) -> None:
    await create_note("Notes", "Unique Note", "content")
    with pytest.raises(FileExistsError):
        await create_note("Notes", "Unique Note", "content again")


async def test_create_note_new_subfolder(
    tmp_vault: Path,
) -> None:
    path = await create_note("Notes/sub", "Deep Note", "content")
    assert path.exists()
    assert "sub" in str(path)


# -------------------------------------------------------------------
# Update note (async)
# -------------------------------------------------------------------


async def test_update_note_content(
    tmp_vault: Path,
) -> None:
    note = tmp_vault / "Projects" / "Project Alpha.md"
    new_content = "---\ntype: project\nupdated: 2026-01-01\n---\n# Updated\n"
    await update_note(note, new_content, update_date=True)
    text = note.read_text()
    assert "2026-01-01" not in text or "updated:" in text


async def test_update_note_missing_raises(
    tmp_vault: Path,
) -> None:
    fake = tmp_vault / "nope.md"
    with pytest.raises(FileNotFoundError):
        await update_note(fake, "content")


# -------------------------------------------------------------------
# Move note (async)
# -------------------------------------------------------------------


async def test_move_note(tmp_vault: Path) -> None:
    old, new = await move_note(
        "Notes/2026-03-01 - Quick Capture.md",
        "Projects",
    )
    assert "Notes" in old
    assert "Projects" in new
    assert (tmp_vault / "Projects" / "2026-03-01 - Quick Capture.md").exists()
    assert not (tmp_vault / "Notes" / "2026-03-01 - Quick Capture.md").exists()


async def test_move_note_missing_raises() -> None:
    with pytest.raises(FileNotFoundError):
        await move_note("Notes/nonexistent.md", "Projects")


async def test_move_note_duplicate_raises(
    tmp_vault: Path,
) -> None:
    (tmp_vault / "APIs" / "2026-03-01 - Quick Capture.md").write_text("dup")
    with pytest.raises(FileExistsError):
        await move_note(
            "Notes/2026-03-01 - Quick Capture.md",
            "APIs",
        )


# -------------------------------------------------------------------
# Backlinks (async)
# -------------------------------------------------------------------


async def test_find_backlinks() -> None:
    backlinks = await find_backlinks("Project Alpha")
    titles = {b["title"] for b in backlinks}
    assert "MOC - Home" in titles
    assert "API Reference" in titles


async def test_find_backlinks_none() -> None:
    assert await find_backlinks("nonexistent note") == []


# -------------------------------------------------------------------
# Structure (async)
# -------------------------------------------------------------------


async def test_get_structure() -> None:
    result = await get_structure()
    assert result["total_notes"] > 0
    assert "Notes" in result["folders"]
    assert "Projects" in result["folders"]
    assert "# Home" in result["moc_home"]


# -------------------------------------------------------------------
# List folders (async)
# -------------------------------------------------------------------


async def test_list_folders_root() -> None:
    result = await list_folders()
    names = {f["name"] for f in result["folders"]}
    assert "Notes" in names
    assert "Projects" in names


async def test_list_folders_subfolder() -> None:
    result = await list_folders("Projects")
    assert result["parent"] == "Projects"


async def test_list_folders_nonexistent() -> None:
    with pytest.raises(NotADirectoryError):
        await list_folders("nonexistent_folder")


# -------------------------------------------------------------------
# Append to note (async)
# -------------------------------------------------------------------


async def test_append_to_note(tmp_vault: Path) -> None:
    note = tmp_vault / "Projects" / "Project Alpha.md"
    await append_to_note(note, "## Appended Section\n\nNew content.")
    text = note.read_text()
    assert "## Appended Section" in text
    assert "New content." in text
    # Original content should still be there
    assert "# Project Alpha" in text


async def test_append_to_note_updates_date(
    tmp_vault: Path,
) -> None:
    note = tmp_vault / "Projects" / "Project Alpha.md"
    await append_to_note(note, "More content", update_date=True)
    text = note.read_text()
    from datetime import date

    assert date.today().isoformat() in text


async def test_append_to_note_missing_raises(
    tmp_vault: Path,
) -> None:
    fake = tmp_vault / "nope.md"
    with pytest.raises(FileNotFoundError):
        await append_to_note(fake, "text")


# -------------------------------------------------------------------
# Search frontmatter (async)
# -------------------------------------------------------------------


async def test_search_frontmatter_by_type() -> None:
    results = await search_frontmatter("type", "project")
    assert len(results) >= 1
    assert all(r["field_value"] == "project" for r in results)


async def test_search_frontmatter_field_exists() -> None:
    results = await search_frontmatter("status")
    assert len(results) >= 1
    assert any(r["title"] == "Project Alpha" for r in results)


async def test_search_frontmatter_scoped() -> None:
    results = await search_frontmatter("type", "resource", folder="APIs")
    assert all("APIs" in r["path"] for r in results)


async def test_search_frontmatter_tags_list() -> None:
    results = await search_frontmatter("tags", "python")
    assert len(results) >= 1
    assert any(r["title"] == "Tagged Note" for r in results)


async def test_search_frontmatter_no_results() -> None:
    results = await search_frontmatter("nonexistent_field", "value")
    assert results == []


# -------------------------------------------------------------------
# Recent notes (async)
# -------------------------------------------------------------------


async def test_get_recent_notes() -> None:
    results = await get_recent_notes(limit=5)
    assert len(results) >= 1
    assert len(results) <= 5
    # Should have required fields
    assert all("modified" in r for r in results)
    assert all("title" in r for r in results)


async def test_get_recent_notes_scoped() -> None:
    results = await get_recent_notes(limit=10, folder="Projects")
    assert all("Projects" in r["path"] for r in results)


async def test_get_recent_notes_ordering() -> None:
    results = await get_recent_notes(limit=100)
    # Dates should be in descending order
    dates = [r["modified"] for r in results]
    assert dates == sorted(dates, reverse=True)


# -------------------------------------------------------------------
# Tags (async)
# -------------------------------------------------------------------


async def test_get_all_tags() -> None:
    tags = await get_all_tags()
    assert "python" in tags
    assert "api" in tags
    assert "testing" in tags


async def test_get_all_tags_sorted() -> None:
    tags = await get_all_tags()
    assert tags == sorted(tags)


async def test_get_all_tags_scoped() -> None:
    tags = await get_all_tags(folder="Projects")
    # Projects folder has no tagged notes
    assert tags == []


async def test_get_all_tags_empty_vault() -> None:
    tags = await get_all_tags(folder="Infrastructure")
    assert tags == []
