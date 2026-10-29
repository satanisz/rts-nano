"""Presentation layer: draws the game world, HUD, minimap, and menus.

The renderer reads a ``GameSession`` (and its ``CommandPanel``) but never mutates
simulation state. Keeping it separate means the core can run headless without any
draw/font calls. World↔screen transforms still live on the manager because input
shares them; the renderer calls them read-only.
"""

from __future__ import annotations

from textwrap import wrap
from typing import TYPE_CHECKING

import pygame

from rts_nano.content import CONTENT
from rts_nano.game.constants import (
    BLUE,
    BOTTOM_MENU_HEIGHT,
    FOG_CELL_SIZE,
    FPS,
    GREEN,
    RED,
    WHITE,
    YELLOW,
)
from rts_nano.game.fog import FogOfWar
from rts_nano.game.ui.effects import ArcherShot, MagicMissile
from rts_nano.game.ui.match_result import (
    match_clock_label,
    match_result_buttons,
    match_result_detail,
    match_result_title,
)
from rts_nano.game.ui.order_display import unit_order_lines
from rts_nano.game.ui.pygame_assets import PygameAssets, building_glyph
from rts_nano.game.ui.selection_panel import PORTRAIT_SIZE, build_selection_panel_layout
from rts_nano.game.ui.state import PresentationState
from rts_nano.game.ui.tech_tree import build_tech_tree
from rts_nano.game.ui.terrain_renderer import TerrainRenderer
from rts_nano.simulation.entities import TeamColor, Wood
from rts_nano.simulation.entities.base import Building, Entity, Resource, Unit
from rts_nano.simulation.entities.units import CasterUnit

if TYPE_CHECKING:
    from rts_nano.application import GameSession
    from rts_nano.game.ui.command_panel import CommandButton
    from rts_nano.simulation.geometry import Rect

WOOD_ICON = "\U0001fab5"
GOLD_ICON = "\U0001fa99"


