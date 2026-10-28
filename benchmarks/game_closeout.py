"""Reproducible C4 gameplay acceptance, timing, and active-memory evidence.

Run from the repository root with ``python benchmarks/game_closeout.py``.
This is a controlled test driver, not a playable AI or an ML adapter.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import math
import platform
import time
import tracemalloc
from pathlib import Path
from typing import TYPE_CHECKING, cast

from rts_nano.game.match import MatchRules
from rts_nano.game.observations import EntityIdRegistry, build_observation
from rts_nano.headless import HeadlessSimulation
from rts_nano.map_schema import load_map_settings
from rts_nano.simulation.entities import TeamColor

if TYPE_CHECKING:
    from rts_nano.application import GameSession
    from rts_nano.simulation.entities.base import Building, Unit
    from rts_nano.simulation.entities.units import CasterUnit, Peasant

PAIRINGS = (("AEGIS", "RUST"), ("RUST", "AEGIS"), ("AEGIS", "AEGIS"), ("RUST", "RUST"))


def _require(condition: object, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def _gather(game: GameSession, team: TeamColor, worker: Peasant, kind: str) -> None:
    nodes = game.state.resources_by_content(kind)
    if nodes:
        target = min(nodes, key=lambda node: math.dist(worker.get_center(), node.get_center()))
        game.issue_gather_order(team, target, [worker])


def _build(game: GameSession, team: TeamColor, builder: Peasant, content_id: str) -> Building:
    base = game.bases_for_team(team)[0]
    sign = 1 if team == TeamColor.BLUE else -1
    candidates = [
        (base.x + sign * dx, base.y + sign * dy)
        for dx in range(-240, 241, 80)
        for dy in range(-240, 241, 80)
        if dx or dy
    ]
    candidates.sort(key=lambda point: (math.dist(point, base.get_center()), point[1] * sign, point[0] * sign))
    for point in candidates:
        if game.construction.can_start_construction(builder, content_id, point)[0] and game.movement.find_unit_path(
            builder, point
        ):
            _require(game.construct_building(builder, content_id, point), f"Placement failed: {team}/{content_id}")
            return cast("Building", game.state.entities_by_content_id(content_id, team=team)[-1])
    raise RuntimeError(f"No reachable placement: {team}/{content_id}")


def run_scenario(
    map_index: int,
    factions: tuple[str, str],
    *,
    reverse_commands: bool = False,
    frames: int = 18_000,
    trace_memory: bool = False,
) -> dict[str, object]:
    """Earn the entire tech build, cast, fight, reach a result, and restart both sides."""
    path = Path(f"src/rts_nano/maps/map_spec_{map_index:02}.json")
    settings = load_map_settings(path)
    settings["Blue"]["faction_id"], settings["Red"]["faction_id"] = factions
    simulation = HeadlessSimulation.from_settings(settings, match_rules=MatchRules(max_frames=frames))
    game = simulation.manager
    teams = (TeamColor.RED, TeamColor.BLUE) if reverse_commands else (TeamColor.BLUE, TeamColor.RED)
    workers = {team: cast("list[Peasant]", game.state.entities_by_content_id("peasant", team=team)) for team in teams}
    stages = dict.fromkeys(teams, 0)
    jobs: dict[TeamColor, Building] = {}
    milestones: dict[str, dict[str, int]] = {team.value: {} for team in teams}
    center = json.loads(path.read_text(encoding="utf-8"))["anchors"]["center"]
    for team in teams:
        for index, worker in enumerate(workers[team]):
            _gather(game, team, worker, "gold" if index == 2 else "wood")
    arena_tick: int | None = None
    cast_issued = False
    fought = False
    active_ticks = 0
    tick_seconds = command_seconds = max_tick_seconds = max_command_seconds = 0.0
    command_batches = 0
    memory_before = 0
    if trace_memory:
        tracemalloc.start()
    started = time.perf_counter()
    while not game.paused:
        tick = game.state.tick_count
        if trace_memory and tick == 1000:
            gc.collect()
            memory_before = tracemalloc.get_traced_memory()[0]
        if tick % 30 == 0:
            command_start = time.perf_counter()
            for team in teams:
                faction = game.state.faction_for_team(team)
                buildings = ("house", "arsenal", "spire") if faction == "AEGIS" else ("house", "pit", "chem_vat")
                upgrade = "aegis_mage_arcbinder" if faction == "AEGIS" else "rust_mage_plaguecaller"
                for index, worker in enumerate(workers[team]):
                    if worker.life <= 0 or (index == 0 and team in jobs):
                        continue
                    if worker.state == "IDLE":
                        if worker.carry_wood or worker.carry_gold:
                            game.issue_return_cargo_order(team, [worker])
                        else:
                            _gather(game, team, worker, "gold" if index == 2 else "wood")
                stage = stages[team]
                if stage < 3:
                    content_id = buildings[stage]
                    if team in jobs:
                        if not jobs[team].is_under_construction:
                            milestones[team.value][content_id] = tick
                            if stage > 0:
                                sign = -1 if team == TeamColor.BLUE else 1
                                _require(
                                    game.set_producer_rally(
                                        team, (center[0] + sign * 60, center[1] + 70), [jobs[team]]
                                    ),
                                    "Rally rejected",
                                )
                            del jobs[team]
                            stages[team] += 1
                            _gather(game, team, workers[team][0], "wood")
                        elif workers[team][0].state == "IDLE":
                            game.issue_build_order(team, jobs[team], [workers[team][0]])
                    elif game.construction.can_team_construct(team, content_id)[0]:
                        jobs[team] = _build(game, team, workers[team][0], content_id)
                elif stage < 6:
                    producer_id = buildings[1] if stage == 3 else buildings[2]
                    producer = cast("Building", game.state.entities_by_content_id(producer_id, team=team)[0])
                    success = (
                        game.produce_unit(producer, "knight" if stage == 3 else "mage")
                        if stage < 5
                        else game.research_upgrade(producer, upgrade)
                    )
                    if success:
                        stages[team] += 1
                elif game.teams[team].has_upgrade(upgrade) and "research" not in milestones[team.value]:
                    milestones[team.value]["research"] = tick
                    _require(
                        game.state.entities_by_content_id("mage", team=team), "Research ran before Mage production"
                    )
                    _require(game.state.population_for_team(team) == 8, "Unexpected army population")
            if arena_tick is None and all("research" in record for record in milestones.values()):
                arena_tick = tick
                for team in teams:
                    sign = -1 if team == TeamColor.BLUE else 1
                    for content_id, offset_y in (("knight", 0), ("mage", 70)):
                        unit = cast("Unit", game.state.entities_by_content_id(content_id, team=team)[0])
                        destination = (center[0] + sign * 60, center[1] + offset_y)
                        _require(game.issue_move_order(team, destination, [unit]), "Arena movement rejected")
            if arena_tick is not None and tick >= arena_tick + 1800 and not cast_issued:
                for team in teams:
                    enemy = TeamColor.RED if team == TeamColor.BLUE else TeamColor.BLUE
                    caster = cast("CasterUnit", game.state.entities_by_content_id("mage", team=team)[0])
                    target = game.state.entities_by_content_id("knight", team=enemy)[0]
                    _require(math.dist(caster.get_center(), center) < 260, f"Mage did not reach arena: {team}")
                    if game.state.faction_for_team(team) == "AEGIS":
                        accepted = game.issue_cast_order(team, "arc_bind", caster, target=target)
                    else:
                        accepted = game.issue_cast_order(team, "toxic_cloud", caster, destination=target.get_center())
                    _require(accepted, "Cast rejected")
                cast_issued = True
            if (
                cast_issued
                and not fought
                and all(
                    any(
                        cooldown > 0
                        for cooldown in cast(
                            "CasterUnit", game.state.entities_by_content_id("mage", team=team)[0]
                        ).ability_cooldowns.values()
                    )
                    for team in teams
                )
            ):
                for team in teams:
                    enemy = TeamColor.RED if team == TeamColor.BLUE else TeamColor.BLUE
                    target = game.state.entities_by_content_id("knight", team=enemy)[0]
                    army = [unit for unit in game.units_for_team(team) if str(unit.content_id) in {"knight", "mage"}]
                    _require(game.issue_target_order(team, target, army), "Combat order rejected")
                    milestones[team.value]["cast"] = tick
                fought = True
            command_elapsed = time.perf_counter() - command_start
            command_seconds += command_elapsed
            max_command_seconds = max(max_command_seconds, command_elapsed)
            command_batches += 1
        if any(
            worker.life > 0 and worker.state in {"GATHERING", "DEPOSITING", "BUILDING"}
            for group in workers.values()
            for worker in group
        ):
            active_ticks += 1
        step_start = time.perf_counter()
        simulation.step()
        step_elapsed = time.perf_counter() - step_start
        tick_seconds += step_elapsed
        max_tick_seconds = max(max_tick_seconds, step_elapsed)
        if game.recent_attacks:
            for record in milestones.values():
                record.setdefault("combat", game.state.tick_count)
        _require(
            all(value >= 0 for state in game.teams.values() for value in state.resources.values()), "Negative bank"
        )
    elapsed = time.perf_counter() - started
    retained_mib = None
    if trace_memory:
        gc.collect()
        retained_mib = (tracemalloc.get_traced_memory()[0] - memory_before) / (1024 * 1024)
        tracemalloc.stop()
    _require(
        fought and all("combat" in record for record in milestones.values()),
        f"Incomplete progression: {milestones}; banks={game.teams}; workers="
        f"{[(team, worker.state, worker.get_center(), worker.path_unreachable, worker.carry_gold) for team, group in workers.items() for worker in group]}",
    )
    _require(active_ticks > 1000, "Insufficient active economy coverage")
    _require(game.game_over_message is not None and game.state.tick_count <= frames, "Unbounded match")
    snapshot = build_observation(game, game.state.tick_count, EntityIdRegistry()).to_dict()
    digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
    restarted = game.restart()
    _require(restarted.state.tick_count == 0 and restarted.game_over_message is None, "Restart did not clear result")
    _require(restarted.state.match_rules == game.state.match_rules, "Restart lost rules")
    _require(
        all(
            not state.completed_upgrades and state.resources == {"wood": 0, "gold": 0}
            for state in restarted.teams.values()
        ),
        "Restart retained economy/research",
    )
    simulation.close()
    return {
        "map": path.name,
        "factions": factions,
        "reverse_commands": reverse_commands,
        "ticks": game.state.tick_count,
        "result": game.game_over_message,
        "reason": game.state.match_end_reason,
        "milestones": milestones,
        "digest": digest,
        "active_economy_ticks": active_ticks,
        "elapsed_seconds": round(elapsed, 4),
        "tick_steps_per_second": round(game.state.tick_count / tick_seconds, 2),
        "max_tick_ms": round(max_tick_seconds * 1000, 3),
        "command_batches": command_batches,
        "mean_command_ms": round(command_seconds / command_batches * 1000, 3),
        "max_command_ms": round(max_command_seconds * 1000, 3),
        "retained_python_mib_after_warmup": retained_mib,
    }


def main() -> None:
    """Run the acceptance matrix or one long active-memory scenario."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", type=int, choices=(1, 2, 3))
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument("--soak", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    results = []
    if args.soak:
        results.append(run_scenario(args.map or 1, PAIRINGS[0], frames=36_000, trace_memory=True))
        _require(
            results[0]["retained_python_mib_after_warmup"] < 2, "Active retained memory exceeds 2 MiB review budget"
        )
    else:
        for map_index in (args.map,) if args.map else (1, 2, 3):
            for factions in PAIRINGS:
                for reverse in (False, True):
                    runs = [run_scenario(map_index, factions, reverse_commands=reverse) for _ in range(args.repeats)]
                    _require(len({result["digest"] for result in runs}) == 1, "Replay mismatch")
                    results.extend(runs)
                    print(f"PASS map={map_index} factions={factions} reverse={reverse} repeats={len(runs)}", flush=True)
    report = {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "python": platform.python_version(),
        "runs": results,
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    else:
        print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
