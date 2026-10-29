"""Repeat full two-bot application matches and record deterministic acceptance evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from pathlib import Path
from typing import cast

from rts_nano.application import GameSession, MatchController, MatchMode
from rts_nano.game.observations import EntityIdRegistry, build_observation
from rts_nano.map_schema import load_map_settings
from rts_nano.simulation.entities import TeamColor


def _require(condition: object, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _digest(match: MatchController) -> str:
    snapshot = build_observation(match.session, match.session.state.tick_count, EntityIdRegistry())
    # Selection and view team are presentation state; all gameplay fields remain.
    payload = snapshot.to_dict()
    payload.pop("current_team")
    for entity in cast("tuple[dict[str, object], ...]", payload["entities"]):
        entity.pop("selected")
    payload["bot_memory"] = [
        {"decisions": bot._frame, "enemy_base": bot.known_enemy_base_position, "vision": bot._vision.grid}
        for bot in match._bots
    ]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def run_match(map_path: Path) -> dict[str, object]:
    """Advance real baseline bots to a natural result or the ordinary game deadline."""
    match = MatchController(GameSession(load_map_settings(map_path)), MatchMode.SPECTATE)
    game = match.session
    army_seen = dict.fromkeys((TeamColor.BLUE, TeamColor.RED), False)
    checkpoints: dict[int, str] = {}
    attacks = 0
    started = time.perf_counter()
    limit = game.state.match_rules.max_frames
    if limit is None:
        raise RuntimeError("Acceptance requires a bounded game")
    for _ in range(limit):
        match.step()
        attacks += len(game.recent_attacks)
        for team in army_seen:
            army_seen[team] |= any(str(unit.content_id) != "peasant" for unit in game.units_for_team(team))
        if game.state.tick_count % 6000 == 0:
            checkpoints[game.state.tick_count] = _digest(match)
            print(f"PROGRESS {map_path.name} tick={game.state.tick_count}", flush=True)
        if game.game_over_message is not None:
            break
    elapsed = time.perf_counter() - started
    _require(game.game_over_message is not None, "The match did not reach a bounded result")
    _require(all(army_seen.values()), "Both bots must demonstrate military production")
    _require(attacks > 0, "The match never reached combat")
    checkpoints[game.state.tick_count] = _digest(match)
    restarted = match.restart()
    _require(restarted.mode == MatchMode.SPECTATE and len(restarted._bots) == 2, "Restart lost participants")
    _require(
        restarted.session.state.tick_count == 0 and restarted.session.game_over_message is None,
        "Restart retained result",
    )
    _require(
        all(bot._frame == 0 and bot.known_enemy_base_position is None for bot in restarted._bots),
        "Restart retained bot memory",
    )
    return {
        "map": map_path.name,
        "ticks": game.state.tick_count,
        "result": game.game_over_message,
        "reason": game.state.match_end_reason,
        "attacks_landed": attacks,
        "both_armies_seen": all(army_seen.values()),
        "checkpoints": checkpoints,
        "elapsed_seconds": round(elapsed, 4),
        "ticks_per_second": round(game.state.tick_count / elapsed, 2),
        "restart": "PASS",
    }


def main() -> None:
    """Check repeated full matches on all shipped v3 maps."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--map", type=int, choices=(1, 2, 3))
    parser.add_argument("--output", type=Path, default=Path("tmp/bot-spectator.json"))
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    results = []
    for index in (args.map,) if args.map else (1, 2, 3):
        map_path = Path(f"src/rts_nano/maps/map_spec_{index:02}.json")
        reference = None
        for repeat in range(args.repeats):
            result = run_match(map_path)
            if reference is not None:
                _require(result["checkpoints"] == reference, "Fresh bot matches diverged")
            reference = result["checkpoints"]
            results.append(result)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(
                    {
                        "platform": platform.platform(),
                        "processor": platform.processor(),
                        "python": platform.python_version(),
                        "runs": results,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            print(
                f"PASS {map_path.name} repeat={repeat + 1} tick={result['ticks']} result={result['result']} wall={result['elapsed_seconds']}s",
                flush=True,
            )


if __name__ == "__main__":
    main()
