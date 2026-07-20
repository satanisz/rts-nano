# Match Restart Sprint 3 Review

Date: 2026-07-20
Status: accepted

## Delivered

- Full terminal overlay with player-relative `VICTORY`, `DEFEAT`, and `DRAW` labels.
- Shared renderer/input hitboxes for `RESTART MATCH` and `QUIT GAME` actions.
- `R` restarts a completed match without allowing terminal input to reach the world.
- Restart creates a fresh `GameSession` from an immutable deep copy of the same map settings.
- Entity IDs, resources, queues, selection, camera, fog, effects, and tick count restart cleanly.
- Viewport and fullscreen preference survive restart; simulation speed returns to normal.
- Renderer, input, and presentation discard match-local transients while the Pygame asset cache is
  retained.
- The scripted opponent is rebound to the new session by the application shell.

Reconstructing the session is safer than manually clearing every subsystem and makes the reset
path identical to initial match creation. Restart remains an application operation and does not add
Pygame or lifecycle branches to the simulation runner.

## Verification

- A mutated running match restarts with the original entity-ID sequence, resources, and tick zero.
- Result labels are correct after switching the locally controlled team.
- Keyboard and both result buttons emit the correct application events.
- The terminal overlay renders through the dummy-compatible Pygame path.
- Reset retains the same `PygameAssets` cache object.

Final gate: 235 tests passed. The benchmark measured 15,242 idle steps/s, 141.2 steps/s with 400
units, 1.027 MiB peak Python memory, and 1,258 ms for two 400-unit group orders. Restart support
adds no work to the simulation tick and preserves the previous memory profile.
