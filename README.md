# RTS Nano

RTS Nano is a compact real-time strategy game with a deterministic, presentation-independent
simulation core. The current milestone is a complete game core for later AI and reinforcement-
learning work; it is not intended to be a commercial game product.

## Current game

Two factions share the same economy and construction fundamentals but use distinct rosters:

| Faction | Units | Production and defense |
|---|---|---|
| AEGIS | Peasant, Knight, Archer, Mage, Guardian, Marksman, Arclight | Base, House, Arsenal, Spire, Bastion |
| RUST | Peasant, Knight, Archer, Mage, Ripper, Spitter, Brute | Base, House, Pit, Chem Vat, Spiker |

The game supports gathering wood and gold, population supply, construction, production queues,
terrain height and ramps, water and rock obstacles, formation movement, attack-move, patrol,
defensive towers, fog of war, shields, poison, frenzy, splash damage, and deterministic victory.
Teams select factions explicitly in map data; Blue and Red do not imply a faction.
Shared Knight, Archer, and Mage units branch into exclusive faction doctrines researched at the
Arsenal/Pit and Spire/Chem Vat. Press `F9` to inspect the current team's registry-derived tree.

## Competitive maps

The playable game defaults to the semantic MapSpec v3 map set:

| Map | Style | Strategic shape |
|---|---|---|
| Crown Divide | Standard | Protected main plateaus, safe starting economy, contested central lane |
| Twin Rivers | Control | Three river crossings, elevated center, northern and southern outposts |
| Ashen Circuit | Aggressive | Short routes, compact defended mains, raised central arena |

Every map uses exact 180-degree spawn/resource symmetry and executable checks for starting economy
and critical routes. Legacy v2 maps remain available for compatibility and regression tests.

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

# Play another competitive map
uv run python -m rts_nano.main --map map_spec_02.json

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

`rts_nano.env.RtsNanoEnv` adds a deterministic episode lifecycle and simultaneous Blue/Red action
boundary for future RL adapters. It defaults to a 36,000-frame limit, reports termination and
truncation separately, supports configurable frame skip, and exposes registry-derived strategic
and tactical actions. It remains tensor-framework neutral; Gymnasium/PyTorch adapters belong to
the next milestone.

```python
from rts_nano.actions import MoveAction, NoOpAction
from rts_nano.env import RtsNanoEnv
from rts_nano.simulation.entities import TeamColor

env = RtsNanoEnv(frame_skip=8)  # Always headless; no visual assets are loaded.
observation = env.reset(seed=7)
result = env.step_joint({
    TeamColor.BLUE: (MoveAction(TeamColor.BLUE, (600, 400)),),
    TeamColor.RED: (NoOpAction(),),
})
env.close()
```

## Core controls

- Right-click ground to move selected units. Hold Shift while right-clicking to append a move.
- Right-click wood or gold with selected Peasants to gather it. Shift appends gathering after the
  current move or construction order.
- Right-click ground with a selected Base to set its Peasant rally point. Right-click wood or gold
  to make newly produced Peasants harvest automatically.
- Right-click ground with any selected production building to rally new units there. Right-click a
  visible enemy to set an attack-move rally at its last known position.
- Place a building with a Peasant, then Shift-right-click a resource to finish construction before
  harvesting. The selection panel shows the active order and up to three queued orders.
- Right-click an unfinished allied building with additional Peasants to accelerate construction.
  Right-click a damaged completed allied building to repair it using Wood.
- After Victory, Defeat, or Draw, choose `RESTART MATCH` or press `R` to recreate the same map from
  clean deterministic state without reloading cached art.
- Press `F9` to open or close the current faction's technology tree. The view shows research
  location, cost, prerequisites, exclusive choices, and live completion state.

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
- [Competitive map review](docs/reviews/COMPETITIVE_MAPS_REVIEW.md)
- [Adding units, buildings, resources, or factions](docs/ADDING_CONTENT.md)
- [Technology and ability authoring](docs/TECH_TREE_AUTHORING.md)
- [Determinism contract](docs/DETERMINISM.md)
- [RL environment contract](docs/RL_ENVIRONMENT_CONTRACT.md)
- [Sprint S5 performance report](benchmarks/SPRINT_S5_REPORT.md)
- [Game-core readiness plan](EXECUTIVE_PLAN_05_CORE_READINESS.md)
- [Expanded faction tech-tree plan](EXECUTIVE_PLAN_06_EXPANDED_FACTION_TECH_TREES.md)
- [RL environment foundation plan](EXECUTIVE_PLAN_07_RL_ENVIRONMENT_FOUNDATION.md)

Tensor schemas, curriculum maps, vector environments, AI policies, automated balance work, reward
design, Gymnasium/PyTorch adapters, and RL training remain deferred to the next milestone.
