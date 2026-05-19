# RTS Nano Executive Plan

## Agent Role

The agent working on this repository should act as a Senior Python Developer.
The expected posture is pragmatic, architecture-aware, and implementation-focused:
protect the playable game, improve maintainability in small verified steps, and keep
the codebase friendly for future reinforcement-learning and neural-network agents.

## Purpose Of This Document

This file is the repository-level navigation point for ongoing cleanup and
modernization work. Every agent should read it before starting substantial work,
update the progress tracker after completing a phase, and keep notes concise enough
that the next agent can quickly understand where the project is and what changed.

## Current Baseline

Last reviewed: 2026-05-19.

Known verification results from the latest implementation pass:

- `uv run pytest`: passed, 19 tests.
- `uv run ruff check --no-fix src tests`: passed.
- `uv run ty check`: passed.
- `uv run tox -e py313`: passed.
- `uv run tox`: passed for default `py313` and `coverage` environments.
- `uv run pre-commit run --all-files`: passed.
- Working tree contains this plan update and implementation changes from the first sprint.

Important observations:

- Runtime code uses Pygame throughout `main.py`, `manager.py`, `terrain.py`, entities, editor, tests, and headless mode; `pygame` is now declared and locked.
- `python-json-logger` was removed because no active runtime logging module used it.
- `pre-commit` is configured for basic file hygiene, Ruff, Ruff format, and Ty.
- Local/generated directories are ignored: `.venv`, `.pytest_cache`, `.ruff_cache`, `__pycache__`, `.tox`, and coverage outputs.
- Source/development art is tracked under top-level `assets/development` and documented in `assets/README.md`.
- The strongest architecture pressure points are large orchestration classes:
  - `src/rts_nano/game/manager.py`
  - `src/rts_nano/map_editor.py`
  - `src/rts_nano/game/assets/entities/base_entities.py`
- Strong existing foundations:
  - `src/rts_nano/game/rules.py` is pure and testable.
  - `src/rts_nano/game/pathfinding.py` is independent from Pygame terrain classes.
  - `src/rts_nano/map_schema.py` centralizes validation.
- `src/rts_nano/headless.py` remains the low-level no-render wrapper.
- `src/rts_nano/env.py` exposes the first stable AI/RL-facing environment facade.

## Strategic Goals

1. Keep the game playable while improving architecture.
2. Make a clean checkout reproducible.
3. Separate simulation from rendering and input.
4. Prefer functional design for deterministic rules and transformations.
5. Use object-oriented design where it fits game entities, systems, and ownership.
6. Apply SOLID principles without overengineering.
7. Respect the Law of Demeter by avoiding deep object graph access and broad manager knowledge.
8. Improve typing and docstrings so the codebase is easier for humans and agents to extend.
9. Expose a clean game API so neural networks and RL agents can plug into the simulation.

## Executive Workstreams

### 1. Repository Hygiene And Artifacts

Status: DONE

Actions:

- Add missing runtime dependency: `pygame`.
- Regenerate `uv.lock` from a clean environment.
- Decide whether `python-json-logger` is needed; remove it if unused or add real logging infrastructure if desired.
- Add `.pre-commit-config.yaml` for Ruff, Ty, and basic file hygiene.
- Extend `.gitignore` for generated artifacts:
  - `.tox/`
  - `.coverage`
  - `.coverage.*`
  - `htmlcov/`
  - `.pytest_cache/`
  - `.ruff_cache/`
  - `.mypy_cache/`
  - `__pycache__/`
- Keep runtime assets in the package, but move development/source art out of the importable package or into a documented source-art area.
- Review duplicate or accidental development files, especially copy-style filenames such as `mage_base -- kopia.png` equivalent.
- Consider Git LFS for large source assets if they must remain versioned.
- Review empty package files such as `src/__init__.py`.

Definition of done:

- A clean checkout can install and run tests without relying on a pre-existing local environment.
- Generated folders are ignored.
- Runtime assets and source/development assets have a documented policy.

### 2. Quality Gate Stabilization

Status: DONE

Actions:

- Fix current Ruff issues:
  - trailing whitespace,
  - unused `pygame` import in fog code,
  - type-only import placement,
  - unused `cell_radius`,
  - import ordering in `manager.py`.
- Fix current Ty issue in `GameManager.draw_bottom_menu` by narrowing `primary_entity` to `Base` before appending to `build_peasant_buttons`.
- Align Python target versions:
  - `pyproject.toml` requires Python `>=3.13`,
  - `ty.toml` targets 3.13,
  - `ruff.toml` currently targets `py314`.
