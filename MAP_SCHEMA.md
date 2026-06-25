# RTS Nano Map Schema

Maps are JSON files stored in `src/rts_nano/maps/`. The game loads
`map_settings_01.json` by default, but the editor and validator can target other
files.

## Top-Level Shape

```json
{
    "Blue": {},
    "Red": {},
    "Resources": {},
    "Terrain": {}
}
```

`Blue` and `Red` hold team-owned entities. `Resources` holds neutral harvestable
entities. `Terrain` holds dimensions, terrain regions, and decorations.

## Teams

Each team section contains lists of `[x, y]` world coordinates:

```json
"Blue": {
    "peasant": [[300, 350]],
    "base": [[360, 500]],
    "knight": [],
    "archer": [],
    "mage": []
}
```

Known entity keys:

- `peasant`
- `base`
- `knight`
- `archer`
- `mage`

## Resources

Resources are also `[x, y]` world coordinates:

```json
"Resources": {
    "wood": [[823, 486]],
    "gold": [[750, 632]]
}
```

Known resource keys:

- `wood`
- `gold`

## Terrain

```json
"Terrain": {
    "width": 3200,
    "height": 2200,
    "high_ground": [],
    "ramps": [],
    "water": [],
    "rocks": [],
    "grass": []
}
```

All terrain coordinates are world coordinates.

## Grouped High Ground And Water

`high_ground` and `water` use grouped rectangle shapes. Each outer list entry is
one visual shape. Each shape contains one or more `[x, y, width, height]`
rectangles.

Single-rectangle shape:

```json
"high_ground": [
    [
        [145, 205, 565, 590]
    ]
]
```

Multi-rectangle joined shape:

```json
"water": [
    [
        [100, 100, 200, 80],
        [250, 140, 100, 160]
    ]
]
```

The game flattens these rectangles for collision and height queries but keeps
the groups for rendering. This avoids turning L-shaped or stepped terrain into a
large filled bounding box.

## Ramps

Ramps are independent flat rectangles:

```json
"ramps": [
    [640, 415, 95, 70]
]
```

Ramps connect low ground and high ground. A unit can change height only when the
current or next movement point is on a ramp.

## Rocks And Grass

Rocks and grass are `[x, y, radius]` payloads:

```json
"rocks": [[835, 575, 24]],
"grass": [[530, 205, 9]]
```

Rocks block movement. Grass is decorative only.

## Validation

Run:

```powershell
uv run python -m rts_nano.validate_map src/rts_nano/maps/map_settings_01.json
```

The canonical schema requires grouped `high_ground` and `water`. The runtime
loader is permissive for older hand-written maps, but the editor saves the
canonical grouped format.
