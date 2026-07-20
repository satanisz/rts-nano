# Aggressive Rally Sprint 2 Review

Date: 2026-07-20
Status: accepted

## Delivered

- Rally orders are simulation state on every production-capable building, not only the Base.
- Ground right-click sets a move rally for Base, Arsenal, Spire, Pit, and Chem-Vat producers.
- Right-click on a visible hostile unit or building sets an attack-move rally.
- Aggressive rally stores the clicked world position rather than tracking an enemy through fog.
- Newly produced military units receive attack-move through the existing deterministic order path.
- Base resource rally retains its gather behavior; military producers treat resource clicks as
  ordinary move destinations.
- Selected producers display persistent green, gold, or red rally markers by order type.

Production remains independent of movement. It reports spawned producer/unit pairs to the runner,
and `OrderSystem` performs the handoff after spawn.

## Verification

- A Guardian spawned at an Arsenal receives and follows its move rally.
- Pygame enemy right-click creates an attack-move rally on a selected Arsenal.
- Moving the clicked enemy before production completes does not reveal or follow its new position.
- A resource click on a military producer creates a move rally, while existing Base gather-rally
  fallback tests remain green.

Final gate: 231 tests passed. The benchmark measured 15,237 idle steps/s, 100.9 steps/s with 400
units, 1.027 MiB peak Python memory, and 1,370 ms for two 400-unit group orders. No per-tick work
was added for idle rally points.