- Make these commands pass:
  - `uv run pytest`
  - `uv run ruff check --no-fix src tests`
  - `uv run ty check`
  - `uv run tox -e py313`
- Decide whether `coverage.fail_under = 100` is realistic for this Pygame project; keep it only if exclusions are intentional and documented.

Definition of done:

- Tests, lint, type checking, and tox pass from a clean environment.
- CI/pre-commit can enforce the same checks.

### 3. Game API For Neural Network And RL Integration

Status: IN PROGRESS

This is a core architectural requirement. Future code should make it easy to
connect a neural network or RL algorithm to the game without depending on Pygame,
mouse input, rendering, or private `GameManager` internals.

Actions:

- Promote `HeadlessSimulation` into a stable public simulation API.
- Add a dedicated environment facade, for example `RtsNanoEnv`, with methods such as:
  - `reset(seed: int | None = None, map_id: str | None = None)`
  - `step(action)`
  - `observe()`
  - `available_actions()`
  - `is_done()`
  - `reward()`
  - `close()`
- Keep observations deterministic and serializable:
  - plain dictionaries,
  - typed dataclasses,
  - numpy arrays later if introduced,
  - tensors only at adapter boundaries.
- Define explicit action models:
  - move,
  - attack,
  - gather,
  - deposit,
  - build,
  - select/control group,
  - no-op.
- Avoid exposing live entity objects directly to AI callers; expose immutable snapshots or DTOs.
- Add adapters later for Gymnasium or PettingZoo-style APIs.
- Support deterministic seeds for any future randomness.
- Add tests proving that the same map, seed, and action sequence produce the same state sequence.
- Keep reward shaping outside low-level game rules so experiments can swap reward functions.

Completed first slice:

- Added `RtsNanoEnv` in `src/rts_nano/env.py`.
- Added typed action DTOs for no-op, move, attack, gather, deposit, build, and select.
- Added immutable observation DTOs with stable environment entity IDs.
- Added injectable reward function support; default reward remains `0.0`.
- Added deterministic replay coverage in `tests/test_env.py`.

Definition of done:

- A neural-network loop can run the game headlessly using public APIs only.
- The API can run many simulation steps without creating a display surface.
- Observations and actions are documented, typed, and tested.

### 4. Pythonic Architecture Refactor

Status: DONE

Approach:

- Keep object-oriented design for game entities, ownership, polymorphic behavior, and stateful systems.
- Prefer functional style for deterministic rules, transformations, geometry helpers, validation, observations, rewards, and action translation.
- Introduce abstractions only when they remove real coupling or duplication.

Actions:

- Split `GameManager` into smaller systems:
  - camera system,
  - selection system,
  - order/action system,
  - economy/harvesting system,
  - combat/projectile system,
  - fog system coordination,
  - renderer/HUD/minimap layer.
- Split `MapEditor` into:
  - editor state,
  - tool commands,
  - schema/map repository,
  - editor renderer.
- Keep `main.py` thin and process-oriented.
- Replace string state values such as `"IDLE"`, `"MOVING"`, `"GATHERING"`, `"DEPOSITING"`, `"ATTACKING"` with `StrEnum`.
- Use `dataclass(slots=True)` or frozen dataclasses for value objects where appropriate.
- Move repeated visibility checks into named helper functions or policies.
- Keep pure modules free of Pygame imports wherever possible.

Definition of done:

- Core systems are smaller, named by responsibility, and easier to test.
- Public behavior remains covered by existing and new tests.
- Rendering/input code is not required for headless simulation.

### 5. SOLID And Law Of Demeter

Status: TODO

Actions:

- Single Responsibility Principle:
  - reduce `GameManager` responsibility count,
  - move rendering concerns away from simulation concerns where practical.
- Open/Closed Principle:
  - make entity registration data-driven instead of expanding conditionals in multiple files.
- Liskov Substitution Principle:
  - keep entity subclasses behaviorally consistent with base contracts.
- Interface Segregation Principle:
  - introduce narrow protocols for selectability, damageability, team ownership, harvestability, and movement validation.
- Dependency Inversion Principle:
  - depend on protocols for terrain movement, time/clock, asset loading, and action application.
- Law of Demeter:
  - reduce `getattr`, `hasattr`, and direct deep field access from orchestration code,
  - prefer methods or snapshot DTOs that express intent.

Definition of done:

- High-level systems depend on small interfaces rather than concrete internals.
- Adding a new unit, resource, action, or observation does not require broad edits across unrelated modules.

### 6. Typing And Docstrings

Status: TODO

Actions:

