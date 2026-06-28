# RTS Nano - Executive Plan 04: Asymmetric Factions (AEGIS vs RUST)

Last updated: 2026-06-29

Goal: replace the two identical rosters with two **asymmetric factions** that play
differently — Blue = **AEGIS** (precision / armored / ranged elite that scales),
Red = **RUST** (cheap / fast / expendable swarm that rushes) — each with a full
mechanic kit. Economy stays identical (fair); all asymmetry lives in the army,
tech, and signature mechanics.

This is a deliberate **gameplay change**, not a refactor: the deterministic
"golden" digest will be re-baselined once factions land, and Knight/Archer/Mage
+ the shared maps/tests are migrated to faction rosters.

---

## 1. Faction identity

| | BLUE — AEGIS | RED — RUST |
|---|---|---|
| Theme | Hextech, shields, drones, snipers | Scrap, chem, toxins, fast mobs |
| Plan | Quality: few, durable, ranged, scales | Quantity: cheap, fast, fragile, rush |
| Signature | **Shields** (regen buffer) + **Splash** | **Toxin** (poison DoT) + **Frenzy** |

## 2. Shared economy (identical for both, reflavored names only)

| Role | Class reused | Cost | Pop | Build | Stats |
|---|---|---|---|---|---|
| Worker (Engineer/Scav) | `Peasant` | 50W | 1 | 60 | life 5, dmg 3, gather 10, spd 2.0 |
| HQ (Citadel/Warren) | `Base` | 400W 100G | +10 | 300 | life 500, builds Worker |
| Supply (Conduit/Shanty) | `House` | 80W | +6 | 180 | life 500 |

## 3. AEGIS roster (Blue)

Tech: `Citadel → Arsenal → Spire`. All AEGIS units have **Shields**.

**Buildings**

| Building | Cost | Build | Requires | Produces |
|---|---|---|---|---|
| Arsenal | 220W 60G | 360 | Citadel | Marksman, Guardian |
| Spire | 200W 150G | 420 | Arsenal | Arclight |
| Bastion (tower) | 150W 80G | 240 | — | auto-attack: 12 dmg, 200 range, 1.0/s, shielded |

**Units** (shield = absorb buffer; armor = flat damage reduction; atk/s = attacks per second)

| Unit | Cost | Pop | Build | Life | Shield | Armor | Dmg | Range | Atk/s | Spd | Kit |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Marksman (ranged) | 90W 35G | 2 | 120 | 70 | 30 | 1 | 9 | 210 | 1.0 | 2.2 | shields |
| Guardian (tank) | 110W 55G | 3 | 150 | 150 | 60 | 4 | 8 | 5 | 1.0 | 1.9 | shields, anvil |
| Arclight (artillery) | 80W 130G | 3 | 180 | 40 | 20 | 0 | 16 | 520 | 0.77 | 1.4 | shields, **splash r=60** |

## 4. RUST roster (Red)

Tech: `Warren → Pit → Chem-Vat`.

**Buildings**

| Building | Cost | Build | Requires | Produces |
|---|---|---|---|---|
| Pit | 180W 40G | 300 | Warren | Ripper, Spitter |
| Chem-Vat | 160W 120G | 360 | Pit | Brute |
| Spiker (tower) | 120W 60G | 200 | — | auto-attack: 8 dmg, 150 range, 1.6/s, **poison** |

**Units**

| Unit | Cost | Pop | Build | Life | Armor | Dmg | Range | Atk/s | Spd | Kit |
|---|---|---|---|---|---|---|---|---|---|---|
| Ripper (swarm) | 55W 10G | **1** | 90 | 45 | 0 | 6 | 5 | 1.0 | 3.0 | **frenzy** |
| Spitter (chem) | 60W 20G | 1 | 100 | 40 | 0 | 6 | 130 | 1.0 | 2.4 | **poison** |
| Brute (heavy) | 120W 40G | 3 | 180 | 200 | 1 | 14 | 5 | 0.9 | 1.8 | **poison, frenzy** |

## 5. Mechanic rules (deterministic, frame-based)

All applied through one central `apply_damage(target, amount, attacker_tick)` helper
so unit attacks, tower attacks, and poison all share one path.