class GameRenderer:
    """Draws the current state of a ``GameSession`` to a display surface."""

    def __init__(
        self,
        assets: PygameAssets | None = None,
        presentation: PresentationState | None = None,
    ) -> None:
        """Create presentation-owned asset and facing caches."""
        self.assets = assets or PygameAssets()
        self.presentation = presentation or PresentationState()
        self._unit_facing: dict[int, tuple[float, str]] = {}
        self._hit_flash_until_tick: dict[int, int] = {}
        self._magic_missiles: list[MagicMissile] = []
        self._archer_shots: list[ArcherShot] = []
        self._last_effect_tick = -1
        self._terrain_renderer = TerrainRenderer()

    def draw(self, screen: pygame.Surface, manager: GameSession) -> None:
        """Draw world entities, selection state, HUD, minimap, and overlays."""
        screen_width = manager.screen_width
        play_area_height = manager.play_area_height
        screen_height = manager.screen_height

        self.presentation.view.refresh(manager)
        fog = self.presentation.view.fog_for(manager)
        self._update_effects(manager)

        world_surface = screen.subsurface(pygame.Rect(0, 0, screen_width, play_area_height))
        camera_offset = (manager.camera_x, manager.camera_y)

        self._terrain_renderer.draw(world_surface, manager.terrain, camera_offset)

        for entity in manager.all_entities:
            if self.presentation.view.can_inspect(manager, entity):
                self._draw_entity(
                    world_surface,
                    entity,
                    camera_offset,
                    manager.state.tick_count,
                    entity in manager.selected_entities,
                )

        self._draw_rally_points(world_surface, manager, camera_offset)

        for missile in self._magic_missiles:
            if fog is None or fog.is_visible(missile.x, missile.y):
                missile.draw(world_surface, camera_offset)
        for shot in self._archer_shots:
            if fog is None or fog.is_visible(shot.x, shot.y):
                shot.draw(world_surface, camera_offset)
        now_ms = pygame.time.get_ticks()
        self.presentation.click_markers = [
            marker for marker in self.presentation.click_markers if marker.is_alive(now_ms)
        ]
        for marker in self.presentation.click_markers:
            marker.draw(world_surface, camera_offset)

        self._draw_pending_construction(world_surface, camera_offset, manager)

        if fog is not None:
            self._draw_world_fog(world_surface, manager, fog)

        if manager.dragging and manager.drag_start and manager.drag_end:
            x1, y1 = manager._world_to_screen(manager.drag_start)
            x2, y2 = manager._world_to_screen(manager.drag_end)
            min_x = min(x1, x2)
            max_x = max(x1, x2)
            min_y = min(y1, y2)
            max_y = max(y1, y2)
            width = max_x - min_x
            height = max_y - min_y
            selection_surface = pygame.Surface((width, height), pygame.SRCALPHA)
            selection_surface.fill((0, 255, 0, 50))
            screen.blit(selection_surface, (min_x, min_y))
            pygame.draw.rect(screen, GREEN, (min_x, min_y, width, height), 2)

        if manager.paused and not manager.menu_active and manager.game_over_message is None:
            font = pygame.font.SysFont(None, 36)
            pause_text = font.render("- PAUSED -", True, WHITE)
            text_rect = pause_text.get_rect(center=(screen_width // 2, screen_height // 2))
            screen.blit(pause_text, text_rect)

        if self.presentation.view.is_spectator:
            self._draw_spectator_hud(screen, manager)
        else:
            self._draw_player_hud(screen, manager)
        self._draw_bottom_menu(screen, manager)
        self._draw_minimap(screen, manager)
        if self.presentation.view.is_spectator:
            self._draw_spectator_controls(screen, manager)

        if manager.game_over_message is not None:
            self._draw_match_result(screen, manager)
        elif self.presentation.tech_tree_visible:
            self._draw_tech_tree(screen, manager)
        elif manager.menu_active:
            self._draw_main_menu(screen, manager)

    @staticmethod
    def _draw_world_fog(surface: pygame.Surface, manager: GameSession, fog: FogOfWar) -> None:
        """Draw one view's fog without changing any exploration data."""
        width, height = surface.get_size()
        fog_surf = pygame.Surface((width, height), pygame.SRCALPHA)
        fog_surf.fill((0, 0, 0, 255))
        start_col = max(0, int(manager.camera_x // FOG_CELL_SIZE))
        end_col = min(fog.cols - 1, int((manager.camera_x + width) // FOG_CELL_SIZE))
        start_row = max(0, int(manager.camera_y // FOG_CELL_SIZE))
        end_row = min(fog.rows - 1, int((manager.camera_y + height) // FOG_CELL_SIZE))
        for row in range(start_row, end_row + 1):
            for col in range(start_col, end_col + 1):
                state = fog.grid[row][col]
                if state > 0:
                    rect = pygame.Rect(
                        int(col * FOG_CELL_SIZE - manager.camera_x),
                        int(row * FOG_CELL_SIZE - manager.camera_y),
                        FOG_CELL_SIZE + 1,
                        FOG_CELL_SIZE + 1,
                    )
                    fog_surf.fill((0, 0, 0, 0 if state == FogOfWar.VISIBLE else 150), rect)
        surface.blit(fog_surf, (0, 0))

    @staticmethod
    def _draw_player_hud(screen: pygame.Surface, manager: GameSession) -> None:
        """Keep the existing player economy/clock presentation."""
        font = pygame.font.SysFont(None, 36)
        emoji_font = pygame.font.SysFont(["Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji", "Noto Emoji"], 20)
        team_group = manager.teams.get(manager.current_team)
        ui_color = BLUE if manager.current_team == TeamColor.BLUE else RED

        if team_group:
            res = team_group.resources
            num_buildings = len(manager.state.buildings_for_team(manager.current_team))
            population = manager.state.population_for_team(manager.current_team)
            queued_population = manager.production.queued_population_for_team(manager.current_team)
            population_cap = manager.population_cap_for_team(manager.current_team)
        else:
            res = {"wood": 0, "gold": 0}
            num_buildings = 0
            population = 0
            queued_population = 0
            population_cap = 0

        at_population_cap = population + queued_population >= population_cap
        population_color = (255, 90, 90) if at_population_cap else ui_color
        hud_parts: list[pygame.Surface] = [
            font.render(f"Team {manager.current_team.value} | ", True, ui_color),
            emoji_font.render(WOOD_ICON, True, ui_color),
            font.render(f": {res['wood']}   ", True, ui_color),
            emoji_font.render(GOLD_ICON, True, ui_color),
            font.render(f": {res['gold']} | Buildings: {num_buildings}   ", True, ui_color),
            font.render(
                f"Population: {population}/{population_cap} (+{queued_population} queued)", True, population_color
            ),
            font.render(f" | {match_clock_label(manager)}", True, ui_color),
        ]

        hud_x = 10
        hud_y = 10
        for part_surface in hud_parts:
            screen.blit(part_surface, (hud_x, hud_y))
            hud_x += part_surface.get_width()

    def _draw_spectator_hud(self, screen: pygame.Surface, manager: GameSession) -> None:
        """Show the observer view and both sides' public match statistics."""
        background = pygame.Surface((manager.screen_width, 90), pygame.SRCALPHA)
        background.fill((12, 17, 24, 225))
        screen.blit(background, (0, 0))
        font = pygame.font.SysFont(None, 26)
        header = (
            f"SPECTATOR | View: {self.presentation.view.label} | "
            f"{match_clock_label(manager)} | Speed: {manager.fps_multiplier:g}x"
        )
        screen.blit(font.render(header, True, WHITE), (10, 10))
        for index, team in enumerate((TeamColor.BLUE, TeamColor.RED)):
            state = manager.state.team(team)
            if state is None:
                continue
            population = manager.state.population_for_team(team)
            capacity = manager.population_cap_for_team(team)
            queued = manager.production.queued_population_for_team(team)
            buildings = len(manager.state.buildings_for_team(team))
            label = (
                f"{team.value} ({state.faction_id}) | Wood: {state.resources['wood']} | Gold: {state.resources['gold']} | "
                f"Population: {population}/{capacity} (+{queued} queued) | Buildings: {buildings}"
            )
            color = (145, 180, 255) if team == TeamColor.BLUE else (255, 145, 145)
            available_width = manager.screen_width - 20
            label_font = font
            if font.size(label)[0] > available_width:
                label_font = pygame.font.SysFont(None, max(16, int(26 * available_width / font.size(label)[0])))
            screen.blit(label_font.render(label, True, color), (10, 38 + index * 25))

    @staticmethod
    def _draw_spectator_controls(screen: pygame.Surface, manager: GameSession) -> None:
        """Replace gameplay command cards with persistent observer help."""
        left = manager.screen_width - 174
        top = manager.screen_height - BOTTOM_MENU_HEIGHT + 12
        font = pygame.font.SysFont(None, 18)
        lines = (
            "SPECTATOR",
            "Tab: All / Blue / Red",
            "Click: Inspect",
            "P / Space: Pause",
            "R: Restart",
            "F9: Technology",
            "F10: Menu / speed",
            "F11: Fullscreen",
        )
        for index, line in enumerate(lines):
            screen.blit(font.render(line, True, WHITE), (left, top + index * 19))

    def reset_match(self) -> None:
        """Clear match-local effects while preserving cached presentation assets."""
        self._unit_facing.clear()
        self._hit_flash_until_tick.clear()
        self._magic_missiles.clear()
        self._archer_shots.clear()
        self._last_effect_tick = -1

    def _draw_tech_tree(self, screen: pygame.Surface, manager: GameSession) -> None:
        """Draw the current faction tree from the canonical registry-derived view model."""
        team = manager.teams.get(manager.current_team)
        if team is None:
            return
        overlay = pygame.Surface((manager.screen_width, manager.screen_height), pygame.SRCALPHA)
        overlay.fill((8, 12, 18, 238))
        screen.blit(overlay, (0, 0))
        title_font = pygame.font.SysFont(None, 42)
        row_font = pygame.font.SysFont(None, 23)
        small_font = pygame.font.SysFont(None, 18)
        title = title_font.render(f"{team.faction_id} TECHNOLOGY TREE", True, WHITE)
        screen.blit(title, (32, 24))
        instructions = (
            "F9: close  |  Read-only team research overview"
            if self.presentation.view.is_spectator
            else "F9: close  |  Research at the listed production building"
        )
        hint = row_font.render(instructions, True, (170, 190, 210))
        screen.blit(hint, (32, 66))
        entries = build_tech_tree(team)
        column_width = max(360, (manager.screen_width - 96) // 2)
        row_height = 112
        for index, entry in enumerate(entries):
            column = index % 2
            row = index // 2
            x = 32 + column * (column_width + 24)
            y = 104 + row * row_height
            rect = pygame.Rect(x, y, column_width, row_height - 12)
            status_color = {
                "COMPLETED": (90, 220, 130),
                "AVAILABLE": (230, 205, 90),
                "RESEARCHING": (90, 180, 245),
            }.get(entry.status, (150, 155, 165))
            pygame.draw.rect(screen, (25, 31, 40), rect)
            pygame.draw.rect(screen, status_color, rect, 2)
            screen.blit(row_font.render(entry.name, True, WHITE), (x + 10, y + 8))
            status = small_font.render(entry.status, True, status_color)
            screen.blit(status, (rect.right - status.get_width() - 10, y + 10))
            screen.blit(
                small_font.render(f"At: {entry.producer}  |  {entry.cost}", True, (190, 205, 220)),
                (x + 10, y + 34),
            )
            screen.blit(
                small_font.render(f"Requires: {entry.requirement}", True, (170, 180, 195)),
                (x + 10, y + 54),
            )
            details = f"Affects/unlocks: {entry.unlocks} — {entry.description}"
            details = details[:92] + ("..." if len(details) > 92 else "")
            screen.blit(small_font.render(details, True, (210, 215, 220)), (x + 10, y + 75))

    @staticmethod
    def _draw_rally_points(
        screen: pygame.Surface,
        manager: GameSession,
        camera_offset: tuple[float, float],
    ) -> None:
        """Draw persistent rally lines for currently selected bases."""
        for entity in manager.selected_entities:
            if not isinstance(entity, Building) or entity.rally_order is None:
                continue
            destination = entity.rally_order.destination
            if destination is None:
                continue
            start = (int(entity.x - camera_offset[0]), int(entity.y - camera_offset[1]))
            end = (int(destination[0] - camera_offset[0]), int(destination[1] - camera_offset[1]))
            if entity.rally_order.kind == "gather":
                color = (230, 190, 40)
            elif entity.rally_order.kind == "attack_move":
                color = (255, 90, 90)
            else:
                color = (80, 255, 120)
            pygame.draw.line(screen, color, start, end, width=1)
            pygame.draw.circle(screen, color, end, 10, width=2)
            pygame.draw.line(screen, color, (end[0] - 5, end[1]), (end[0] + 5, end[1]), width=2)
            pygame.draw.line(screen, color, (end[0], end[1] - 5), (end[0], end[1] + 5), width=2)

    def _update_effects(self, manager: GameSession) -> None:
        """Consume each simulation tick's attack outputs exactly once."""
        tick = manager.state.tick_count
        if tick == self._last_effect_tick:
            return
        self._last_effect_tick = tick
        flash_duration = max(1, round(0.12 * FPS))
        for event in manager.recent_attacks:
            self._hit_flash_until_tick[int(event.attacker_id)] = tick + flash_duration
            effect_type = MagicMissile if str(event.attacker_content_id) in {"arclight", "mage"} else ArcherShot
            effect = effect_type(
                event.source[0],
                event.source[1],
                event.target[0],
                event.target[1],
                target_entity=event.target_entity,
            )
            if isinstance(effect, MagicMissile):
                self._magic_missiles.append(effect)
            else:
                self._archer_shots.append(effect)
        self._magic_missiles = [effect for effect in self._magic_missiles if effect.update()]
        self._archer_shots = [effect for effect in self._archer_shots if effect.update()]

    def _draw_entity(
        self,
        screen: pygame.Surface,
        entity: Entity,
        offset: tuple[float, float],
        tick: int,
        selected: bool,
    ) -> None:
        """Render a pure entity through presentation-owned state and assets."""
        offset_x, offset_y = offset
        draw_x = int(entity.x - offset_x)
        draw_y = int(entity.y - offset_y)
        size = int(entity.size)
        top_left = (draw_x - size // 2, draw_y - size // 2)

        key = int(entity.entity_id) if entity.entity_id is not None else id(entity)
        hitbox_color = YELLOW if tick < self._hit_flash_until_tick.get(key, 0) else entity.color
        pygame.draw.circle(screen, hitbox_color, (draw_x, draw_y), int(entity.radius + 2), 1)

        flipped = self._is_unit_flipped(entity)
        sprite = self.assets.sprite(entity, flipped=flipped)
        if sprite is not None:
            screen.blit(sprite, top_left)
        elif isinstance(entity, Building):
            self._draw_building_fallback(screen, entity, top_left, (draw_x, draw_y))
        else:
            pygame.draw.rect(screen, entity.color, (*top_left, size, size))

        if isinstance(entity, Building) and entity.is_under_construction:
            scaffold = pygame.Surface((size, size), pygame.SRCALPHA)
            scaffold.fill((20, 20, 20, 110))
            screen.blit(scaffold, top_left)
            pygame.draw.rect(
                screen,
                (80, 220, 120),
                (top_left[0], top_left[1] + size - 5, int(size * entity.construction_progress), 4),
            )

        if selected:
            pygame.draw.rect(screen, WHITE, (*top_left, size, size), 1)

    def _is_unit_flipped(self, entity: Entity) -> bool:
        """Track facing outside simulation and select the cached sprite variant."""
        if not isinstance(entity, Unit):
            return False
        key = int(entity.entity_id) if entity.entity_id is not None else id(entity)
        default_facing = "right" if entity.team == TeamColor.BLUE else "left"
        previous_x, facing = self._unit_facing.get(key, (entity.x, default_facing))
        dx = entity.x - previous_x
        if dx > 0.1:
            facing = "right"
        elif dx < -0.1:
            facing = "left"
        self._unit_facing[key] = (entity.x, facing)
        return facing != default_facing

    @staticmethod
    def _draw_building_fallback(
        screen: pygame.Surface,
        entity: Building,
        top_left: tuple[int, int],
        center: tuple[int, int],
    ) -> None:
        """Draw a typed placeholder when building art is unavailable."""
        size = int(entity.size)
        body_rect = pygame.Rect(*top_left, size, size)
        label, accent = building_glyph(str(entity.content_id))
        pygame.draw.rect(screen, (66, 68, 78), body_rect)
        pygame.draw.rect(screen, accent, pygame.Rect(top_left[0], top_left[1], size, max(6, size // 4)))
        pygame.draw.rect(screen, entity.color, body_rect, 3)
        glyph = pygame.font.SysFont(None, max(12, int(size * 0.5))).render(label, True, (235, 235, 235))
        screen.blit(glyph, glyph.get_rect(center=(center[0], center[1] + size // 8)))

    def _draw_pending_construction(
        self,
        screen: pygame.Surface,
        offset: tuple[float, float],
        manager: GameSession,
    ) -> None:
        """Draw a simple placement preview for the pending construction command."""
        building_type = manager.pending_construction_type
        builder = manager._pending_construction_builder()
        if building_type is None or builder is None or manager.mouse_pos[1] >= manager.play_area_height:
            return

        world_pos = manager._screen_to_world(manager.mouse_pos)
        can_start, _ = manager.construction.can_start_construction(builder, building_type, world_pos)
        color = (80, 255, 120) if can_start else (255, 80, 80)
        screen_pos = manager._world_to_screen(world_pos)
        definition = CONTENT.get_building(building_type)
        preview_rect = pygame.Rect(0, 0, definition.size, definition.size)
        preview_rect.center = screen_pos

        preview_surface = pygame.Surface((definition.size, definition.size), pygame.SRCALPHA)
        preview_surface.fill((*color, 55))
        screen.blit(preview_surface, preview_rect)
        pygame.draw.rect(screen, color, preview_rect, width=2)
        pygame.draw.circle(screen, color, screen_pos, int(definition.radius), width=1)

    def _draw_bottom_menu(self, screen: pygame.Surface, manager: GameSession) -> None:
        """Draw the selection details, portrait, and command-panel buttons."""
        screen_width = manager.screen_width
        screen_height = manager.screen_height

        menu_rect = pygame.Rect(0, screen_height - BOTTOM_MENU_HEIGHT, screen_width, BOTTOM_MENU_HEIGHT)
        pygame.draw.rect(screen, (40, 40, 40), menu_rect)
        pygame.draw.rect(screen, (200, 200, 200), menu_rect, 2)

        if not manager.selected_entities:
            return

        primary_entity = manager.selected_entities[0]

        portrait_size = PORTRAIT_SIZE
        layout = build_selection_panel_layout(len(manager.selected_entities), screen_width, screen_height)
        portrait_x = layout.portrait_x
        center_panel_x = layout.center_panel_x

        font_small = pygame.font.SysFont(None, 24)

        if len(manager.selected_entities) > 1:
            for entity, icon_rect in zip(manager.selected_entities, layout.icon_rects, strict=False):
                pos_x = icon_rect.x
                pos_y = icon_rect.y
                icon_size = icon_rect.width

                sprite = self.assets.sprite(entity)
                if sprite is not None:
                    small_img = pygame.transform.scale(sprite, (icon_size, icon_size))
                    screen.blit(small_img, (pos_x, pos_y))
                else:
                    pygame.draw.rect(screen, entity.color, icon_rect)

                if isinstance(entity, (Unit, Building)):
                    hp_pct = max(0, entity.life / entity.max_life)
                    hp_width = int(icon_size * hp_pct)
                    hp_rect = pygame.Rect(pos_x, pos_y + icon_size - 4, icon_size, 4)
                    pygame.draw.rect(screen, (50, 50, 50), hp_rect)
                    pygame.draw.rect(
                        screen, GREEN if hp_pct > 0.5 else RED, (pos_x, pos_y + icon_size - 4, hp_width, 4)
                    )

                pygame.draw.rect(screen, WHITE, icon_rect, 1)

        else:
            start_x = center_panel_x + 20
            start_y = screen_height - BOTTOM_MENU_HEIGHT + 15

            cls_name = type(primary_entity).__name__
            stats_texts = [f"{cls_name}"]

            if isinstance(primary_entity, Unit):
                stats_texts.append(f"HP: {primary_entity.life}/{primary_entity.max_life}")
                stats_texts.append(f"ATTACK: {primary_entity.attack_damage}")
                stats_texts.append(f"RANGE: {primary_entity.attack_range}")
                stats_texts.append(f"SHIELD: {primary_entity.shield_modifier}")
                if isinstance(primary_entity, CasterUnit):
                    stats_texts.append(f"ENERGY: {primary_entity.energy}/{primary_entity.energy_max}")
                stats_texts.extend(unit_order_lines(primary_entity))
            elif isinstance(primary_entity, Building):
                stats_texts.append(f"HP: {primary_entity.life}/{primary_entity.max_life}")
                if primary_entity.is_under_construction:
                    stats_texts.append(f"Build: {primary_entity.construction_progress:.0%}")
                    stats_texts.append(f"Builders: {manager.construction.active_builder_count(primary_entity)}")
                elif primary_entity.life < primary_entity.max_life:
                    stats_texts.append(f"Repairers: {manager.construction.active_repairer_count(primary_entity)}")
                stats_texts.append(f"SHIELD: {primary_entity.shield_modifier}")
                activity = manager.production.queue_for(primary_entity)
                if activity:
                    entry = activity[0]
                    if entry.kind == "research":
                        name = CONTENT.get_upgrade(entry.content_id).display_name
                        stats_texts.append(f"Research: {name} {entry.progress:.0%}")
                    else:
                        name = CONTENT.get_unit(entry.content_id).display_name
                        stats_texts.append(f"Training: {name} {entry.progress:.0%}")
                    if len(activity) > 1:
                        next_job = activity[1]
                        name = (
                            CONTENT.get_upgrade(next_job.content_id).display_name
                            if next_job.kind == "research"
                            else CONTENT.get_unit(next_job.content_id).display_name
                        )
                        stats_texts.append(f"Next: {name} ({len(activity) - 1} waiting)")
                team_state = manager.state.team(primary_entity.team)
                if team_state is not None and team_state.completed_upgrades:
                    completed_names = [
                        CONTENT.get_upgrade(str(upgrade_id)).display_name
                        for upgrade_id in team_state.completed_upgrades
                    ]
                    stats_texts.append(f"Completed: {', '.join(completed_names)}")
            elif isinstance(primary_entity, Resource):
                stats_texts.append(f"Amount: {primary_entity.amount}")

            for j, stat_text in enumerate(stats_texts):
                color = WHITE
                if j == 0 and hasattr(primary_entity, "team"):
                    if primary_entity.team == TeamColor.BLUE:
                        color = (130, 130, 255)
                    elif primary_entity.team == TeamColor.RED:
                        color = (255, 130, 130)

                text_surf = font_small.render(stat_text, True, color)
                screen.blit(text_surf, (start_x, start_y + j * 20))

        avatar_y = screen_height - BOTTOM_MENU_HEIGHT + (BOTTOM_MENU_HEIGHT - portrait_size) // 2
        frame_rect = pygame.Rect(portrait_x - 2, avatar_y - 2, portrait_size + 4, portrait_size + 4)

        portrait = self.assets.portrait(primary_entity, portrait_size)
        if portrait is not None:
            pygame.draw.rect(screen, (80, 80, 80), frame_rect)
            pygame.draw.rect(screen, WHITE, frame_rect, 2)
            screen.blit(portrait, (portrait_x, avatar_y))
        else:
            pygame.draw.rect(screen, (40, 42, 50), frame_rect)
            if isinstance(primary_entity, Building):
                label, accent = building_glyph(getattr(primary_entity, "spec_key", ""))
                pygame.draw.rect(screen, accent, pygame.Rect(portrait_x, avatar_y, portrait_size, portrait_size // 5))
                glyph = pygame.font.SysFont(None, 80).render(label, True, (235, 235, 235))
                screen.blit(
                    glyph, glyph.get_rect(center=(portrait_x + portrait_size // 2, avatar_y + portrait_size // 2))
                )
            pygame.draw.rect(screen, WHITE, frame_rect, 2)

        if self.presentation.view.is_spectator:
            return
        buttons = self.presentation.command_panel.build(manager, screen_width, screen_height)
        buttons_by_slot = {button.slot: button for button in buttons}
        hovered_button: CommandButton | None = None
        command_label_font = pygame.font.SysFont(None, 13)
        command_badge_font = pygame.font.SysFont(None, 13, bold=True)
        command_tooltip_font = pygame.font.SysFont(None, 17)
        for index, slot_rect in enumerate(self.presentation.command_panel.slot_rects(screen_width, screen_height)):
            button = buttons_by_slot.get(index)
            if button is None:
                pygame.draw.rect(screen, (25, 27, 30), slot_rect)
                pygame.draw.rect(screen, (55, 58, 62), slot_rect, 1)
                continue
            is_hovered = slot_rect.collidepoint(manager.mouse_pos)
            is_active = (
                button.action == manager.pending_unit_command
                or (button.action == "open_build_menu" and self.presentation.command_panel.page == "build")
                or (button.action == "construct" and button.building_type == manager.pending_construction_type)
            )
            if not button.enabled:
                bg_color = (37, 39, 42)
                border_color = (72, 74, 78)
            elif is_active:
                bg_color = (55, 88, 75)
                border_color = (105, 235, 170)
            elif is_hovered:
                bg_color = (91, 78, 43)
                border_color = (235, 194, 92)
            else:
                bg_color = (52, 56, 61)
                border_color = (130, 137, 145)
            pygame.draw.rect(screen, bg_color, slot_rect)
            pygame.draw.rect(screen, border_color, slot_rect, 2 if is_hovered or is_active else 1)
            self._draw_command_button(screen, manager, button, command_label_font, command_badge_font)
            if is_hovered:
                hovered_button = button
        if hovered_button is not None:
            self._draw_command_tooltip(screen, hovered_button, screen_width, screen_height, command_tooltip_font)

    def _draw_command_button(
        self,
        screen: pygame.Surface,
        manager: GameSession,
        button: CommandButton,
        label_font: pygame.font.Font,
        badge_font: pygame.font.Font,
    ) -> None:
        """Draw one compact icon, hotkey badge, label, and state overlay."""
        rect = button.rect
        icon_rect = pygame.Rect(rect.x + 9, rect.y + 3, 28, 28)
        content_id = button.unit_type or button.building_type
        content_icon = self.assets.content_icon(content_id, manager.current_team, 28) if content_id else None
        if content_icon is not None:
            if not button.enabled:
                content_icon = content_icon.copy()
                content_icon.set_alpha(85)
            screen.blit(content_icon, icon_rect)
        else:
            self._draw_command_glyph(screen, icon_rect, button.icon, button.enabled)

        if button.hotkey:
            badge = badge_font.render(button.hotkey, True, (255, 222, 116) if button.enabled else (125, 125, 125))
            screen.blit(badge, (rect.x + 2, rect.y + 1))

        label = button.label if len(button.label) <= 9 else f"{button.label[:8]}…"
        label_color = (235, 238, 240) if button.enabled else (120, 122, 125)
        label_surface = label_font.render(label, True, label_color)
        screen.blit(label_surface, label_surface.get_rect(center=(rect.centerx, rect.bottom - 7)))

        if button.status:
            pygame.draw.rect(screen, (150, 70, 52), (rect.right - 8, rect.y + 2, 6, 6))

    @staticmethod
    def _draw_command_glyph(
        screen: pygame.Surface,
        rect: pygame.Rect,
        icon: str,
        enabled: bool,
    ) -> None:
        """Draw crisp code-native RTS command symbols without loading assets."""
        color = (220, 226, 232) if enabled else (100, 103, 108)
        accent = (232, 176, 70) if enabled else color
        center = rect.center
        if icon == "move":
            pygame.draw.line(screen, color, (rect.left + 4, rect.bottom - 5), (rect.right - 6, rect.top + 6), 3)
            pygame.draw.polygon(
                screen,
                color,
                [(rect.right - 7, rect.top + 3), (rect.right - 3, rect.top + 11), (rect.right - 12, rect.top + 9)],
            )
        elif icon == "stop":
            pygame.draw.rect(screen, color, rect.inflate(-10, -10), 3)
        elif icon == "hold":
            pygame.draw.polygon(
                screen,
                color,
                [
                    (center[0], rect.top + 3),
                    (rect.right - 5, rect.top + 8),
                    (rect.right - 7, rect.bottom - 8),
                    (center[0], rect.bottom - 3),
                    (rect.left + 7, rect.bottom - 8),
                    (rect.left + 5, rect.top + 8),
                ],
                2,
            )
        elif icon == "attack_move":
            pygame.draw.circle(screen, accent, center, 9, 2)
            pygame.draw.line(screen, color, (rect.left + 3, rect.bottom - 4), (rect.right - 4, rect.top + 3), 3)
            pygame.draw.polygon(
                screen,
                color,
                [(rect.right - 4, rect.top + 2), (rect.right - 3, rect.top + 10), (rect.right - 11, rect.top + 3)],
            )
        elif icon == "patrol":
            pygame.draw.arc(screen, color, rect.inflate(-5, -5), 0.25, 3.2, 2)
            pygame.draw.arc(screen, color, rect.inflate(-5, -5), 3.4, 6.2, 2)
            pygame.draw.polygon(
                screen,
                color,
                [(rect.left + 4, center[1]), (rect.left + 9, center[1] - 4), (rect.left + 10, center[1] + 4)],
            )
            pygame.draw.polygon(
                screen,
                color,
                [(rect.right - 4, center[1]), (rect.right - 9, center[1] - 4), (rect.right - 10, center[1] + 4)],
            )
        elif icon == "gather":
            pygame.draw.line(screen, color, (rect.left + 7, rect.bottom - 4), (rect.right - 7, rect.top + 5), 3)
            pygame.draw.arc(screen, accent, (rect.left + 4, rect.top + 3, 18, 11), 3.2, 6.1, 3)
        elif icon == "return_cargo":
            pygame.draw.circle(screen, accent, (center[0] + 4, center[1] + 4), 7, 2)
            pygame.draw.line(screen, color, (rect.right - 3, rect.top + 5), (rect.left + 4, rect.top + 5), 2)
            pygame.draw.polygon(
                screen,
                color,
                [(rect.left + 3, rect.top + 5), (rect.left + 9, rect.top + 1), (rect.left + 9, rect.top + 9)],
            )
        elif icon == "build":
            pygame.draw.line(screen, color, (rect.left + 6, rect.bottom - 4), (rect.right - 7, rect.top + 5), 4)
            pygame.draw.rect(screen, accent, (rect.right - 13, rect.top + 3, 10, 7), 2)
        elif icon == "back":
            pygame.draw.line(screen, color, (rect.right - 4, center[1]), (rect.left + 6, center[1]), 3)
            pygame.draw.polygon(
                screen,
                color,
                [(rect.left + 4, center[1]), (rect.left + 11, center[1] - 6), (rect.left + 11, center[1] + 6)],
            )
        elif icon == "cancel":
            pygame.draw.line(screen, (220, 95, 85), (rect.left + 6, rect.top + 6), (rect.right - 6, rect.bottom - 6), 4)
            pygame.draw.line(screen, (220, 95, 85), (rect.right - 6, rect.top + 6), (rect.left + 6, rect.bottom - 6), 4)
        elif icon == "research":
            pygame.draw.rect(screen, color, (rect.left + 7, rect.top + 4, 14, 19), 2)
            pygame.draw.line(screen, accent, (rect.left + 10, rect.top + 10), (rect.right - 9, rect.top + 10), 2)
            pygame.draw.line(screen, accent, (rect.left + 10, rect.top + 15), (rect.right - 9, rect.top + 15), 2)
        elif icon == "ability":
            pygame.draw.polygon(
                screen,
                accent,
                [
                    (center[0], rect.top + 2),
                    (rect.right - 4, center[1]),
                    (center[0], rect.bottom - 2),
                    (rect.left + 4, center[1]),
                ],
                2,
            )
        else:
            pygame.draw.circle(screen, color, center, 8, 2)

    @staticmethod
    def _draw_command_tooltip(
        screen: pygame.Surface,
        button: CommandButton,
        screen_width: int,
        screen_height: int,
        font: pygame.font.Font,
    ) -> None:
        """Draw the full command name, cost, status, and description above the HUD."""
        title = button.label + (f" [{button.hotkey}]" if button.hotkey else "")
        body_lines = [
            wrapped for source_line in button.tooltip.splitlines() for wrapped in (wrap(source_line, width=42) or [""])
        ]
        lines = [title, *body_lines]
        if button.cost:
            lines.append(f"Cost: {button.cost}")
        if button.status:
            lines.append(button.status)
        width = 270
        height = 12 + len(lines) * 18
        x = max(8, screen_width - width - 190)
        y = max(8, screen_height - BOTTOM_MENU_HEIGHT - height - 6)
        box = pygame.Rect(x, y, width, height)
        pygame.draw.rect(screen, (17, 20, 24), box)
        pygame.draw.rect(screen, (205, 170, 80), box, 1)
        for index, line in enumerate(lines):
            if index == 0:
                color = (244, 213, 125)
            elif button.status and line == button.status:
                color = (235, 115, 92)
            else:
                color = (215, 218, 222)
            screen.blit(font.render(line, True, color), (x + 8, y + 7 + index * 18))

    def _draw_minimap(self, screen: pygame.Surface, manager: GameSession) -> None:
        """Draw a compact world overview and the current camera rectangle."""
        minimap_bounds = manager._minimap_rect()
        rect = pygame.Rect(
            minimap_bounds.x,
            minimap_bounds.y,
            minimap_bounds.width,
            minimap_bounds.height,
        )
        pygame.draw.rect(screen, (23, 32, 25), rect)
        pygame.draw.rect(screen, WHITE, rect, 2)

        scale_x = rect.width / manager.map_width
        scale_y = rect.height / manager.map_height

        def mini_rect(world_rect: Rect) -> pygame.Rect:
            return pygame.Rect(
                rect.left + int(world_rect.left * scale_x),
                rect.top + int(world_rect.top * scale_y),
                max(1, int(world_rect.width * scale_x)),
                max(1, int(world_rect.height * scale_y)),
            )

        for region in manager.terrain.water:
            pygame.draw.rect(screen, (43, 92, 119), mini_rect(region.rect))
        for region in manager.terrain.high_ground:
            pygame.draw.rect(screen, (113, 132, 77), mini_rect(region.rect))
        for region in manager.terrain.ramps:
            pygame.draw.rect(screen, (158, 142, 96), mini_rect(region.rect))

        fog = self.presentation.view.fog_for(manager)
        if fog is not None:
            fog_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
            fog_surf.fill((0, 0, 0, 255))
            for row in range(fog.rows):
                for col in range(fog.cols):
                    state = fog.grid[row][col]
                    if state > 0:
                        cell_rect = pygame.Rect(
                            int(col * FOG_CELL_SIZE * scale_x),
                            int(row * FOG_CELL_SIZE * scale_y),
                            max(1, int(FOG_CELL_SIZE * scale_x)) + 1,
                            max(1, int(FOG_CELL_SIZE * scale_y)) + 1,
                        )
                        fog_surf.fill((0, 0, 0, 0 if state == FogOfWar.VISIBLE else 150), cell_rect)
            screen.blit(fog_surf, (rect.left, rect.top))

        for entity in manager.all_entities:
            if self.presentation.view.can_inspect(manager, entity):
                color = getattr(entity, "color", WHITE)
                if isinstance(entity, Resource):
                    color = (80, 210, 120) if isinstance(entity, Wood) else (90, 220, 240)
                mini_x = rect.left + int(entity.x * scale_x)
                mini_y = rect.top + int(entity.y * scale_y)
                pygame.draw.circle(screen, color, (mini_x, mini_y), 2)

        camera_rect = pygame.Rect(
            rect.left + int(manager.camera_x * scale_x),
            rect.top + int(manager.camera_y * scale_y),
            max(4, int(manager.screen_width * scale_x)),
            max(4, int(manager.play_area_height * scale_y)),
        )
        pygame.draw.rect(screen, WHITE, camera_rect, 1)

    def _draw_main_menu(self, screen: pygame.Surface, manager: GameSession) -> None:
        """Draw the F10 pause menu."""
        screen_width = manager.screen_width
        screen_height = manager.screen_height

        overlay = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        menu_width = 300
        button_height = 50
        spacing = 20
        options = self.presentation.view.menu_options(manager)
        total_height = len(options) * (button_height + spacing) - spacing
        start_x = (screen_width - menu_width) // 2
        start_y = (screen_height - total_height) // 2

        font = pygame.font.SysFont(None, 40)

        for i, option in enumerate(options):
            rect = pygame.Rect(start_x, start_y + i * (button_height + spacing), menu_width, button_height)

            color = (80, 80, 80) if rect.collidepoint(manager.mouse_pos) else (40, 40, 40)

            pygame.draw.rect(screen, color, rect)
            pygame.draw.rect(screen, WHITE, rect, 2)

            text_surf = font.render(option, True, WHITE)
            text_rect = text_surf.get_rect(center=rect.center)
            screen.blit(text_surf, text_rect)

        if manager.menu_status:
            status_font = pygame.font.SysFont(None, 26)
            status_surf = status_font.render(manager.menu_status, True, WHITE)
            status_rect = status_surf.get_rect(center=(screen_width // 2, start_y + total_height + 30))
            screen.blit(status_surf, status_rect)

    def _draw_match_result(self, screen: pygame.Surface, manager: GameSession) -> None:
        """Draw a terminal result overlay with restart and quit actions."""
        overlay = pygame.Surface((manager.screen_width, manager.screen_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 190))
        screen.blit(overlay, (0, 0))
        title_font = pygame.font.SysFont(None, 72)
        button_font = pygame.font.SysFont(None, 34)
        title = title_font.render(
            match_result_title(manager, spectator=self.presentation.view.is_spectator), True, WHITE
        )
        screen.blit(title, title.get_rect(center=(manager.screen_width // 2, manager.screen_height // 2 - 40)))
        detail = pygame.font.SysFont(None, 26).render(match_result_detail(manager), True, WHITE)
        screen.blit(detail, detail.get_rect(center=(manager.screen_width // 2, manager.screen_height // 2 + 5)))
        for label, rect in match_result_buttons(manager.screen_width, manager.screen_height):
            color = (80, 80, 80) if rect.collidepoint(manager.mouse_pos) else (40, 40, 40)
            pygame.draw.rect(screen, color, rect)
            pygame.draw.rect(screen, WHITE, rect, 2)
            text_surface = button_font.render(label, True, WHITE)
            screen.blit(text_surface, text_surface.get_rect(center=rect.center))
