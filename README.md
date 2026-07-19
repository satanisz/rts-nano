# RTS Nano

RTS Nano is a compact real-time strategy game with a deterministic, presentation-independent
simulation core. The current milestone is a complete game core for later AI and reinforcement-
learning work; it is not intended to be a commercial game product.

## Current game

Two factions share the same economy and construction fundamentals but use distinct rosters:

| Faction | Units | Production and defense |
|---|---|---|
| AEGIS | Peasant, Guardian, Marksman, Arclight | Base, House, Arsenal, Spire, Bastion |
| RUST | Peasant, Ripper, Spitter, Brute | Base, House, Pit, Chem Vat, Spiker |

The game supports gathering wood and gold, population supply, construction, production queues,
terrain height and ramps, water and rock obstacles, formation movement, attack-move, patrol,
defensive towers, fog of war, shields, poison, frenzy, splash damage, and deterministic victory.
Teams select factions explicitly in map data; Blue and Red do not imply a faction.

## Requirements and installation

- Python 3.14 or newer
- [uv](https://docs.astral.sh/uv/)
- Pygame CE (installed from the lockfile)

```powershell
uv sync --locked --dev
```

## Run

```powershell
# Play the game
uv run python -m rts_nano.main

# Open the map editor
uv run python -m rts_nano.map_editor --map map_settings_01.json

# Validate one or more maps
uv run python -m rts_nano.validate_map src/rts_nano/maps/map_spec_01.json

# Inspect and preview the semantic MapSpec example
uv run python -m rts_nano.map_inspect src/rts_nano/maps/map_spec_01.json
uv run python -m rts_nano.map_preview src/rts_nano/maps/map_spec_01.json --output tmp/map_spec_01.svg

# Run the pure headless benchmark
uv run python benchmarks/core_baseline.py
```

`rts_nano.headless.HeadlessSimulation` exposes the same simulation used by the windowed game
without importing Pygame, configuring SDL, loading images, or creating presentation objects.

## Quality gate

```powershell
uv run ruff format --check .
uv run ruff check .
uv run ty check src/rts_nano
uv run pytest --cov=src/rts_nano
```

The stored replay digest protects deterministic gameplay. CI also validates every shipped map,
runs rendering with SDL's dummy video driver, and reports a fast benchmark smoke sample.

## Project guides

- [Architecture](ARCHITECTURE.md)
- [Map schema](MAP_SCHEMA.md)
- [MapSpec v3 authoring](docs/MAP_AUTHORING.md)
- [Adding units, buildings, resources, or factions](docs/ADDING_CONTENT.md)
- [Determinism contract](docs/DETERMINISM.md)
- [Sprint S5 performance report](benchmarks/SPRINT_S5_REPORT.md)
- [Game-core readiness plan](EXECUTIVE_PLAN_05_CORE_READINESS.md)

AI policies, automated balance work, reward design, environment lifecycle changes, and RL training
adapters intentionally belong to the next stage after this game-core milestone.
