# Game Rules — Verified State

Date: 2026-10-28. Frozen through closeout sprint C4.
This document describes gameplay without designing an ML API. Current acceptance evidence is in
the [C4 review](reviews/GAME_CLOSEOUT_C4_REVIEW.md); the [original audit](reviews/GAME_STAGE_AUDIT_2026-10-28.md)
records the pre-fix state. Its G1–G3 defects are resolved.

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

Ordinary windowed and headless games draw after 36,000 simulation ticks (10 nominal minutes) if
elimination has not produced a result. Elimination on the final allowed tick takes precedence,
including mutual elimination. No army-value score or heuristic lack-of-progress detection is used.
The HUD shows elapsed time/limit and the result overlay explains a time-limit draw. Pause freezes
the clock, a terminal result is latched, and restart resets time/result while retaining match rules.
There is no surrender command.

`MatchRules(max_frames=...)` configures controlled game scenarios; `None` explicitly disables the
game deadline. The existing `RtsNanoEnv` opts out of that game deadline internally and retains its
own unchanged episode truncation policy, including a disabled episode limit. No new ML-facing API,
observation schema, or reward behavior was added to implement the game rule.

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
The selected producer shows the active training/research progress, its next job, and waiting count.

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
  of retrying pathfinding forever. Path edges validate the actual starting and ending points;
  leaving an existing building overlap must move outward without cutting through its center.
- Modified damage cannot be negative. Shields absorb damage before HP and regenerate after a
  damage-free delay. Poison refreshes one effect rather than stacking independently, and also
  passes through shields.
- Elevation changes ranged reach and damage. Combat and effects work without graphics; attack
  animations present an already resolved result.
- Fog has unexplored/explored/visible states based on vision radius. `FogOfWar` does not model
  terrain occlusion.
- Input and rendering refresh the current player's fog from living allied entities. Each selectable
  side has separate exploration memory; switching teams cannot transfer that memory. Restart clears
  it. The bot owns its separate explored-cell memory and last-seen enemy-base position. This is not
  one shared per-tick simulation of every team's knowledge.

Selection, right-click, gather, rally, and entity casts share one player-target rule: living allied
objects are available, hostile objects must be currently visible, and resources must be explored
and nonempty. Unknown object clicks resolve as ground where appropriate, without object identity.
An unseen entity cannot become a new cast target. Ground/area spells may still target coordinates
without identifying hidden entities. Enemy inspection clears when sight is lost.

A legally issued attack or entity cast continues tracking its living target after sight is lost;
this preserves the existing explicit-target rule. Enemy rally stores the visible target's position
as attack-move ground coordinates, not a tracking reference. These are deliberate gameplay policies,
not a physical line-of-sight model. This closes audit bug G2.

## Maps and bot

The target game set is Crown Divide, Twin Rivers, and Ashen Circuit (`map_spec_01..03`).
MapSpec v3 compiles to runtime v2. Validation checks authored routes and starting resources;
tests confirm rotational symmetry of starts and resources. Symmetry does not prove faction balance.
Legacy `map_settings_*.json` remain compatibility/regression material; the visual editor supports v2 only.

`ScriptedAI` demonstrates gathering, one basic military producer, training, scouting, and attacks.
It does not build Houses, train workers, research, or use active abilities. It neither validates
the whole tech tree nor provides a reliable balance measure. Controlled scenarios can serve game
acceptance without expanding the bot. The C4 driver verifies earned economy, both producer tiers,
research, casts, combat, result, and restart in all 12 map/faction combinations, both command orders,
with two fresh runs per ordering. Its 18,000-tick acceptance deadline is deliberately shorter than
the ordinary 36,000-tick match rule; its draws are not a balance result.

## Outside the game stage

New factions/units, campaigns, audio, save/load, full expansions, a v3 editor, a strong bot, and
perfect competitive balance are not required. Future RL benefits from explicit frozen rules and
the removal of bugs offering unintended advantages. API design, tensors, ML observations, rewards,
adapters, vectorization, and training are outside this document.
