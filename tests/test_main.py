"""Tests for playable-game startup options."""

from __future__ import annotations

from pathlib import Path

from rts_nano.main import MAPS_DIR, _resolve_game_map_path


def test_packaged_map_name_resolves_to_maps_directory() -> None:
    assert _resolve_game_map_path(Path("map_spec_02.json")) == MAPS_DIR / "map_spec_02.json"


def test_existing_explicit_map_path_is_preserved(tmp_path: Path) -> None:
    path = tmp_path / "custom.json"
    path.write_text("{}", encoding="utf-8")

    assert _resolve_game_map_path(path) == path
