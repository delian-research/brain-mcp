"""Shared test fixtures for brain-mcp."""

from pathlib import Path

import pytest


@pytest.fixture()
def tmp_vault(tmp_path: Path) -> Path:
    """Create a temporary vault structure for testing."""
    # Canonical folders
    for folder in ["Notes", "Projects", "APIs", "Infrastructure", "Tooling", "Workflows"]:
        (tmp_path / folder).mkdir()

    # MOC - Home
    (tmp_path / "MOC - Home.md").write_text(
        "---\ntype: moc\n---\n# Home\n\n- [[Project Alpha]]\n- [[API Reference]]\n",
        encoding="utf-8",
    )

    # Sample notes
    (tmp_path / "Notes" / "2026-03-01 - Quick Capture.md").write_text(
        "---\ntype: resource\nupdated: 2026-03-01\n---\n# Quick Capture\n\nSome fleeting idea.\n",
        encoding="utf-8",
    )

    (tmp_path / "Projects" / "Project Alpha.md").write_text(
        "---\ntype: project\nupdated: 2026-03-10\nstatus: active\n---\n"
        "# Project Alpha\n\nA test project.\n\n## Related\n\n- [[API Reference]]\n",
        encoding="utf-8",
    )

    (tmp_path / "APIs" / "API Reference.md").write_text(
        "---\ntype: resource\nupdated: 2026-02-15\n---\n# API Reference\n\n"
        "Details about the API.\n\n## See Also\n\n- [[Project Alpha]]\n",
        encoding="utf-8",
    )

    # .obsidian folder (should be excluded)
    obsidian = tmp_path / ".obsidian"
    obsidian.mkdir()
    (obsidian / "config.md").write_text("internal config", encoding="utf-8")

    return tmp_path


@pytest.fixture(autouse=True)
def _set_vault_path(tmp_vault: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the vault module at the temp vault for every test."""
    monkeypatch.setenv("BRAIN_VAULT_PATH", str(tmp_vault))
    # Reload vault config so it picks up the new path
    import brain_mcp.vault as vault_mod

    monkeypatch.setattr(vault_mod, "VAULT_PATH", str(tmp_vault))
    monkeypatch.setattr(vault_mod, "VAULT_ROOT", tmp_vault)
