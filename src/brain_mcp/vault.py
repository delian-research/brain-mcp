"""Vault filesystem operations for the Brain Obsidian vault.

Provides path resolution, note reading, searching, and metadata
extraction. All vault access goes through this module to enforce
path safety.
"""

import logging
import os
import re
from datetime import date
from pathlib import Path
from typing import Optional

import anyio
import yaml

logger = logging.getLogger("brain_mcp.vault")

__all__ = [
    "CANONICAL_FOLDERS",
    "NOTE_TYPES",
    "get_vault_root",
    "resolve_path",
    "vault_relative",
    "parse_frontmatter",
    "extract_wikilinks",
    "find_note_by_title",
    "collect_notes",
    "search_content",
    "create_note",
    "update_note",
    "move_note",
    "find_backlinks",
    "get_structure",
    "list_folders",
    "append_to_note",
    "search_frontmatter",
    "get_recent_notes",
    "get_all_tags",
]

# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------

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

_vault_root: Optional[Path] = None


def get_vault_root() -> Path:
    """Return the vault root path, lazily initialised."""
    global _vault_root  # noqa: PLW0603
    if _vault_root is None:
        vault_path = os.environ.get(
            "BRAIN_VAULT_PATH",
            os.path.expanduser("~/Documents/Projects/Obsidian/Brain"),
        )
        _vault_root = Path(vault_path)
    return _vault_root


def _reset_vault_root() -> None:
    """Reset cached vault root (for testing)."""
    global _vault_root  # noqa: PLW0603
    _vault_root = None


# -------------------------------------------------------------------
# Path utilities
# -------------------------------------------------------------------


def resolve_path(relative: str) -> Path:
    """Resolve a vault-relative path, preventing traversal."""
    root = get_vault_root()
    cleaned = relative.lstrip("/").lstrip("\\")
    full = (root / cleaned).resolve()
    if not str(full).startswith(str(root.resolve())):
        raise ValueError(f"Path escapes vault root: {relative}")
    return full


def vault_relative(absolute: Path) -> str:
    """Return vault-relative path string."""
    try:
        return str(absolute.resolve().relative_to(get_vault_root().resolve()))
    except ValueError:
        return str(absolute)


# -------------------------------------------------------------------
# Frontmatter & wikilink parsing
# -------------------------------------------------------------------


def parse_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter from a markdown string."""
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not match:
        return {}
    try:
        raw = yaml.safe_load(match.group(1)) or {}
        return {k: str(v) if isinstance(v, date) else v for k, v in raw.items()}
    except yaml.YAMLError:
        return {}


def extract_wikilinks(text: str) -> list[str]:
    """Extract [[wikilink]] targets from markdown text."""
    return re.findall(r"\[\[([^\]|]+?)(?:\|[^\]]*?)?\]\]", text)


# -------------------------------------------------------------------
# Note lookup
# -------------------------------------------------------------------


async def find_note_by_title(
    title: str,
) -> Optional[Path]:
    """Find a note by title (filename sans .md), case-insensitive."""
    title_lower = title.lower().strip()
    root = anyio.Path(get_vault_root())
    async for p in root.rglob("*.md"):
        if Path(p).stem.lower() == title_lower:
            return Path(p)
    return None


def _is_excluded(path: Path) -> bool:
    """Check if a path should be excluded from vault ops."""
    return ".obsidian" in path.parts


# -------------------------------------------------------------------
# Collection & search
# -------------------------------------------------------------------


async def collect_notes(
    folder: Optional[str] = None,
    note_type: Optional[str] = None,
    recursive: bool = True,
) -> list[dict]:
    """Collect note metadata from the vault."""
    root = resolve_path(folder) if folder else get_vault_root()
    aroot = anyio.Path(root)
    if not await aroot.is_dir():
        return []

    pattern = "**/*.md" if recursive else "*.md"
    results = []
    async for p in aroot.glob(pattern):
        pp = Path(p)
        if _is_excluded(pp):
            continue
        text = await anyio.Path(p).read_text(encoding="utf-8", errors="replace")
        meta = parse_frontmatter(text)
        if note_type and meta.get("type") != note_type:
            continue
        results.append(
            {
                "path": vault_relative(pp),
                "title": pp.stem,
                "type": meta.get("type", "unknown"),
                "updated": str(meta.get("updated", "")),
                "status": meta.get("status", ""),
            }
        )
    results.sort(key=lambda n: n["path"])
    return results


async def search_content(
    query: str,
    folder: Optional[str] = None,
    case_sensitive: bool = False,
) -> list[dict]:
    """Full-text search across vault notes with snippets."""
    root = resolve_path(folder) if folder else get_vault_root()
    flags = 0 if case_sensitive else re.IGNORECASE
    pat = re.compile(re.escape(query), flags)
    results = []

    async for p in anyio.Path(root).rglob("*.md"):
        pp = Path(p)
        if _is_excluded(pp):
            continue
        text = await anyio.Path(p).read_text(encoding="utf-8", errors="replace")
        matches = list(pat.finditer(text))
        if not matches:
            continue

        lines = text.splitlines()
        snippets = []
        for m in matches[:5]:
            line_start = text.count("\n", 0, m.start())
            ctx_start = max(0, line_start - 1)
            ctx_end = min(len(lines), line_start + 2)
            snippet = "\n".join(lines[ctx_start:ctx_end])
            snippets.append(snippet.strip())

        meta = parse_frontmatter(text)
        results.append(
            {
                "path": vault_relative(pp),
                "title": pp.stem,
                "type": meta.get("type", "unknown"),
                "match_count": len(matches),
                "snippets": snippets,
            }
        )

    results.sort(key=lambda r: r["match_count"], reverse=True)
    return results


# -------------------------------------------------------------------
# Write operations
# -------------------------------------------------------------------


async def create_note(folder: str, title: str, content: str) -> Path:
    """Create a new note file. Raises if it already exists."""
    folder_path = resolve_path(folder)
    await anyio.Path(folder_path).mkdir(parents=True, exist_ok=True)

    filename = title if title.endswith(".md") else f"{title}.md"
    target = folder_path / filename

    if await anyio.Path(target).exists():
        raise FileExistsError(f"Note already exists at {vault_relative(target)}")

    await anyio.Path(target).write_text(content, encoding="utf-8")
    logger.info("Created note: %s", vault_relative(target))
    return target


async def update_note(path: Path, content: str, update_date: bool = True) -> Path:
    """Overwrite a note's content. Optionally stamps today."""
    if not await anyio.Path(path).exists():
        raise FileNotFoundError(f"Note not found at {vault_relative(path)}")

    if update_date:
        meta = parse_frontmatter(content)
        if meta:
            today = date.today().isoformat()
            content = re.sub(
                r"(updated:\s*)[\d-]+",
                f"\\g<1>{today}",
                content,
                count=1,
            )

    await anyio.Path(path).write_text(content, encoding="utf-8")
    logger.info("Updated note: %s", vault_relative(path))
    return path


