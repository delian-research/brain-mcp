"""Vault filesystem operations for the Brain Obsidian vault.

Provides path resolution, note reading, searching, and metadata extraction.
All vault access goes through this module to enforce path safety.
"""

import logging
import os
import re
from datetime import date
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger("brain_mcp.vault")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

VAULT_PATH = os.environ.get(
    "BRAIN_VAULT_PATH",
    os.path.expanduser("~/Documents/Projects/Obsidian/Brain"),
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


# ---------------------------------------------------------------------------
# Path utilities
# ---------------------------------------------------------------------------


def resolve_path(relative: str) -> Path:
    """Resolve a vault-relative path, preventing directory traversal."""
    cleaned = relative.lstrip("/").lstrip("\\")
    full = (VAULT_ROOT / cleaned).resolve()
    if not str(full).startswith(str(VAULT_ROOT.resolve())):
        raise ValueError(f"Path escapes vault root: {relative}")
    return full


def vault_relative(absolute: Path) -> str:
    """Return vault-relative path string."""
    try:
        return str(absolute.resolve().relative_to(VAULT_ROOT.resolve()))
    except ValueError:
        return str(absolute)


# ---------------------------------------------------------------------------
# Frontmatter & wikilink parsing
# ---------------------------------------------------------------------------


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


def build_frontmatter(meta: dict) -> str:
    """Build a YAML frontmatter block string."""
    lines = ["---"]
    for key, value in meta.items():
        lines.append(f"{key}: {value}")
    lines.append("---")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Note lookup
# ---------------------------------------------------------------------------


def find_note_by_title(title: str) -> Optional[Path]:
    """Find a note by its title (filename without .md), case-insensitive."""
    title_lower = title.lower().strip()
    for p in VAULT_ROOT.rglob("*.md"):
        if p.stem.lower() == title_lower:
            return p
    return None


def _is_excluded(path: Path) -> bool:
    """Check if a path should be excluded from vault operations."""
    return ".obsidian" in path.parts


# ---------------------------------------------------------------------------
# Collection & search
# ---------------------------------------------------------------------------


def collect_notes(
    folder: Optional[str] = None,
    note_type: Optional[str] = None,
    recursive: bool = True,
) -> list[dict]:
    """Collect note metadata from the vault."""
    root = resolve_path(folder) if folder else VAULT_ROOT
    if not root.is_dir():
        return []

    pattern = "**/*.md" if recursive else "*.md"
    results = []
    for p in root.glob(pattern):
        if _is_excluded(p):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        meta = parse_frontmatter(text)
        if note_type and meta.get("type") != note_type:
            continue
        results.append(
            {
                "path": vault_relative(p),
                "title": p.stem,
                "type": meta.get("type", "unknown"),
                "updated": str(meta.get("updated", "")),
                "status": meta.get("status", ""),
            }
        )
    results.sort(key=lambda n: n["path"])
    return results


def search_content(
    query: str,
    folder: Optional[str] = None,
    case_sensitive: bool = False,
) -> list[dict]:
    """Full-text search across vault notes, returning matching snippets."""
    root = resolve_path(folder) if folder else VAULT_ROOT
    flags = 0 if case_sensitive else re.IGNORECASE
    pattern = re.compile(re.escape(query), flags)
    results = []

    for p in root.rglob("*.md"):
        if _is_excluded(p):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        matches = list(pattern.finditer(text))
        if not matches:
            continue

        lines = text.splitlines()
        snippets = []
        for m in matches[:5]:
            line_start = text.count("\n", 0, m.start())
            context_start = max(0, line_start - 1)
            context_end = min(len(lines), line_start + 2)
            snippet = "\n".join(lines[context_start:context_end])
            snippets.append(snippet.strip())

        meta = parse_frontmatter(text)
        results.append(
            {
                "path": vault_relative(p),
                "title": p.stem,
                "type": meta.get("type", "unknown"),
                "match_count": len(matches),
                "snippets": snippets,
            }
        )

    results.sort(key=lambda r: r["match_count"], reverse=True)
    return results


# ---------------------------------------------------------------------------
# Write operations
# ---------------------------------------------------------------------------


def create_note(folder: str, title: str, content: str) -> Path:
    """Create a new note file, returning the path. Raises if it already exists."""
    folder_path = resolve_path(folder)
    folder_path.mkdir(parents=True, exist_ok=True)

    filename = title if title.endswith(".md") else f"{title}.md"
    target = folder_path / filename

    if target.exists():
        raise FileExistsError(f"Note already exists at {vault_relative(target)}")

    target.write_text(content, encoding="utf-8")
    logger.info("Created note: %s", vault_relative(target))
    return target


def update_note(path: Path, content: str, update_date: bool = True) -> Path:
    """Overwrite a note's content. Optionally stamps today's date."""
    if not path.exists():
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

    path.write_text(content, encoding="utf-8")
    logger.info("Updated note: %s", vault_relative(path))
    return path


def move_note(source_rel: str, dest_folder: str) -> tuple[str, str]:
    """Move a note to a new folder. Returns (old_path, new_path) as vault-relative strings."""
    source = resolve_path(source_rel)
    if not source.exists():
        raise FileNotFoundError(f"Source not found at {source_rel}")

    dest_dir = resolve_path(dest_folder)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / source.name

    if dest.exists():
        raise FileExistsError(f"A note with the same name already exists at {vault_relative(dest)}")

    source.rename(dest)
    logger.info("Moved note: %s -> %s", source_rel, vault_relative(dest))
    return source_rel, vault_relative(dest)


def find_backlinks(title: str) -> list[dict]:
    """Find all notes that link to a given note via [[wikilinks]]."""
    title_lower = title.lower()
    backlinks = []

    for p in VAULT_ROOT.rglob("*.md"):
        if _is_excluded(p):
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        links = extract_wikilinks(text)
        if any(link.lower() == title_lower for link in links):
            meta = parse_frontmatter(text)
            backlinks.append(
                {
                    "path": vault_relative(p),
                    "title": p.stem,
                    "type": meta.get("type", "unknown"),
                }
            )

    return sorted(backlinks, key=lambda b: b["path"])


def get_structure() -> dict:
    """Get high-level vault structure with folder stats and MOC content."""
    folders: dict[str, int] = {}
    total = 0

    for folder_name in CANONICAL_FOLDERS:
        folder_path = VAULT_ROOT / folder_name
        if folder_path.is_dir():
            count = sum(1 for _ in folder_path.rglob("*.md"))
            folders[folder_name] = count
            total += count

    moc_home = VAULT_ROOT / "MOC - Home.md"
    moc_content = ""
    if moc_home.exists():
        moc_content = moc_home.read_text(encoding="utf-8", errors="replace")

    return {
        "vault_path": str(VAULT_ROOT),
        "total_notes": total,
        "folders": folders,
        "moc_home": moc_content,
    }


def list_folders(folder: Optional[str] = None) -> dict:
    """List subdirectories and their note counts."""
    root = resolve_path(folder) if folder else VAULT_ROOT
    if not root.is_dir():
        raise NotADirectoryError(f"Not a directory: {folder}")

    dirs = []
    for item in sorted(root.iterdir()):
        if item.is_dir() and item.name != ".obsidian" and not item.name.startswith("."):
            count = sum(1 for _ in item.rglob("*.md"))
            dirs.append({"name": item.name, "note_count": count})

    return {"parent": folder or "/", "folders": dirs}
