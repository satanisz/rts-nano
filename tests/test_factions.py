"""Tests for faction signature mechanics (shields, and later poison/splash/frenzy)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rts_nano.ai import ScriptedAI
from rts_nano.game.constants import POISON_INTERVAL
from rts_nano.game.observations import EntityIdRegistry, build_observation
from rts_nano.game.rules import apply_damage, apply_poison
from rts_nano.headless import HeadlessSimulation
from rts_nano.simulation.entities.base import TeamColor

if TYPE_CHECKING:
    from rts_nano.map_schema import MapSettings


def _settings() -> MapSettings:
    """Small map with a Blue (AEGIS) base/peasant and a far Red base."""
    return {
        "schema_version": 2,
        "Blue": {
            "faction_id": "AEGIS",
            "peasant": [[40, 40]],
            "base": [[80, 80]],
            "guardian": [],
            "marksman": [],
            "arclight": [],
        },
        "Red": {"faction_id": "RUST", "peasant": [], "base": [[760, 560]], "ripper": [], "spitter": [], "brute": []},
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


def _with_ripper() -> MapSettings:
    """A lone RUST ripper makes a clean, unshielded poison target."""
    settings = _settings()
    settings["Red"]["ripper"] = [[300, 300]]
    return settings


def test_apply_damage_drains_shield_before_life() -> None:
    """Damage hits the AEGIS shield buffer first, then spills into life."""
    simulation = HeadlessSimulation.from_settings(_with_guardian())
    guardian = simulation.manager.state.entities_by_content_id("guardian", team=TeamColor.BLUE)[0]
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
    ripper = simulation.manager.state.entities_by_content_id("ripper", team=TeamColor.RED)[0]

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
    guardian = manager.state.entities_by_content_id("guardian", team=TeamColor.BLUE)[0]

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
    guardian = manager.state.entities_by_content_id("guardian", team=TeamColor.BLUE)[0]

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
    guardian = manager.state.entities_by_content_id("guardian", team=TeamColor.BLUE)[0]
    ripper = manager.state.entities_by_content_id("ripper", team=TeamColor.RED)[0]

    # Make the ripper attack the guardian.
    manager.issue_attack_move_order(TeamColor.RED, guardian.get_center(), [ripper])
    for _ in range(120):
        simulation.step(1)
        if guardian.shield < guardian.shield_max:
            break

    assert guardian.shield < guardian.shield_max
    assert guardian.life == guardian.max_life  # shield soaked the early hits
    simulation.close()


# --- Poison (RUST) -------------------------------------------------------------


def test_poison_attacker_stats() -> None:
    """Only the RUST chem units inflict poison; rippers and AEGIS do not."""
    settings = _settings()
    settings["Red"]["spitter"] = [[300, 300]]
    settings["Red"]["brute"] = [[340, 300]]
    settings["Red"]["ripper"] = [[380, 300]]
    settings["Blue"]["guardian"] = [[200, 200]]
    simulation = HeadlessSimulation.from_settings(settings)
    manager = simulation.manager
    spitter = manager.state.entities_by_content_id("spitter", team=TeamColor.RED)[0]
    brute = manager.state.entities_by_content_id("brute", team=TeamColor.RED)[0]
    ripper = manager.state.entities_by_content_id("ripper", team=TeamColor.RED)[0]
    guardian = manager.state.entities_by_content_id("guardian", team=TeamColor.BLUE)[0]

    assert (spitter.poison_damage, spitter.poison_duration) == (2, 90)
    assert (brute.poison_damage, brute.poison_duration) == (3, 120)
    assert ripper.poison_damage == 0  # ripper relies on frenzy, not poison
    assert guardian.poison_damage == 0
    simulation.close()


def test_apply_poison_refreshes_not_stacks() -> None:
    """A second poison application refreshes the timer instead of stacking damage."""
    simulation = HeadlessSimulation.from_settings(_with_ripper())
    manager = simulation.manager
    ripper = manager.state.entities_by_content_id("ripper", team=TeamColor.RED)[0]

    apply_poison(ripper, 2, 90)
    assert (ripper.poison_tick_damage, ripper.poison_remaining_frames) == (2, 90)

    for _ in range(20):
        manager.effects.update()
    assert ripper.poison_remaining_frames == 70

    apply_poison(ripper, 2, 90)
    assert ripper.poison_remaining_frames == 90  # refreshed, not 70 + 90
    assert ripper.poison_tick_damage == 2  # not stacked to 4
    simulation.close()


def test_poison_deals_periodic_damage_then_expires() -> None:
    """Poison drains life on the interval cadence and stops once it runs out."""
    simulation = HeadlessSimulation.from_settings(_with_ripper())
    manager = simulation.manager
    ripper = manager.state.entities_by_content_id("ripper", team=TeamColor.RED)[0]
    start_life = ripper.life

    apply_poison(ripper, 2, 3 * POISON_INTERVAL)

    for _ in range(POISON_INTERVAL):
        manager.effects.update()
    assert ripper.life == start_life - 2  # one tick

    for _ in range(2 * POISON_INTERVAL):
        manager.effects.update()
    assert ripper.life == start_life - 6  # three ticks total
    assert ripper.poison_remaining_frames == 0
    assert ripper.poison_tick_damage == 0

    for _ in range(2 * POISON_INTERVAL):
        manager.effects.update()
    assert ripper.life == start_life - 6  # expired: no further damage
    simulation.close()


def test_poison_drains_shield_on_aegis_target() -> None:
    """Poison ticks route through the shield buffer before life, like any damage."""
    simulation = HeadlessSimulation.from_settings(_with_guardian())
    manager = simulation.manager
    guardian = manager.state.entities_by_content_id("guardian", team=TeamColor.BLUE)[0]

    apply_poison(guardian, 2, 3 * POISON_INTERVAL)
    for _ in range(POISON_INTERVAL):
        manager.effects.update()

    assert guardian.shield == guardian.shield_max - 2
    assert guardian.life == guardian.max_life
    simulation.close()


def test_spitter_applies_poison_in_live_combat() -> None:
    """A spitter's landed shot leaves lingering poison on its target."""
    settings = _settings()
    settings["Blue"]["guardian"] = [[300, 300]]
    settings["Red"]["spitter"] = [[400, 300]]
    simulation = HeadlessSimulation.from_settings(settings)
    manager = simulation.manager
    guardian = manager.state.entities_by_content_id("guardian", team=TeamColor.BLUE)[0]
    spitter = manager.state.entities_by_content_id("spitter", team=TeamColor.RED)[0]

    manager.issue_attack_move_order(TeamColor.RED, guardian.get_center(), [spitter])
    for _ in range(200):
        simulation.step(1)
        if guardian.poison_remaining_frames > 0:
            break

    assert guardian.poison_tick_damage == 2
    assert guardian.poison_remaining_frames > 0
    simulation.close()


