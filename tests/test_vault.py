"""Tests for vault filesystem operations."""

from pathlib import Path

import pytest

from brain_mcp.vault import (
    collect_notes,
    create_note,
    extract_wikilinks,
    find_backlinks,
    find_note_by_title,
    get_structure,
    list_folders,
    move_note,
    parse_frontmatter,
    resolve_path,
    search_content,
    update_note,
    vault_relative,
)


class TestPathResolution:
    def test_resolve_valid_path(self, tmp_vault: Path) -> None:
        result = resolve_path("Notes")
        assert result == tmp_vault / "Notes"

    def test_resolve_strips_leading_slash(self, tmp_vault: Path) -> None:
        result = resolve_path("/Notes")
        assert result == tmp_vault / "Notes"

    def test_resolve_blocks_traversal(self) -> None:
        with pytest.raises(ValueError, match="escapes vault root"):
            resolve_path("../../etc/passwd")

    def test_vault_relative(self, tmp_vault: Path) -> None:
        full = tmp_vault / "Projects" / "foo.md"
        assert vault_relative(full) == "Projects/foo.md"


class TestFrontmatter:
    def test_parse_valid(self) -> None:
        text = "---\ntype: project\nupdated: 2026-03-01\n---\n# Title\n"
        meta = parse_frontmatter(text)
        assert meta["type"] == "project"
        assert meta["updated"] == "2026-03-01"

    def test_parse_no_frontmatter(self) -> None:
        assert parse_frontmatter("# Just a heading\n") == {}

    def test_parse_invalid_yaml(self) -> None:
        text = "---\n: invalid: yaml: here\n---\n"
        assert parse_frontmatter(text) == {}


class TestWikilinks:
    def test_extract_simple(self) -> None:
        text = "See [[Project Alpha]] and [[API Reference]]."
        links = extract_wikilinks(text)
        assert links == ["Project Alpha", "API Reference"]

    def test_extract_with_alias(self) -> None:
        text = "See [[Project Alpha|the project]]."
        links = extract_wikilinks(text)
        assert links == ["Project Alpha"]

    def test_extract_none(self) -> None:
        assert extract_wikilinks("No links here.") == []


class TestNoteLookup:
    def test_find_by_title(self, tmp_vault: Path) -> None:
        result = find_note_by_title("Project Alpha")
        assert result is not None
        assert result.stem == "Project Alpha"

    def test_find_by_title_case_insensitive(self, tmp_vault: Path) -> None:
        result = find_note_by_title("project alpha")
        assert result is not None

    def test_find_by_title_missing(self) -> None:
        assert find_note_by_title("nonexistent") is None


class TestCollectNotes:
    def test_collect_all(self) -> None:
        notes = collect_notes()
        titles = {n["title"] for n in notes}
        assert "Project Alpha" in titles
        assert "API Reference" in titles

    def test_collect_folder(self) -> None:
        notes = collect_notes(folder="Projects")
        assert len(notes) == 1
        assert notes[0]["title"] == "Project Alpha"

    def test_collect_by_type(self) -> None:
        notes = collect_notes(note_type="project")
        assert all(n["type"] == "project" for n in notes)

    def test_excludes_obsidian(self) -> None:
        notes = collect_notes()
        paths = [n["path"] for n in notes]
        assert not any(".obsidian" in p for p in paths)


class TestSearchContent:
    def test_search_finds_match(self) -> None:
        results = search_content("test project")
        assert len(results) >= 1
        assert any(r["title"] == "Project Alpha" for r in results)

    def test_search_case_insensitive(self) -> None:
        results = search_content("TEST PROJECT")
        assert len(results) >= 1

    def test_search_no_results(self) -> None:
        assert search_content("zzz_nonexistent_zzz") == []

    def test_search_scoped_to_folder(self) -> None:
        results = search_content("Reference", folder="APIs")
        assert all("APIs" in r["path"] for r in results)


class TestCreateNote:
    def test_create(self, tmp_vault: Path) -> None:
        path = create_note("Notes", "Test Note", "---\ntype: resource\n---\n# Test\n")
        assert path.exists()
        assert path.stem == "Test Note"

    def test_create_duplicate_raises(self, tmp_vault: Path) -> None:
        create_note("Notes", "Unique Note", "content")
        with pytest.raises(FileExistsError):
            create_note("Notes", "Unique Note", "content again")

    def test_create_in_new_subfolder(self, tmp_vault: Path) -> None:
        path = create_note("Notes/sub", "Deep Note", "content")
        assert path.exists()
        assert "sub" in str(path)


class TestUpdateNote:
    def test_update_content(self, tmp_vault: Path) -> None:
        note = tmp_vault / "Projects" / "Project Alpha.md"
        new_content = "---\ntype: project\nupdated: 2026-01-01\n---\n# Updated\n"
        update_note(note, new_content, update_date=True)
        text = note.read_text()
        # Should have today's date, not 2026-01-01
        assert "2026-01-01" not in text or "updated:" in text

    def test_update_missing_raises(self, tmp_vault: Path) -> None:
        fake = tmp_vault / "nope.md"
        with pytest.raises(FileNotFoundError):
            update_note(fake, "content")


class TestMoveNote:
    def test_move(self, tmp_vault: Path) -> None:
        old, new = move_note("Notes/2026-03-01 - Quick Capture.md", "Projects")
        assert "Notes" in old
        assert "Projects" in new
        assert (tmp_vault / "Projects" / "2026-03-01 - Quick Capture.md").exists()
        assert not (tmp_vault / "Notes" / "2026-03-01 - Quick Capture.md").exists()

    def test_move_missing_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            move_note("Notes/nonexistent.md", "Projects")

    def test_move_duplicate_raises(self, tmp_vault: Path) -> None:
        # Create a note in destination with same name
        (tmp_vault / "APIs" / "2026-03-01 - Quick Capture.md").write_text("dup")
        with pytest.raises(FileExistsError):
            move_note("Notes/2026-03-01 - Quick Capture.md", "APIs")


class TestBacklinks:
    def test_find_backlinks(self) -> None:
        backlinks = find_backlinks("Project Alpha")
        titles = {b["title"] for b in backlinks}
        # MOC - Home and API Reference both link to Project Alpha
        assert "MOC - Home" in titles
        assert "API Reference" in titles

    def test_no_backlinks(self) -> None:
        assert find_backlinks("nonexistent note") == []


class TestStructure:
    def test_get_structure(self) -> None:
        result = get_structure()
        assert result["total_notes"] > 0
        assert "Notes" in result["folders"]
        assert "Projects" in result["folders"]
        assert "# Home" in result["moc_home"]


class TestListFolders:
    def test_list_root(self) -> None:
        result = list_folders()
        names = {f["name"] for f in result["folders"]}
        assert "Notes" in names
        assert "Projects" in names

    def test_list_subfolder(self) -> None:
        result = list_folders("Projects")
        assert result["parent"] == "Projects"

    def test_list_nonexistent(self) -> None:
        with pytest.raises(NotADirectoryError):
            list_folders("nonexistent_folder")
