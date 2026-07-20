# RL Environment Contract

This document freezes the Plan 07 boundary before runtime implementation.

## Episode rules

The default RL episode limit is 36,000 simulation frames. Natural victory or draw sets
`terminated`; reaching the limit without a result sets `truncated`. A result reached on the final
allowed frame takes precedence. A completed environment rejects further steps until `reset()`.

## Joint decision rules

`step_joint()` accepts at most 16 ordered actions for each known team. Both batches are normalized
and validated against one immutable pre-step view, conflicts are resolved, accepted commands are
applied, and the simulation advances exactly once by the environment frame skip. Mapping insertion
order cannot affect results.

An illegal policy action is a reported no-op, not an exception. Configuration errors, unknown team
keys, stepping a closed environment, and stepping a completed episode remain exceptions. Resource,
activity-queue, exclusivity, and placement validation reserves claims in batch order. Placements
from opposing teams that would overlap reject both claims with `joint_conflict`.

## Strategic action rules

Unit and building content IDs come from the central gameplay registry rather than a second API
roster. Typed actions expose research, shared production/research cancellation, ground/resource/
enemy rally points, repairs, additional construction workers, and queued worker orders. They act
on explicit snapshot IDs and do not depend on the Pygame selection state.

Observation schema v3 exposes each team's faction, completed and reserved upgrades, plus the full
typed activity queue for every building. The legacy unit-only `production_queue` remains available
for existing consumers.

## Compatibility and single player

Legacy `step(Action)` retains scalar reward and action-owned frame count. Joint results return a
reward for each team, defaulting to zero when no team reward function is installed. The Pygame game
loop and ScriptedAI do not call `step_joint()` and must remain behaviorally unchanged.
