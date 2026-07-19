# Competitive Map Rebuild Review

Date: 2026-07-20
Status: accepted

## Goal

Rebuild the playable map set around recognizable competitive RTS principles: protected starts,
fair opening economy, multiple routes, meaningful terrain control, resource outposts, and exact
spawn symmetry. The maps are inspired by classic Warcraft and StarCraft structure without copying
specific commercial layouts.

## Legacy map audit

| Map | Finding | Consequence |
|---|---|---|
| `map_settings_01` | 3200x2200, 160 wood, 80 gold, 14 ramps; both start-to-center routes blocked | Visually busy, difficult to read, and unsuitable as a reliable default |
| `map_settings_02` | Two wood nodes, one shared gold field, unequal worker counts | Prototype-scale economy and strong positional asymmetry |
| `map_settings_03` | Fair starting distances but no high ground or ramps and little route structure | Playable, but strategically flat |

The v2 files remain unchanged for compatibility, regression tests, and historical comparison.

## New map set

| Map | Size | Terrain identity | Intended pacing |
|---|---:|---|---|
| Crown Divide | 2000x1400 | Elevated mains, one defended exit per main, central rocks, edge moats | Standard macro/control |
| Twin Rivers | 2200x1400 | Three crossings through twin rivers and a two-ramp central plateau | Wide multi-lane control |
| Ashen Circuit | 1600x1100 | Compact main plateaus, raised central arena, side basins | Fast pressure and reinforcement |

Each map contains 52 wood nodes and 30 gold nodes: one ten-wood/five-gold starting field and two
eight-wood/five-gold outposts per player. These are resource outposts rather than true expansions,
because the current game does not yet allow construction of additional bases.

## Fairness and playability checks

- Blue and Red bases, workers, wood, and gold are exact 180-degree rotations.
- Each start has ten wood nodes and five gold nodes inside its declared opening radius.
- Nearest starting resources are equal for both players:
  - Crown Divide: wood 137, gold 142;
  - Twin Rivers: wood 138, gold 165;
  - Ashen Circuit: wood 127, gold 124.
- Six authored strategic routes per map pass the simulation terrain/pathfinding validator.
- A real worker completes a harvest/deposit cycle and reaches the center on every map.
- The existing scripted opponent can gather, construct production, train an army, cross the map,
  and destroy the opposing base on every map.
- Both factions were separately smoke-tested from their assigned side. Different completion times
  reflect current faction/AI balance and are not treated as a map-balance result.
- Idle headless throughput measured between approximately 30,700 and 34,100 steps/s across the set,
  comfortably above the established 6,000 steps/s review budget.

## Integration decisions

- The windowed game now defaults to Crown Divide.
- `python -m rts_nano.main --map map_spec_02.json` selects another packaged map.
- The RL environment default remains the legacy map and was deliberately not changed.
- The transitional visual editor cycles through v2 `map_settings_*.json` files only, preventing a v3
  source from being opened and flattened.

## Review boundary

This review establishes structural fairness and mechanical playability, not final competitive
balance. Human playtests should later tune travel times, defensibility, resource quantities, and
faction matchups. True expansions require a separate gameplay decision to make bases constructable.