# --- Splash (Arclight) ---------------------------------------------------------


def test_arclight_splash_hits_nearby_enemies() -> None:
    """An arclight's shot mirrors its damage onto enemies near the primary target."""
    settings = _settings()
    settings["Blue"]["arclight"] = [[300, 300]]
    settings["Red"]["ripper"] = [[400, 300], [440, 300]]  # 40px apart < 60 splash radius
    simulation = HeadlessSimulation.from_settings(settings)
    manager = simulation.manager
    arclight = manager.state.entities_by_content_id("arclight", team=TeamColor.BLUE)[0]
    primary, secondary = manager.state.entities_by_content_id("ripper", team=TeamColor.RED)

    # Drive a single resolved volley directly to isolate one splash.
    arclight._splash_candidates = [primary, secondary]
    arclight.attack_cooldown = 0
    dealt = arclight._attack(primary)

    assert dealt == 16
    assert primary.life == primary.max_life - 16  # direct hit, exactly once
    assert secondary.life == secondary.max_life - 16  # splashed for the same amount
    simulation.close()


def test_arclight_splash_spares_allies() -> None:
    """Splash only harms enemies; friendly units in the blast are untouched."""
    settings = _settings()
    settings["Blue"]["arclight"] = [[300, 300]]
    settings["Blue"]["guardian"] = [[420, 300]]  # ally inside the blast radius
    settings["Red"]["ripper"] = [[400, 300]]
    simulation = HeadlessSimulation.from_settings(settings)
    manager = simulation.manager
    arclight = manager.state.entities_by_content_id("arclight", team=TeamColor.BLUE)[0]
    ally = manager.state.entities_by_content_id("guardian", team=TeamColor.BLUE)[0]
    primary = manager.state.entities_by_content_id("ripper", team=TeamColor.RED)[0]

    arclight._splash_candidates = [primary, ally, arclight]
    arclight.attack_cooldown = 0
    arclight._attack(primary)

    assert primary.life == primary.max_life - 16
    assert ally.shield == ally.shield_max  # ally fully unscathed
    assert ally.life == ally.max_life
    simulation.close()


# --- Frenzy (RUST Ripper/Brute) ------------------------------------------------


def test_frenzy_speeds_attacks_when_wounded() -> None:
    """A frenzied unit's cooldown shrinks once it drops below half life."""
    simulation = HeadlessSimulation.from_settings(_with_ripper())
    ripper = simulation.manager.state.entities_by_content_id("ripper", team=TeamColor.RED)[0]

    ripper.life = ripper.max_life
    healthy = ripper._attack_cooldown_frames()

    ripper.life = ripper.max_life // 2  # at/below the 50% threshold
    frenzied = ripper._attack_cooldown_frames()

    assert frenzied < healthy
    assert frenzied == max(1, int(healthy * ripper.FRENZY_COOLDOWN_MULTIPLIER))
    simulation.close()


