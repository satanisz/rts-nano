"""Architectural guardrails introduced before the core-layer migration."""

from __future__ import annotations

import ast
from pathlib import Path

CORE_ROOT = Path("src/rts_nano/game")
CONTENT_ROOT = Path("src/rts_nano/content")

# Sprint S0 records existing debt rather than pretending the core is already pure.
# Every later sprint must shrink this exact allowlist; Sprint S4 removes it.
APPROVED_DIRECT_PYGAME_DEBT = {
    "assets/entities/base_entities.py",
    "manager.py",
    "terrain.py",
}


def _imports_pygame(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import) and any(alias.name == "pygame" for alias in node.names):
            return True
        if isinstance(node, ast.ImportFrom) and node.module == "pygame":
            return True
    return False


def test_direct_pygame_core_debt_is_explicit_and_cannot_grow() -> None:
    """New direct Pygame dependencies cannot enter non-UI game modules."""
    actual = {
        path.relative_to(CORE_ROOT).as_posix()
        for path in CORE_ROOT.rglob("*.py")
        if "ui" not in path.relative_to(CORE_ROOT).parts and _imports_pygame(path)
    }

    assert actual == APPROVED_DIRECT_PYGAME_DEBT


def test_content_registry_has_no_pygame_dependency() -> None:
    """Static definitions and validation stay safe for headless imports."""
    assert not any(_imports_pygame(path) for path in CONTENT_ROOT.rglob("*.py"))
