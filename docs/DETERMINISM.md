# Determinism Contract

RTS Nano produces the same gameplay state for the same map, initial state, ordered commands, and
number of ticks on the supported runtime.

## Guarantees

- `EntityStore` assigns monotonic IDs and iterates in creation order.
- Team, category, and content indexes preserve that order.
- System order is fixed by `SimulationRunner`.
- Spatial cells and pathfinding neighbors use deterministic traversal and tie-breaking.
- Safe production spawn sorts candidates by distance, then world Y and X.
- Output events are ordered by simulation processing and cleared at the next tick.
- Rendering, frame rate, asset availability, camera, selection, and SDL state cannot change rules.
- Headless and rendered execution share the same simulation and are parity-tested.

The simulation does not promise replay compatibility after an approved gameplay correction. Such a
change must update the readable golden checkpoint and SHA-256 digest together, explain the changed
fields in the sprint review, and prove repeated fresh runs remain equal.

## Replay gate

`tests/test_deterministic_replay.py` runs a versioned scenario twice, compares readable checkpoints,
and checks the stored digest. To investigate a failure, diff `tests/golden/core_replay_v1.json`
before considering a rebaseline. Never update the digest merely to make a failing test pass.

`tests/test_technology_replay.py` independently protects doctrine completion, Mage energy and
cooldowns, temporary effects, and cross-faction status application. Area abilities and pack
bonuses use bounded spatial queries, stable entity-ID ordering, and explicit target/contributor
caps. UI graph generation reads immutable definitions and never enters the simulation tick.

## Avoiding accidental nondeterminism

- Do not derive gameplay order from sets, wall-clock time, rendering frames, or object addresses.
- Sort new unordered inputs with an explicit stable key.
- Keep random behavior behind an explicit seeded generator owned by simulation state.
- Do not mutate the entity registry while iterating it; the runner uses a stable tick snapshot.
- Treat benchmark timing as observational only; it must not influence simulation decisions.