def test_frenzy_threshold_is_half_life() -> None:
    """Frenzy engages only at or below half life, not just above it."""
    simulation = HeadlessSimulation.from_settings(_with_ripper())
    ripper = simulation.manager.state.entities_by_content_id("ripper", team=TeamColor.RED)[0]
    base = max(1, int(ripper.attack_speed * 60))

    ripper.life = 23  # 23 > 0.5 * 45 -> no frenzy
    assert ripper._attack_cooldown_frames() == base

    ripper.life = 22  # 22 <= 22.5 -> frenzy
    assert ripper._attack_cooldown_frames() < base
    simulation.close()


def test_non_frenzy_unit_keeps_constant_attack_speed() -> None:
    """AEGIS units never frenzy: their cooldown is the same at full and low life."""
    simulation = HeadlessSimulation.from_settings(_with_guardian())
    guardian = simulation.manager.state.entities_by_content_id("guardian", team=TeamColor.BLUE)[0]

    full = guardian._attack_cooldown_frames()
    guardian.life = 1
    assert guardian._attack_cooldown_frames() == full
    simulation.close()


# --- Matchup smoke tests (each faction can win from a material advantage) -------


def _battlefield() -> MapSettings:
    return {
        "schema_version": 2,
        "Blue": {
            "faction_id": "AEGIS",
            "peasant": [],
            "base": [[80, 300]],
            "guardian": [],
            "marksman": [],
            "arclight": [],
        },
        "Red": {"faction_id": "RUST", "peasant": [], "base": [[720, 300]], "ripper": [], "spitter": [], "brute": []},
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


def test_aegis_army_can_destroy_rust_base() -> None:
    """An AEGIS strike force can march in and raze a lightly held RUST base."""
    settings = _battlefield()
    settings["Blue"]["guardian"] = [[600, 280], [600, 320], [620, 300]]
    settings["Blue"]["marksman"] = [[560, 290], [560, 310]]
    settings["Red"]["ripper"] = [[700, 300]]
    simulation = HeadlessSimulation.from_settings(settings)
    manager = simulation.manager
    red_base = manager.state.entities_by_content_id("base", team=TeamColor.RED)[0]
    army = manager.units_for_team(TeamColor.BLUE)

    manager.issue_attack_move_order(TeamColor.BLUE, red_base.get_center(), army)
    for _ in range(2500):
        simulation.step(1)
        if red_base.life <= 0:
            break

    assert red_base.life <= 0
    simulation.close()


def test_rust_swarm_can_destroy_aegis_base() -> None:
    """A RUST ripper swarm can overwhelm and destroy an undefended AEGIS base."""
    settings = _battlefield()
    settings["Red"]["ripper"] = [[200 + (i % 4) * 20, 280 + (i // 4) * 20] for i in range(8)]
    simulation = HeadlessSimulation.from_settings(settings)
    manager = simulation.manager
    blue_base = manager.state.entities_by_content_id("base", team=TeamColor.BLUE)[0]
    swarm = manager.units_for_team(TeamColor.RED)

    manager.issue_attack_move_order(TeamColor.RED, blue_base.get_center(), swarm)
    for _ in range(2500):
        simulation.step(1)
        if blue_base.life <= 0:
            break

    assert blue_base.life <= 0
    simulation.close()


def test_aegis_vs_rust_ai_game_progresses_to_engagement() -> None:
    """A fair AEGIS-vs-RUST AI game forms armies and engages (no hard stalemate)."""
    settings: MapSettings = {
        "schema_version": 2,
        "Blue": {"faction_id": "AEGIS", "peasant": [[120, 120], [150, 120], [120, 150]], "base": [[140, 160]]},
        "Red": {"faction_id": "RUST", "peasant": [[680, 460], [650, 460], [680, 430]], "base": [[660, 440]]},
        "Resources": {"wood": [[400, 280], [420, 280], [380, 300]], "gold": [[400, 320]]},
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
    simulation = HeadlessSimulation.from_settings(settings)
    manager = simulation.manager
    manager.teams[TeamColor.BLUE].resources.update({"wood": 2000, "gold": 1000})
    manager.teams[TeamColor.RED].resources.update({"wood": 2000, "gold": 1000})
    blue_ai = ScriptedAI(manager, TeamColor.BLUE, decision_interval=10)
    red_ai = ScriptedAI(manager, TeamColor.RED, decision_interval=10)

    engaged = False
    for _ in range(4000):
        blue_ai.step()
        red_ai.step()
        simulation.step(1)
        if manager.game_over_message:
            break
        units = [unit for team in manager.teams for unit in manager.units_for_team(team)]
        if any(unit.attack_move_destination is not None for unit in units):
            engaged = True
            break

    assert engaged or manager.game_over_message
    simulation.close()
