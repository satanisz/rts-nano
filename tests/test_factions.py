"""Tests for faction signature mechanics (shields, and later poison/splash/frenzy)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rts_nano.game.assets.entities.base_entities import TeamColor
from rts_nano.game.observations import EntityIdRegistry, build_observation
from rts_nano.game.rules import apply_damage
from rts_nano.headless import HeadlessSimulation

if TYPE_CHECKING:
    from rts_nano.map_schema import MapSettings


def _settings() -> MapSettings:
    """Small map with a Blue (AEGIS) base/peasant and a far Red base."""
    return {
        "Blue": {"peasant": [[40, 40]], "base": [[80, 80]], "guardian": [], "marksman": [], "arclight": []},
        "Red": {"peasant": [], "base": [[760, 560]], "ripper": [], "spitter": [], "brute": []},
        "Resources": {"wood": [], "gold": []},
        "Terrain": {
            "width": 800,
            "height": 600,
            "high_ground": [],
            "water": [],
            "ramps": [],
            "rocks": [],
            "grass": [],
        },
    }


def _with_guardian() -> MapSettings:
    settings = _settings()
    settings["Blue"]["guardian"] = [[200, 200]]
    return settings


def test_apply_damage_drains_shield_before_life() -> None:
    """Damage hits the AEGIS shield buffer first, then spills into life."""
    simulation = HeadlessSimulation.from_settings(_with_guardian())
    guardian = simulation.manager.entities[TeamColor.BLUE].knights[0]
    assert (guardian.shield, guardian.shield_max, guardian.life) == (60, 60, 150)

    apply_damage(guardian, 20)
    assert guardian.shield == 40
    assert guardian.life == 150  # fully absorbed
    assert guardian.frames_since_damaged == 0  # hit restarts the regen delay

    spilled = apply_damage(guardian, 50)
    assert guardian.shield == 0
    assert guardian.life == 140  # 40 absorbed, 10 to life
    assert spilled == 10
    simulation.close()


def test_non_aegis_unit_has_no_shield() -> None:
    """RUST units carry no shield buffer; damage lands straight on life."""
    settings = _settings()
    settings["Red"]["ripper"] = [[300, 300]]
    simulation = HeadlessSimulation.from_settings(settings)
    ripper = simulation.manager.entities[TeamColor.RED].knights[0]

    assert ripper.shield_max == 0
    assert ripper.shield == 0

    apply_damage(ripper, 10)
    assert ripper.life == 35  # 45 - 10
    assert ripper.shield == 0
    simulation.close()


def test_shield_regenerates_after_out_of_combat_delay() -> None:
    """A damaged shield only regenerates once the regen delay has elapsed."""
    simulation = HeadlessSimulation.from_settings(_with_guardian())
    manager = simulation.manager
    guardian = manager.entities[TeamColor.BLUE].knights[0]

    apply_damage(guardian, 30)
    assert guardian.shield == 30

    # During the out-of-combat delay the shield holds steady.
    for _ in range(guardian.shield_regen_delay):
        manager.effects.update()
    assert guardian.shield == 30

    # Past the delay it recovers and caps at the maximum.
    for _ in range(400):
        manager.effects.update()
    assert guardian.shield == 60
    simulation.close()


def test_new_hit_restarts_shield_regen_delay() -> None:
    """Taking fresh damage resets the regen delay, pausing recovery again."""
    simulation = HeadlessSimulation.from_settings(_with_guardian())
    manager = simulation.manager
    guardian = manager.entities[TeamColor.BLUE].knights[0]

    apply_damage(guardian, 20)  # shield 40
    for _ in range(guardian.shield_regen_delay):
        manager.effects.update()
    apply_damage(guardian, 5)  # shield 35, delay restarts
    assert guardian.shield == 35

    for _ in range(100):  # still inside the restarted delay window
        manager.effects.update()
    assert guardian.shield == 35
    simulation.close()


def test_observation_exposes_shield_buffer() -> None:
    """Snapshots report shield/shield_max so RL agents can see the buffer."""
    simulation = HeadlessSimulation.from_settings(_with_guardian())
    observation = build_observation(simulation.manager, tick=0, registry=EntityIdRegistry())

    guardian = next(entity for entity in observation.entities if entity.kind == "Guardian")
    assert (guardian.shield, guardian.shield_max) == (60, 60)

    peasant = next(entity for entity in observation.entities if entity.kind == "Peasant")
    assert (peasant.shield, peasant.shield_max) == (0, 0)
    simulation.close()


def test_shield_absorbs_damage_in_live_combat() -> None:
    """A guardian under fire loses shield before any life is lost."""
    settings = _settings()
    settings["Blue"]["guardian"] = [[300, 300]]
    settings["Red"]["ripper"] = [[330, 300]]
    simulation = HeadlessSimulation.from_settings(settings)
    manager = simulation.manager
    guardian = manager.entities[TeamColor.BLUE].knights[0]
    ripper = manager.entities[TeamColor.RED].knights[0]

    # Make the ripper attack the guardian.
    manager.issue_attack_move_order(TeamColor.RED, guardian.get_center(), [ripper])
    for _ in range(120):
        simulation.step(1)
        if guardian.shield < guardian.shield_max:
            break

    assert guardian.shield < guardian.shield_max
    assert guardian.life == guardian.max_life  # shield soaked the early hits
    simulation.close()
