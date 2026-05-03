# RTS Nano Architecture

RTS Nano is a pygame RTS sandbox with a small playable game loop, a JSON map
format, and a standalone map editor. The code is intentionally compact, but a
few boundaries matter.

## Runtime Modules

- `src/rts_nano/main.py`
  Owns pygame startup, display/window/fullscreen creation, and the outer
  event/update/draw loop. It should stay thin.

- `src/rts_nano/game/manager.py`
  Owns live game state: map terrain, teams, resources, selected entities,
  camera, minimap, HUD, menu, projectiles, click markers, harvesting, and
  victory detection.

- `src/rts_nano/game/assets/entities/`
  Contains entity classes. `Unit` owns local movement/combat state. Concrete
  units define stats and small behavior overrides. Buildings and resources are
  selectable entities with different lifetime rules.

- `src/rts_nano/game/terrain.py`
  Loads terrain settings, answers height/blocking/ramp queries, and renders
  terrain. High ground and water are grouped rectangle shapes.

- `src/rts_nano/game/pathfinding.py`
  Provides grid A* pathfinding. It accepts a movement predicate supplied by the
  manager, so pathfinding does not depend directly on terrain implementation.

- `src/rts_nano/game/rules.py`
  Pure helper rules for distance, damage, height bonuses, clamping, and nearest
  entity selection.

- `src/rts_nano/map_editor.py`
  Standalone pygame map editor. It edits the same JSON files the game loads.

- `src/rts_nano/map_schema.py`
  TypedDict-based schema definitions plus map validation/loading helpers.

- `src/rts_nano/validate_map.py`
  CLI validator: `python -m rts_nano.validate_map src/rts_nano/maps/map_settings_01.json`.

- `src/rts_nano/headless.py`
  No-render simulation wrapper for tests and future RL work.

## One Frame

1. `main.py` refreshes the manager viewport size and mouse position from the
   current pygame display surface.
2. Pygame events are read.
3. `main.py` handles process-level events: quit and fullscreen toggles.
4. All other events are forwarded to `GameManager.handle_input`.
5. `GameManager.update` advances camera, units, harvesting, projectiles, click
   markers, and victory detection.
6. `main.py` clears the display surface.
7. `GameManager.draw` renders the world area, entities, VFX, selection box,
   HUD, bottom menu, minimap, and optional F10 menu.
8. `pygame.display.flip()` presents the frame.

## Coordinate Model

- Entity, terrain, path, resource, and order coordinates are world coordinates.
- The camera is stored as `camera_x/camera_y`.
- Rendering subtracts camera offset to obtain screen coordinates.
- HUD, bottom panel, menus, and minimap are screen-space overlays.
- Fullscreen does not stretch a fixed 1600x720 buffer; the game renders directly
  to the current display surface and the viewport grows/shrinks.

## Ownership Boundaries

- Add gameplay rules in entity classes only when the rule is local to that
  entity.
- Add cross-entity systems in `GameManager`.
- Add terrain collision/height behavior in `TerrainMap`.
- Add serialized map types and validation in `map_schema.py`.
- Add editor-only tools in `map_editor.py`.

## Useful Commands

```powershell
uv run python -m rts_nano.main
uv run python -m rts_nano.map_editor --map map_settings_01.json
uv run python -m rts_nano.validate_map src/rts_nano/maps/map_settings_01.json
uv run pytest
uv run ruff check src tests
```