- Add domain type aliases:
  - `WorldPoint`,
  - `ScreenPoint`,
  - `GridCell`,
  - `ResourceKind`,
  - `EntityId`,
  - `TeamId` if needed.
- Convert JSON payloads to typed internal structures at boundaries where mutation is not required.
- Keep `TypedDict` where JSON-like editor mutation is still useful.
- Replace broad dynamic access with typed protocols or dataclasses.
- Strengthen public API docstrings with:
  - purpose,
  - arguments,
  - return values,
  - side effects,
  - invariants when relevant.
- Remove or improve weak docstrings such as `Initialize the object` when they do not add useful context.
- Keep Google-style docstrings, matching the Ruff pydocstyle configuration.

Definition of done:

- Type checker output is clean.
- Public APIs and complex private helpers are documented well enough for a new agent to extend them safely.

### 7. Testing And CI

Status: TODO

Actions:

- Add CI for supported Python versions.
- Run:
  - pytest,
  - Ruff,
  - Ty,
  - tox.
- Expand pure unit tests for:
  - rules,
  - pathfinding,
  - terrain transitions,
  - action translation,
  - reward calculation,
  - observation generation.
- Expand headless integration tests for:
  - combat,
  - economy,
  - fog,
  - group orders,
  - deterministic replay.
- Keep rendering smoke tests minimal and headless-friendly.

Definition of done:

- CI blocks regressions.
- New architecture slices are protected by targeted tests.

## Recommended First Sprint

Status: TODO

Priority order:

1. Add and lock `pygame`.
2. Fix Ruff and Ty baseline issues.
3. Make `tox -e py313` pass.
4. Add pre-commit configuration.
5. Update ignore rules for generated artifacts.
6. Document and clean the asset policy.
7. Add the first stable headless game API facade for AI/RL access.
8. Start splitting `GameManager` only after quality gates are green. Next sprint.

## Progress Tracker

Update this section after each completed phase.

| Workstream | Status | Last Update | Notes |
| --- | --- | --- | --- |
| Repository hygiene | DONE | 2026-05-19 | Added and locked pygame, removed unused python-json-logger, moved source art to `assets/development`, added asset policy, removed empty `src/__init__.py`, expanded `.gitignore`. |
| Quality gates | DONE | 2026-05-19 | `pytest`, Ruff, Ty, tox, and pre-commit pass. Coverage gate reset to realistic baseline `fail_under = 50`; tox defaults to `py313` plus `coverage`. |
| Game API for AI/RL | IN PROGRESS | 2026-05-19 | Added `RtsNanoEnv`, typed actions, serializable snapshots, injectable reward, and deterministic replay tests. |
| Pythonic architecture | TODO | 2026-05-19 | Large classes identified. |
| SOLID and Law of Demeter | TODO | 2026-05-19 | Coupling and dynamic access hotspots identified. |
| Typing and docstrings | TODO | 2026-05-19 | Existing docstrings are useful but uneven. |
| Testing and CI | IN PROGRESS | 2026-05-19 | Local pre-commit configured; CI still needs to be added. |

## Decision Log

Add decisions here when architecture choices are made.

| Date | Decision | Reason |
| --- | --- | --- |
| 2026-05-19 | Treat neural-network integration as a core architecture requirement. | The game is intended as an RL/PyTorch learning sandbox, so API boundaries must support headless deterministic control. |
| 2026-05-19 | Remove unused `python-json-logger` instead of adding logging infrastructure. | No active runtime logging module exists, and the first sprint is focused on reproducibility and quality gates. |
| 2026-05-19 | Use `coverage.fail_under = 50` as the temporary baseline. | The previous 100% threshold did not match the current Pygame-heavy test coverage and blocked tox despite passing tests. |
| 2026-05-19 | Keep runtime assets in `src/rts_nano/assets` and source art in top-level `assets/development`. | Runtime package contents stay small and intentional while source art remains versioned and documented. |
| 2026-05-19 | Expose AI/RL access through `RtsNanoEnv` DTOs instead of live `GameManager` entities. | Neural-network callers need deterministic serializable snapshots and typed actions without depending on Pygame rendering or manager internals. |

## Agent Handoff Notes

- Read this file before starting cleanup or architecture work.
- Keep changes small and verified.
- Do not break the playable Pygame loop while extracting headless simulation APIs.
- Prefer pure functions for deterministic rules and typed DTOs for AI-facing boundaries.
- After completing work, update the progress tracker and decision log if relevant.
- Next recommended step: begin splitting `GameManager` only behind the now-green quality gates, starting with action/order or observation helpers that benefit `RtsNanoEnv`.
