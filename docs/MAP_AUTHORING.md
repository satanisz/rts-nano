# MapSpec v3 Authoring Guide

MapSpec v3 is designed to be readable and editable without reconstructing meaning from hundreds of
raw coordinates. Use descriptive IDs such as `blue_natural_wood`, keep a small set of strategic
anchors, and mirror symmetric features instead of duplicating coordinates.

## Authoring workflow

1. Create a v3 JSON file next to the shipped maps.
2. Validate it after every meaningful edit.
3. Inspect its strategic summary and ASCII overview.
4. Generate an SVG preview for spatial review.
5. Compile to v2 only when a downstream tool specifically requires expanded coordinates.

```powershell
uv run python -m rts_nano.validate_map src/rts_nano/maps/map_spec_01.json
uv run python -m rts_nano.map_inspect src/rts_nano/maps/map_spec_01.json
uv run python -m rts_nano.map_preview src/rts_nano/maps/map_spec_01.json --output tmp/map_spec_01.svg
uv run python -m rts_nano.map_compile src/rts_nano/maps/map_spec_01.json --output tmp/map_spec_01.compiled.json
```

Generated previews and compiled files are review artifacts, not source maps. The game can load v3
directly. The current visual editor intentionally refuses v3 sources so it cannot flatten and
overwrite their semantic structure; use it only for v2 during the transition.

## Anchors and symmetry

An anchor is either an absolute point or a mirrored reference:

```json
"symmetry": {"type": "rotate_180", "center": [800, 600]},
"anchors": {
  "blue_main": [250, 900],
  "red_main": {"mirror_of": "blue_main"},
  "center": [800, 600]
}
```

Supported symmetry is `none` or `rotate_180`. A mirror uses the declared symmetry center. Placement
and terrain mirrors must reference an earlier record, which keeps expansion order deterministic and
turns misspelled references into precise validation errors.

## Teams and entities

`starting_package` places a base at the start anchor and distributes subsequent entities in stable
rings. Use `entities` when exact offsets or absolute positions matter:

```json
{
  "id": "Blue",
  "faction_id": "AEGIS",
  "start_anchor": "blue_main",
  "starting_package": {"base": 1, "peasant": 3},
  "entities": [
    {"content": "guardian", "offset": [90, 0]},
    {"content": "house", "at": [340, 980]}
  ]
}
```

Only content registered for the selected faction is accepted.

## Placements and patterns

Placements support `resource_cluster`, `entity_cluster`, and a single `entity`. Clusters combine an
anchor with one deterministic pattern:

| Pattern | Required fields | Meaning |
|---|---|---|
| `fixed_points` | `points` | Explicit offsets from the anchor |
| `ring` | `count`, `radius` | Even ring; optional `start_angle` |
| `arc` | `count`, `radius` | Inclusive arc; optional `start_angle`, `end_angle` |
| `line` | `count`, `from`, `to` | Evenly spaced offsets |
| `grid` | `rows`, `columns`, `spacing` | Centered rectangular grid |
| `scatter` | `count`, `radius`, `seed` | Repeatable seeded distribution |

Angles are degrees. Coordinates generated from fractional values are rounded deterministically.
`scatter` always requires an explicit non-negative seed.

```json
{
  "id": "blue_natural_wood",
  "kind": "resource_cluster",
  "resource": "wood",
  "anchor": "blue_natural",
  "pattern": {"type": "ring", "count": 10, "radius": 75, "start_angle": 18}
},
{
  "id": "red_natural_wood",
  "mirror_of": "blue_natural_wood"
}
```

For an `entity_cluster`, replace `resource` with `content` and add `team`. A single `entity` accepts
`anchor` plus `offset`, or an absolute `at` point.

## Terrain

Terrain records have stable IDs and one geometry:

- `high_ground` and `water`: `rect` or `rect_group`;
- `ramp`: `rect`;
- `rock` and decorative `grass`: `circle`.

```json
{
  "id": "center_water",
  "kind": "water",
  "geometry": {
    "type": "rect_group",
    "rects": [
      {"position": [700, 380], "size": [200, 130]},
      {"position": [700, 690], "size": [200, 130]}
    ]
  }
}
```

A circle uses `center` and `radius`. Mirrored terrain preserves dimensions and radius.

## Strategic requirements

Requirements turn design intent into executable checks. They do not change runtime gameplay.

```json
"requirements": {
  "start_resources": {
    "wood": {"min_nodes": 8, "max_distance": 350},
    "gold": {"min_nodes": 5, "max_distance": 350}
  },
  "routes": [
    {"id": "blue_to_center", "from": "blue_main", "to": "center", "unit_radius": 8},
    {"id": "red_to_center", "from": "red_main", "to": "center", "unit_radius": 8}
  ]
}
```

`start_resources` is checked from the first base of each team. Route endpoints may be named anchors
or `[x, y]` coordinates and use the simulation's terrain movement and pathfinding rules.

## Migration policy

Do not replace an established v2 map merely because an equivalent-looking v3 file compiles. Keep
the v2 source until coordinate output, headless initialization, determinism, and relevant gameplay
tests demonstrate compatibility. New maps should normally start in v3.
