"""Tests for playable-game startup options."""

from __future__ import annotations

from pathlib import Path

import pygame
import pytest

from rts_nano import main as application
from rts_nano.application import GameSession, MatchController, MatchMode
from rts_nano.game.ui.input_controller import RESTART_MATCH_EVENT
from rts_nano.main import MAPS_DIR, LaunchOptions, _parse_args, _resolve_game_map_path


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


def test_main_composes_spectator_restart_and_stops_immediately_on_quit(monkeypatch: pytest.MonkeyPatch) -> None:
    matches: list[MatchController] = []

    class RecordingMatch(MatchController):
        def __init__(self, session: GameSession, mode: MatchMode = MatchMode.PLAY) -> None:
            super().__init__(session, mode)
            matches.append(self)

    batches = iter(
        [
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_p, mod=0)],
            [pygame.event.Event(pygame.KEYDOWN, key=pygame.K_p, mod=0)],
            [pygame.event.Event(RESTART_MATCH_EVENT)],
            [pygame.event.Event(pygame.QUIT)],
        ]
    )
    monkeypatch.setattr(
        application, "_parse_args", lambda: LaunchOptions(MAPS_DIR / "map_spec_01.json", MatchMode.SPECTATE)
    )
    monkeypatch.setattr(application, "_create_display", lambda **_kwargs: (pygame.Surface((1280, 720)), False))
    monkeypatch.setattr(application, "MatchController", RecordingMatch)
    monkeypatch.setattr(pygame.display, "flip", lambda: None)
    monkeypatch.setattr(pygame.event, "get", lambda: next(batches))
    with pytest.raises(SystemExit):
        application.main()

    assert len(matches) == 2
    assert all(match.mode == MatchMode.SPECTATE and len(match._bots) == 2 for match in matches)
    assert [match.session.state.tick_count for match in matches] == [1, 1]
    assert all(bot._frame == 1 for match in matches for bot in match._bots)