async def move_note(source_rel: str, dest_folder: str) -> tuple[str, str]:
    """Move a note to a new folder.

    Returns (old_path, new_path) as vault-relative strings.
    """
    source = resolve_path(source_rel)
    if not await anyio.Path(source).exists():
        raise FileNotFoundError(f"Source not found at {source_rel}")

    dest_dir = resolve_path(dest_folder)
    await anyio.Path(dest_dir).mkdir(parents=True, exist_ok=True)
    dest = dest_dir / source.name

    if await anyio.Path(dest).exists():
        raise FileExistsError(
            f"A note with the same name already exists at {vault_relative(dest)}"
        )

    await anyio.Path(source).rename(dest)
    logger.info(
        "Moved note: %s -> %s",
        source_rel,
        vault_relative(dest),
    )
    return source_rel, vault_relative(dest)


async def find_backlinks(title: str) -> list[dict]:
    """Find all notes linking to a note via [[wikilinks]]."""
    title_lower = title.lower()
    backlinks = []

    async for p in anyio.Path(get_vault_root()).rglob("*.md"):
        pp = Path(p)
        if _is_excluded(pp):
            continue
        text = await anyio.Path(p).read_text(encoding="utf-8", errors="replace")
        links = extract_wikilinks(text)
        if any(link.lower() == title_lower for link in links):
            meta = parse_frontmatter(text)
            backlinks.append(
                {
                    "path": vault_relative(pp),
                    "title": pp.stem,
                    "type": meta.get("type", "unknown"),
                }
            )

    return sorted(backlinks, key=lambda b: b["path"])


async def get_structure() -> dict:
    """Get vault structure with folder stats and MOC."""
    root = get_vault_root()
    folders: dict[str, int] = {}
    total = 0

    for folder_name in CANONICAL_FOLDERS:
        folder_path = root / folder_name
        if await anyio.Path(folder_path).is_dir():
            count = 0
            async for _ in anyio.Path(folder_path).rglob("*.md"):
                count += 1
            folders[folder_name] = count
            total += count

    moc_home = root / "MOC - Home.md"
    moc_content = ""
    if await anyio.Path(moc_home).exists():
        moc_content = await anyio.Path(moc_home).read_text(
            encoding="utf-8", errors="replace"
        )

    return {
        "vault_path": str(root),
        "total_notes": total,
        "folders": folders,
        "moc_home": moc_content,
    }