1. **Shields (AEGIS).** Unit has `shield`, `shield_max`, `shield_regen` (per second),
   `shield_regen_delay` (frames). Incoming damage subtracts from `shield` first, the
   remainder from `life`. Any hit sets `last_damaged_tick`. Each tick, if
   `tick - last_damaged_tick >= shield_regen_delay` and `shield < shield_max`,
   regen `shield_regen/FPS` accumulated to whole points.
2. **Splash (Arclight).** On a landed hit, deal the same post-mitigation damage to
   every enemy unit/building within `splash_radius` of the primary target's center
   (primary excluded), iterated in stable order.
3. **Poison / Toxin (RUST).** On a landed hit, set the target's `poison_tick_damage`
   and refresh `poison_remaining_frames` to the source's duration (refresh, do not
   stack damage). Each tick a target with poison takes `poison_tick_damage` every
   `POISON_INTERVAL` frames (integer damage; e.g. 2 dmg every 30 frames for 90 frames).
4. **Frenzy (RUST Ripper/Brute).** While `life <= 0.5 * max_life`, the attack cooldown
   is multiplied by `0.66` (≈ +50% attack speed). Checked when the cooldown is set.

Shields/poison/splash are applied identically whether the attacker is a unit or a
tower (the `CombatSystem` and `Unit._attack` both call `apply_damage`).

## 6. Engine changes

- `data.py`: add `faction` + `requires: tuple[str, ...]` to `UnitSpec`/`BuildingSpec`;
  split into `AEGIS_*`/`RUST_*` spec tables (or one table tagged by faction) keyed by
  faction; helper `specs_for_faction(faction)`.
- New unit classes encoding behavior: `AegisUnit(Unit)` (shields) and `RustUnit(Unit)`
  (poison/frenzy hooks); concrete `Marksman`, `Guardian`, `Arclight`, `Ripper`,
  `Spitter`, `Brute`. New buildings `Arsenal`, `Spire`, `Bastion`, `Pit`, `ChemVat`,
  `Spiker` (+ HQ/Supply reused as `Base`/`House`).
- `EntitiesGroup`: faction-flavored rosters (or generic `units`/`buildings` lists keyed
  by spec) — keep per-class lists but extend for the new types.
- `EntityFactory` + `_load_map_settings`: faction-aware name→class; a team's faction is
  read from the map.
- `map_schema` + maps: each team section gets a `"faction": "AEGIS"|"RUST"`; the three
  shipped maps assign Blue=AEGIS, Red=RUST and spawn the right starting units.
- `ProductionSystem`/`ConstructionSystem`: honor `requires` (must own the prerequisite
  building); `CommandPanel` shows the faction's buildable set.
- `rules.py`: central `apply_damage`; `combat`/effects tick for poison + shield regen
  (likely a small new `EffectsSystem` owned by the manager/state).
- `ScriptedAI`: faction-aware build orders (AEGIS: workers → Arsenal → Marksmen +
  Guardians → Spire; RUST: workers → Pit → mass Rippers → Chem-Vat → Brutes).

## 7. Phased build (each phase: full gate green, commit)

- **P1 — Faction data + tech gate (no new mechanics).** Specs tagged by faction +
  `requires`; new unit/building classes as plain stat carriers (behave like today's
  melee/ranged); faction-aware factory/rosters/UI/AI; map schema `faction`; migrate the
  three maps + all tests to faction rosters; re-baseline golden. *Ships factions that
  already play differently via stats + tech.*
- **P2 — Shields (AEGIS)** via the central `apply_damage` helper + regen tick.
- **P3 — Poison (RUST)** DoT tick.
- **P4 — Splash (Arclight) + Frenzy (Ripper/Brute).**
- **P5 — Faction AI build orders + balance pass + matchup tests** (AEGIS-vs-RUST
  headless games that don't hard-stalemate; assert each faction can win from a fair
  start).

## 8. Notes / risks

- Determinism preserved within each phase (integer damage, fixed iteration order, no
  RNG). The golden digest is re-baselined once after P1 and only changes again when a
  phase deliberately alters combat.
- Keep it small: 3 military units + 2 military buildings per faction, 4 mechanics total.
  No hero units, no upgrades-with-research beyond the tech gate (those are future work).
- Workers, HQ, and supply stay shared/identical so the economy is fair and the diff
  stays focused on the army.
