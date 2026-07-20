# Technology and Ability Authoring

The immutable content registry is the single source of truth for research, doctrine choices,
abilities, producers, costs, prerequisites, and English labels. The windowed F9 view reads this
graph directly; do not maintain a second UI-only technology tree.

## Add an upgrade

1. Add one `UpgradeDefinition` to `UPGRADE_DEFINITIONS` in `content/registry.py`.
2. Use a stable lowercase ID, English display name and description, explicit faction, producer,
   integer cost, and research duration.
3. List every affected content ID. Express numeric changes with `StatModifier`; express bounded
   semantic mechanics with a named behavior handled by the pure simulation.
4. For a two-way doctrine, give both entries the same faction-specific `exclusive_group`. Every
   shipped exclusive group must contain exactly two choices.
5. Express follow-ups with `required_upgrades`. A prerequisite is an AND relationship; introduce an
   explicit shared parent if future design needs OR rather than hiding it in code.

## Add an ability

Add an immutable `AbilityDefinition`, grant its ID from an upgrade, then dispatch its typed effect
in `game/abilities.py`. Target candidates must come from a bounded spatial query, use stable entity
ID ordering, and obey `max_targets`. Spend energy and start cooldown only after a valid effect is
confirmed. Temporary state expires in `game/effects.py`; never mutate canonical definitions.

## Required checks

- Add focused existing-unit and future-spawn tests.
- Cover exclusivity, prerequisites, cancellation, target loss, caps, refresh/expiry, and payment.
- Run `validate_technology_graph()` and the full quality gate.
- Update the readable technology replay only for intentional deterministic behavior changes and
  record its new digest in the sprint review.
- Benchmark headless idle and 400-unit stress cases. Locked technology must have no per-tick cost.

AI policy, numeric balance exploration, rewards, observations, and RL actions are separate stages;
content authoring must not change them implicitly.
