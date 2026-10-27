# Game Rules — Verified State

Date: 2026-10-28. Updated through closeout sprint C1.
This document describes gameplay without designing an ML API. Remaining deviations from intended
rules are explicit and must not be treated as accepted design.
Readiness evidence: [game-stage audit](reviews/GAME_STAGE_AUDIT_2026-10-28.md).

## Current game scope

A two-team RTS: Blue and Red identify sides; map `faction_id` selects AEGIS or RUST.
Swapped sides and same-faction matches are supported. The windowed game starts with a Blue
human player and a simple Red bot.

| Shared foundation | AEGIS | RUST |
|---|---|---|
| Peasant, Knight, Archer, Mage | Guardian, Marksman, Arclight | Ripper, Spitter, Brute |
| Base, House | Arsenal, Spire, Bastion | Pit, Chem Vat, Spiker |
| Wood, gold, construction, production, research | Shields and AEGIS doctrines | Poison, frenzy, and RUST doctrines |

Canonical costs, durations, and stats live in
[`content/registry.py`](../src/rts_nano/content/registry.py); a separate full balance table would
create duplication. The in-game technology tree (`F9`) uses this registry. Extension guides:
[ADDING_CONTENT](ADDING_CONTENT.md) and [TECH_TREE_AUTHORING](TECH_TREE_AUTHORING.md).

## Time and resolution

Rules use simulation ticks, nominally 60 per second. Attacks, construction, production, research,
and effects count simulation time. A slower computer may slow windowed gameplay relative to
wall time without changing tick rules. System order is described in
[ARCHITECTURE](../ARCHITECTURE.md). Units act sequentially in stable creation order; damage is
not resolved simultaneously for all units. Determinism does not prove the absence of turn-order bias.

Currently, the only team with living units or buildings wins. With no active teams, the result
is `Draw`. Destroying a base alone does not end a match while its owner has other objects.
Living unfinished buildings also keep a team active. After a result, `GameSession` stops the
simulation; restart recreates the map and match state while retaining cached artwork.

**Limitation:** the game has no match-duration limit, stalemate resolution, or surrender command.
Two opposing houses can keep it running forever. The limit in `env.py` belongs to a separate
layer and does not apply in `main.py`. Choosing the final ending rule belongs to game closeout,
not the ML API.

## Economy and construction

- Peasants gather finite resources and return cargo to an allied base. The bank grows on deposit,
  not on harvesting. Resource nodes do not block movement.
- Depleted nodes are removed; workers seek nearby replacements of the same type. Losing a base
  interrupts the normal deposit cycle.
- Additional bases cannot be constructed (`base.constructable=False`). Map outposts are remote
  resource deposits, not full expansions with new drop-off points.
- Starting construction requires a living worker, resources, the correct faction, technology,
  and a valid location. Costs are paid when construction starts.
- Additional workers accelerate building; repairing completed structures costs wood. Canceling
  construction refunds 75% of each resource cost, rounded down.
- Buildings are dynamic obstacles. Placement/removal changes the obstacle revision and causes
  active routes to update.

Workers with HP <= 0 contribute neither construction nor repair, including before end-of-tick
cleanup. This closes audit bug G3.

## Population and production

A Base provides 10 supply and a completed House provides 6. Units cost 1–3 population.
Queued units reserve their population costs. A unit can be trained only at a registry-listed producer.

Occupied population sums the definition costs of living units, separately from unit count.
New production requires occupied population plus all queued reservations plus the requested unit's
cost to fit supply. Spawning transfers reserved population to occupied population without freeing
capacity. Death and cancellation release the corresponding population. The HUD shows occupied
population/capacity and a separate queued amount. This closes audit bug G1.

Production and research share a building FIFO. Only its first entry advances each tick. If no safe
spawn point exists, the completed job waits instead of spawning inside an obstacle. Cancellation
removes the first entry and refunds 75%; destruction removes the queue without a refund. Population
is validated on enqueue. Losing a House or Base keeps the existing army and allows already paid
jobs to finish, even above the reduced cap; new requests remain blocked until enough capacity
is available. There is no forced unit deletion or automatic refund on supply loss.

## Technologies and abilities

Research belongs to the team. Costs and exclusive-doctrine reservations apply on enqueue.
Cancellation and producer destruction release reservations; completed technology remains.
Modifiers are derived from base definitions in stable ID order for existing and future units.

Mages gain abilities through the appropriate doctrine. Cast orders may wait for range, energy,
or cooldown; energy is spent and cooldown starts only on successful application. Dead/invalid
targets should not consume energy. Area effects have bounded ranges and target counts, selected
in ID order. Temporary statuses use remaining-tick counters.

## Combat, movement, and information

- Move, attack-move, patrol, stop, hold, target interaction, gather, return cargo, build, repair,
  and cast use shared gameplay systems. Unit queues hold 16 deferred orders.
- Water, rocks, elevation, and ramps affect routes. Unreachable movement stops the unit instead
  of retrying pathfinding forever.
- Modified damage cannot be negative. Shields absorb damage before HP and regenerate after a
  damage-free delay. Poison refreshes one effect rather than stacking independently, and also
  passes through shields.
- Elevation changes ranged reach and damage. Combat and effects work without graphics; attack
  animations present an already resolved result.
- Fog has unexplored/explored/visible states based on vision radius. `FogOfWar` does not model
  terrain occlusion.
- The renderer refreshes the current player's fog. The bot owns its explored-cell memory and
  last-seen enemy-base position. This is not one shared per-tick simulation of every team's knowledge.

**Known bug G2:** selection/rendering filter visibility, but right-click and cast-target lookup
search all entities. A hidden object can be targeted before being seen. Closeout requires consistent
target selection, not a physical line-of-sight system.

## Maps and bot

The target game set is Crown Divide, Twin Rivers, and Ashen Circuit (`map_spec_01..03`).
MapSpec v3 compiles to runtime v2. Validation checks authored routes and starting resources;
tests confirm rotational symmetry of starts and resources. Symmetry does not prove faction balance.
Legacy `map_settings_*.json` remain compatibility/regression material; the visual editor supports v2 only.

`ScriptedAI` demonstrates gathering, one basic military producer, training, scouting, and attacks.
It does not build Houses, train workers, research, or use active abilities. It neither validates
the whole tech tree nor provides a reliable balance measure. Controlled scenarios can serve game
acceptance without expanding the bot.

## Outside the game stage

New factions/units, campaigns, audio, save/load, full expansions, a v3 editor, a strong bot, and
perfect competitive balance are not required. Future RL benefits from explicit frozen rules and
the removal of bugs offering unintended advantages. API design, tensors, ML observations, rewards,
adapters, vectorization, and training are outside this document.