async def list_folders(
    folder: Optional[str] = None,
) -> dict:
    """List subdirectories and their note counts."""
    root = resolve_path(folder) if folder else get_vault_root()
    if not await anyio.Path(root).is_dir():
        raise NotADirectoryError(f"Not a directory: {folder}")

    dirs = []
    items = []
    async for item in anyio.Path(root).iterdir():
        items.append(Path(item))
    for item in sorted(items):
        if (
            await anyio.Path(item).is_dir()
            and item.name != ".obsidian"
            and not item.name.startswith(".")
        ):
            count = 0
            async for _ in anyio.Path(item).rglob("*.md"):
                count += 1
            dirs.append({"name": item.name, "note_count": count})

    return {"parent": folder or "/", "folders": dirs}


# -------------------------------------------------------------------
# Append, frontmatter search, recent notes, tags
# -------------------------------------------------------------------


async def append_to_note(
    path: Path,
    text: str,
    update_date: bool = True,
) -> Path:
    """Append text to an existing note.

    Raises FileNotFoundError if the note doesn't exist.
    """
    apath = anyio.Path(path)
    if not await apath.exists():
        raise FileNotFoundError(f"Note not found at {vault_relative(path)}")

    existing = await apath.read_text(encoding="utf-8", errors="replace")
    separator = "\n" if existing.endswith("\n") else "\n\n"
    new_content = existing + separator + text

    if update_date:
        meta = parse_frontmatter(new_content)
        if meta and "updated" in meta:
            today = date.today().isoformat()
            new_content = re.sub(
                r"(updated:\s*)[\d-]+",
                f"\\g<1>{today}",
                new_content,
                count=1,
            )

    await apath.write_text(new_content, encoding="utf-8")
    logger.info("Appended to note: %s", vault_relative(path))
    return path


async def search_frontmatter(
    field: str,
    value: Optional[str] = None,
    folder: Optional[str] = None,
) -> list[dict]:
    """Search notes by frontmatter field/value.

    If *value* is ``None``, returns notes where *field* exists.
    """
    root = resolve_path(folder) if folder else get_vault_root()
    results: list[dict] = []

    async for p in anyio.Path(root).rglob("*.md"):
        pp = Path(p)
        if _is_excluded(pp):
            continue
        text = await anyio.Path(p).read_text(encoding="utf-8", errors="replace")
        meta = parse_frontmatter(text)
        if field not in meta:
            continue

        field_val = meta[field]
        if value is not None:
            # Support comma-separated tags/lists
            if isinstance(field_val, list):
                if not any(str(v).lower() == value.lower() for v in field_val):
                    continue
            elif str(field_val).lower() != value.lower():
                continue

        results.append(
            {
                "path": vault_relative(pp),
                "title": pp.stem,
                "type": meta.get("type", "unknown"),
                "field": field,
                "field_value": field_val,
            }
        )

    results.sort(key=lambda r: r["path"])
    return results


async def get_recent_notes(
    limit: int = 10,
    folder: Optional[str] = None,
) -> list[dict]:
    """Return recently modified notes sorted by mtime (newest first)."""
    root = resolve_path(folder) if folder else get_vault_root()
    notes: list[tuple[float, Path]] = []

    async for p in anyio.Path(root).rglob("*.md"):
        pp = Path(p)
        if _is_excluded(pp):
            continue
        stat = await anyio.Path(p).stat()
        notes.append((stat.st_mtime, pp))

    notes.sort(key=lambda t: t[0], reverse=True)
    trimmed = notes[:limit]

    results: list[dict] = []
    for mtime, pp in trimmed:
        text = await anyio.Path(pp).read_text(encoding="utf-8", errors="replace")
        meta = parse_frontmatter(text)
        results.append(
            {
                "path": vault_relative(pp),
                "title": pp.stem,
                "type": meta.get("type", "unknown"),
                "modified": date.fromtimestamp(mtime).isoformat(),
            }
        )
    return results


async def get_all_tags(
    folder: Optional[str] = None,
) -> list[str]:
    """Collect all unique tags from frontmatter across the vault."""
    root = resolve_path(folder) if folder else get_vault_root()
    tags: set[str] = set()

    async for p in anyio.Path(root).rglob("*.md"):
        pp = Path(p)
        if _is_excluded(pp):
            continue
        text = await anyio.Path(p).read_text(encoding="utf-8", errors="replace")
        meta = parse_frontmatter(text)
        raw = meta.get("tags")
        if isinstance(raw, list):
            tags.update(str(t) for t in raw)
        elif isinstance(raw, str):
            # Support comma-separated: "foo, bar"
            tags.update(t.strip() for t in raw.split(",") if t.strip())

    return sorted(tags)
