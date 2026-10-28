"""Tests for playable-game startup options."""

from __future__ import annotations

from pathlib import Path

import pytest

from rts_nano.application import MatchMode
from rts_nano.main import MAPS_DIR, _parse_args, _resolve_game_map_path


def test_packaged_map_name_resolves_to_maps_directory() -> None:
    assert _resolve_game_map_path(Path("map_spec_02.json")) == MAPS_DIR / "map_spec_02.json"


def test_existing_explicit_map_path_is_preserved(tmp_path: Path) -> None:
    path = tmp_path / "custom.json"
    path.write_text("{}", encoding="utf-8")

    assert _resolve_game_map_path(path) == path


def test_startup_defaults_to_play_and_accepts_spectator_with_a_map() -> None:
    assert _parse_args([]).mode == MatchMode.PLAY
    options = _parse_args(["--mode", "spectate", "--map", "map_spec_03.json"])
    assert options.mode == MatchMode.SPECTATE
    assert options.map_path == MAPS_DIR / "map_spec_03.json"


def test_unknown_mode_is_rejected_at_startup() -> None:
    with pytest.raises(SystemExit) as error:
        _parse_args(["--mode", "unknown"])
    assert error.value.code == 2
