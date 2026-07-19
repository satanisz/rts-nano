# RTS Nano Map Formats

RTS Nano supports two JSON formats with deliberately different jobs:

- **MapSpec v3** is the canonical authoring format. It describes intent with named anchors,
  deterministic patterns, mirrors, and strategic requirements. Humans and LLMs should create and
  review this format.
- **Runtime v2** is the expanded coordinate format consumed by the simulation. Existing maps remain
  compatible, and the current visual editor edits this format only.

`load_map_settings()` accepts either format. It validates and deterministically compiles v3 in
memory, then always returns the same v2 `MapSettings` shape to the simulation. Pygame is not involved
in loading or compilation.

## MapSpec v3

A minimal semantic map has world dimensions, anchors, two teams, placements, and terrain:

```json
{
  "schema_version": 3,
  "id": "small_crossing",
  "name": "Small Crossing",
  "world": {"width": 1600, "height": 1200},
  "symmetry": {"type": "rotate_180", "center": [800, 600]},
  "anchors": {
    "blue_main": [250, 900],
    "red_main": {"mirror_of": "blue_main"},
    "center": [800, 600]
  },
  "teams": [
    {
      "id": "Blue",
      "faction_id": "AEGIS",
      "start_anchor": "blue_main",
      "starting_package": {"base": 1, "peasant": 3}
    },
    {
      "id": "Red",
      "faction_id": "RUST",
      "start_anchor": "red_main",
      "starting_package": {"base": 1, "peasant": 3}
    }
  ],
  "placements": [],
  "terrain": []
}
```

See [Map authoring](docs/MAP_AUTHORING.md) for patterns, terrain geometry, requirements, tools, and
the safe migration workflow. The complete executable example is
[`map_spec_01.json`](src/rts_nano/maps/map_spec_01.json).

## Runtime v2

Runtime v2 stores every generated coordinate explicitly:

```json
{
  "schema_version": 2,
  "Blue": {"faction_id": "AEGIS", "base": [[250, 900]], "peasant": []},
  "Red": {"faction_id": "RUST", "base": [[1350, 300]], "peasant": []},
  "Resources": {"wood": [], "gold": []},
  "Terrain": {
    "width": 1600,
    "height": 1200,
    "high_ground": [],
    "ramps": [],
    "water": [],
    "rocks": [],
    "grass": []
  }
}
```

Team entity and neutral resource positions are `[x, y]`. `high_ground` and `water` are grouped
rectangle shapes: each shape is a list of `[x, y, width, height]` rectangles. Ramps are independent
rectangles. Rocks and decorative grass are `[x, y, radius]` circles.

Content IDs and faction rosters come exclusively from `src/rts_nano/content/`. The validator rejects
unknown IDs and entities unavailable to a team's faction.

## Validation contract

The shared validator checks both versions:

```powershell
uv run python -m rts_nano.validate_map src/rts_nano/maps/map_spec_01.json
```

For v3 it also rejects broken references, non-deterministic patterns, generated objects outside the
world (including their radius), duplicate positions, objects on blocking terrain, insufficient
starting resources, and unreachable declared routes. A valid v3 source must compile to valid v2.

World dimensions are simulation state. Window or viewport resizing never changes map bounds.
