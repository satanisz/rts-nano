# MapSpec v3 Foundation Review

Date: 2026-07-20
Status: accepted

## Outcome

The map-authoring foundation is ready for incremental use. New maps can be expressed as semantic,
deterministic MapSpec v3 JSON while the simulation continues to consume the established runtime v2
shape. Existing v2 maps were not rewritten or removed.

The delivered slice includes:

- authoritative world bounds independent of viewport size;
- named anchors and 180-degree mirrors;
- deterministic fixed, ring, arc, line, grid, and seeded-scatter patterns;
- semantic team, resource, entity, and terrain declarations;
- declared starting-resource and route requirements;
- validation of references, faction content, bounds including radii, duplicate coordinates,
  blocking-terrain overlap, resource access, and reachability;
- text inspection, ASCII overview, SVG preview, and explicit v3-to-v2 compilation tools;
- a playable `Mirror Basin` v3 example loaded by the real headless runtime;
- a safe v2-only guard in the transitional visual editor;
- English schema, authoring, architecture, and README documentation.

## Review findings resolved

1. Viewport resize previously enlarged small simulation worlds. World size now comes only from the
   map, and a regression test changes the viewport without changing terrain, fog, or state bounds.
2. A v3 source could have been opened and flattened by the v2 visual editor. The editor now refuses
   v3 with directions to preview or compile it instead.
3. The grid pattern initially required a redundant `count`. Its cardinality now derives exclusively
   from rows and columns.
4. Mirroring without declared rotational symmetry and anchors outside the world are now rejected.
5. Loading v3 initially compiled it twice and cost about 10.4 ms on every call. Validation and
   compilation now happen once per changed file; a bounded cache retains the compiled blueprint and
   every caller receives a deep copy. Warm measured load cost is about 0.095 ms, so environments do
   not share mutable map data.
6. The sample's first center basin blocked both declared routes. Its two water lobes now leave a
   verified central corridor.

## Verification

- Ruff format: clean (87 files)
- Ruff lint: clean
- Ty: clean
- Pytest: 197 passed
- Coverage: above 73% (required minimum: 50%)
- All three shipped v2 maps and the v3 example: valid
- `map_compile`: generated valid runtime v2 JSON
- `map_preview`: generated dependency-free SVG
- `map_inspect`: both bases report reachable center routes

Standard core benchmark, three repeats:

| Scenario | Result | Review budget |
|---|---:|---:|
| Map 01 cold initialization | 1.097 ms | below 20 ms |
| Map 01 throughput | 15,665 steps/s | at least 6,000 steps/s |
| 400 dispersed group orders | 1,201 ms | below 5,000 ms |
| 400 dispersed throughput | 162.5 steps/s | at least 60 steps/s |

The map tooling does not import Pygame. Strategic validation is authoring/load-time work and is not
part of a simulation tick.

## Deferred intentionally

- Existing v2 maps remain v2 until an individual migration proves exact gameplay compatibility.
- The visual editor has not been redesigned around semantic v3 operations.
- AI behavior, balance, rewards, and RL adapters remain outside this slice.
- Cross-process precompiled artifact distribution is unnecessary at current map sizes; the in-process
  cache removes repeated compilation for multi-environment use.
