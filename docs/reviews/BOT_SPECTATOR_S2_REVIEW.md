# Bot Spectator S2 — Read-only Observation

Date: 2026-10-29. Status: complete.

`PresentationState` owns `MatchView`, which supplies one visibility/inspection rule to world
drawing, effects, minimap, and clicks. Spectators start in All view; Tab cycles Blue/Red/All.
Separate presentation exploration grids refresh for both teams, including while another view is
selected. No bot vision/memory or simulation state is populated by the observer's full-map view.
Player visibility continues to use the existing fog-aware player policy.

Spectator gameplay keys return before command dispatch; world clicks inspect without routing
through player targeting; right-click/rally and command-card actions are blocked. Production cards
are replaced by observer help. The HUD shows both factions' banks, population, queues, buildings,
clock, perspective, and speed. Team views filter terrain/objects; the match-wide statistics remain
visible in each observer perspective.

P/Space pauses, R restarts, F9 inspects technology, F10 opens the working menu controls (including
speed), and F11 toggles fullscreen. Mouse/keyboard camera movement and minimap dragging remain.
The observer menu excludes the existing unsupported Save/Load placeholders and preserves a manual
pause when closed. Results say BLUE WINS/RED WINS/DRAW rather than assigning a human victory.
Restart resets view/exploration and transient input while preserving the selected participant mode.

Validation: **127 targeted tests passed**, including 14 new observer cases. They exercise actual
keyboard/mouse/card/rally attempts with funded producers and selected units/buildings, inspection
of both teams, perspective cycling, off-view exploration/reset, minimap/world pixel visibility,
pause/menu/speed/F9/restart/fullscreen, neutral results, and isolated bot knowledge. Existing player
fog, headless, command-card, result, render parity, AI, and application lifecycle tests pass.
Ruff, formatting, and ty pass. Whole-match acceptance and visual inspection follow in S3.
