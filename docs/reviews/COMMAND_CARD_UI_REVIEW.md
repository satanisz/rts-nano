# RTS Command Card UI Review

Date: 2026-07-24
Verdict: **APPROVED**

The player command card now follows a stable RTS-style 3x3 layout. Move, Stop, Hold, Attack Move,
Patrol, Gather, Return Cargo, and Build keep fixed positions and visible hotkeys. Move has an
explicit point-targeting mode while the existing right-click movement remains unchanged.

Peasants open a separate Build card derived from the central faction registry. AEGIS and RUST show
their complete current building trees, including disabled advanced buildings, costs, and required
prerequisites. Back/Escape returns to unit commands. Production buildings keep up to eight current
unit/research choices while active production uses the ninth Cancel slot, so the expanded Arsenal
tree no longer loses doctrine buttons.

## Presentation review

- Action commands use crisp code-native symbols; units and buildings reuse cached runtime art.
- Hover and active states have distinct borders and backgrounds.
- Disabled buttons stay visible and explain their resource, population, or prerequisite denial.
- Tooltips show the full non-truncated name, hotkey, description, cost, status, and requirements.
- Long descriptions wrap above the HUD instead of overflowing the card.
- Command fonts are shared within a render pass rather than created separately per button.
- No new raster assets, duplicate faction tables, or simulation-owned UI state were introduced.

## Validation

- Focused command, input, asset, headless, and presentation tests: 91 passed.
- Full suite: 322 passed; 74.73% coverage.
- Ruff format/lint and Ty: passed.
- ScriptedAI completes all three competitive maps through the full suite.
- Rendering-vs-headless deterministic snapshot test: passed.
- Manual dummy-SDL review covered root commands and the AEGIS Build submenu at 1600x720.
- Temporary screenshots were removed after review; the worktree contains source, tests, and docs only.

The change is presentation-focused. Game balance, AI, map data, RL contracts, and right-click order
semantics remain unchanged.
