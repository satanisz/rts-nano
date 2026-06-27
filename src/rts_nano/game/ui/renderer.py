"""Presentation layer: draws the game world, HUD, minimap, and menus.

The renderer reads a ``GameManager`` (and its ``CommandPanel``) but never mutates
simulation state. Keeping it separate means the core can run headless without any
draw/font calls. World↔screen transforms still live on the manager because input
shares them; the renderer calls them read-only.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from rts_nano.game.assets.entities import TeamColor, Wood
from rts_nano.game.assets.entities.base_entities import Building, Resource, Unit, building_glyph
from rts_nano.game.constants import (
    BLUE,
    BOTTOM_MENU_HEIGHT,
    FOG_CELL_SIZE,
    GREEN,
    MINIMAP_PADDING,
    MINIMAP_WIDTH,
    RED,
    WHITE,
)
from rts_nano.game.fog import FogOfWar

if TYPE_CHECKING:
    from rts_nano.game.manager import GameManager

WOOD_ICON = "\U0001fab5"
GOLD_ICON = "\U0001fa99"


class GameRenderer:
    """Draws the current state of a ``GameManager`` to a display surface."""

    def draw(self, screen: pygame.Surface, manager: GameManager) -> None:
        """Draw world entities, selection state, HUD, minimap, and overlays."""
        screen_width = manager.screen_width
        play_area_height = manager.play_area_height
        screen_height = manager.screen_height

        world_surface = screen.subsurface(pygame.Rect(0, 0, screen_width, play_area_height))
        camera_offset = (manager.camera_x, manager.camera_y)

        manager.terrain.draw(world_surface, camera_offset)

        for entity in manager.all_entities:
            cx, cy = entity.get_center()
            is_visible = manager.fog.is_visible(cx, cy)
            is_explored = manager.fog.is_explored(cx, cy)

            is_allied = getattr(entity, "team", None) == manager.current_team
            is_resource = isinstance(entity, Resource)

            if is_allied:
                entity.draw(world_surface, camera_offset)
            elif is_resource:
                if is_explored or is_visible:
                    entity.draw(world_surface, camera_offset)
            else:
                if is_visible:
                    entity.draw(world_surface, camera_offset)

        for missile in manager.magic_missiles:
            if manager.fog.is_visible(missile.x, missile.y):
                missile.draw(world_surface, camera_offset)
        for shot in manager.archer_shots:
            if manager.fog.is_visible(shot.x, shot.y):
                shot.draw(world_surface, camera_offset)
        for marker in manager.click_markers:
            marker.draw(world_surface, camera_offset)

        self._draw_pending_construction(world_surface, camera_offset, manager)

        fog_surf = pygame.Surface((screen_width, play_area_height), pygame.SRCALPHA)
        fog_surf.fill((0, 0, 0, 255))

        start_col = max(0, int(manager.camera_x // FOG_CELL_SIZE))
        end_col = min(manager.fog.cols - 1, int((manager.camera_x + screen_width) // FOG_CELL_SIZE))
        start_row = max(0, int(manager.camera_y // FOG_CELL_SIZE))
        end_row = min(manager.fog.rows - 1, int((manager.camera_y + play_area_height) // FOG_CELL_SIZE))

        for row in range(start_row, end_row + 1):
            for col in range(start_col, end_col + 1):
                state = manager.fog.grid[row][col]
                if state > 0:
                    rect_x = int(col * FOG_CELL_SIZE - manager.camera_x)
                    rect_y = int(row * FOG_CELL_SIZE - manager.camera_y)
                    # Expand by 1 pixel to prevent visual seams between grid cells
                    rect = pygame.Rect(rect_x, rect_y, FOG_CELL_SIZE + 1, FOG_CELL_SIZE + 1)
                    if state == FogOfWar.VISIBLE:
                        fog_surf.fill((0, 0, 0, 0), rect)
                    else:
                        fog_surf.fill((0, 0, 0, 150), rect)

        world_surface.blit(fog_surf, (0, 0))

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

        font = pygame.font.SysFont(None, 36)
        emoji_font = pygame.font.SysFont(["Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji", "Noto Emoji"], 20)
        team_group = manager.entities.get(manager.current_team)
        ui_color = BLUE if manager.current_team == TeamColor.BLUE else RED

        if team_group:
            res = team_group.resources
            num_buildings = (
                len(team_group.bases)
                + len(team_group.barracks)
                + len(team_group.houses)
                + len(team_group.mage_towers)
                + len(team_group.towers)
            )
            num_units = (
                len(team_group.peasents) + len(team_group.knights) + len(team_group.archers) + len(team_group.mages)
            )
            population_cap = manager.population_cap_for_team(manager.current_team)
        else:
            res = {"wood": 0, "gold": 0}
            num_buildings = 0
            num_units = 0
            population_cap = 0

        at_population_cap = population_cap > 0 and num_units >= population_cap
        population_color = (255, 90, 90) if at_population_cap else ui_color
        hud_parts: list[pygame.Surface] = [
            font.render(f"Team {manager.current_team.value} | ", True, ui_color),
            emoji_font.render(WOOD_ICON, True, ui_color),
            font.render(f": {res['wood']}   ", True, ui_color),
            emoji_font.render(GOLD_ICON, True, ui_color),
            font.render(f": {res['gold']} | Buildings: {num_buildings}   ", True, ui_color),
            font.render(f"Units: {num_units}/{population_cap}", True, population_color),
        ]

        if manager.paused and not manager.menu_active:
            pause_label = manager.game_over_message or "- PAUSED -"
            pause_text = font.render(pause_label, True, WHITE)
            text_rect = pause_text.get_rect(center=(screen_width // 2, screen_height // 2))
            screen.blit(pause_text, text_rect)

        hud_x = 10
        hud_y = 10
        for part_surface in hud_parts:
            screen.blit(part_surface, (hud_x, hud_y))
            hud_x += part_surface.get_width()
        self._draw_bottom_menu(screen, manager)
        self._draw_minimap(screen, manager)

        if manager.menu_active:
            self._draw_main_menu(screen, manager)

    def _draw_pending_construction(
        self,
        screen: pygame.Surface,
        offset: tuple[float, float],
        manager: GameManager,
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
        preview_rect = pygame.Rect(0, 0, Building.SIZE, Building.SIZE)
        preview_rect.center = screen_pos

        preview_surface = pygame.Surface((Building.SIZE, Building.SIZE), pygame.SRCALPHA)
        preview_surface.fill((*color, 55))
        screen.blit(preview_surface, preview_rect)
        pygame.draw.rect(screen, color, preview_rect, width=2)
        pygame.draw.circle(screen, color, screen_pos, int(Building.RADIUS), width=1)

    def _draw_bottom_menu(self, screen: pygame.Surface, manager: GameManager) -> None:
        """Draw the selection details, portrait, and command-panel buttons."""
        screen_width = manager.screen_width
        screen_height = manager.screen_height

        menu_rect = pygame.Rect(0, screen_height - BOTTOM_MENU_HEIGHT, screen_width, BOTTOM_MENU_HEIGHT)
        pygame.draw.rect(screen, (40, 40, 40), menu_rect)
        pygame.draw.rect(screen, (200, 200, 200), menu_rect, 2)

        if not manager.selected_entities:
            return

        primary_entity = manager.selected_entities[0]

        minimap_end_x = MINIMAP_WIDTH + MINIMAP_PADDING * 2
        command_card_width = 180
        portrait_size = 120
        portrait_box_width = portrait_size + 20

        command_card_x = screen_width - command_card_width
        portrait_x = command_card_x - portrait_box_width
        center_panel_x = minimap_end_x
        center_panel_width = portrait_x - minimap_end_x

        font_small = pygame.font.SysFont(None, 24)

        if len(manager.selected_entities) > 1:
            icon_size = 40
            padding = 8
            max_cols = max(1, center_panel_width // (icon_size + padding))

            start_x = center_panel_x + padding
            start_y = screen_height - BOTTOM_MENU_HEIGHT + padding

            for i, entity in enumerate(manager.selected_entities):
                col = i % max_cols
                row = i // max_cols

                pos_x = start_x + col * (icon_size + padding)
                pos_y = start_y + row * (icon_size + padding)

                if pos_y + icon_size > screen_height:
                    break

                icon_rect = pygame.Rect(pos_x, pos_y, icon_size, icon_size)

                if entity.image:
                    small_img = pygame.transform.scale(entity.image, (icon_size, icon_size))
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
            elif isinstance(primary_entity, Building):
                stats_texts.append(f"HP: {primary_entity.life}/{primary_entity.max_life}")
                if primary_entity.is_under_construction:
                    stats_texts.append(f"Build: {primary_entity.construction_progress:.0%}")
                stats_texts.append(f"SHIELD: {primary_entity.shield_modifier}")
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

        if hasattr(primary_entity, "avatar_image") and primary_entity.avatar_image:
            pygame.draw.rect(screen, (80, 80, 80), frame_rect)
            pygame.draw.rect(screen, WHITE, frame_rect, 2)
            screen.blit(primary_entity.avatar_image, (portrait_x, avatar_y))
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

        font_tiny = pygame.font.SysFont(None, 16)
        buttons = manager.command_panel.build(manager, screen_width, screen_height)
        for index, slot_rect in enumerate(manager.command_panel.slot_rects(screen_width, screen_height)):
            if index >= len(buttons):
                pygame.draw.rect(screen, (30, 30, 30), slot_rect)
                pygame.draw.rect(screen, (50, 50, 50), slot_rect, 1)
                continue

            button = buttons[index]
            is_hovered = slot_rect.collidepoint(manager.mouse_pos)
            bg_color = (100, 100, 60) if (is_hovered and button.enabled) else (60, 60, 60)
            pygame.draw.rect(screen, bg_color, slot_rect)
            pygame.draw.rect(screen, WHITE, slot_rect, 1)

            for word_index, word in enumerate(button.label.split()):
                text_surf = font_tiny.render(word, True, WHITE)
                text_rect = text_surf.get_rect(
                    center=(slot_rect.x + slot_rect.width // 2, slot_rect.y + 16 + word_index * 14)
                )
                screen.blit(text_surf, text_rect)

    def _draw_minimap(self, screen: pygame.Surface, manager: GameManager) -> None:
        """Draw a compact world overview and the current camera rectangle."""
        rect = manager._minimap_rect()
        pygame.draw.rect(screen, (23, 32, 25), rect)
        pygame.draw.rect(screen, WHITE, rect, 2)

        scale_x = rect.width / manager.map_width
        scale_y = rect.height / manager.map_height

        def mini_rect(world_rect: pygame.Rect) -> pygame.Rect:
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

        fog_surf = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
        fog_surf.fill((0, 0, 0, 255))

        for row in range(manager.fog.rows):
            for col in range(manager.fog.cols):
                state = manager.fog.grid[row][col]
                if state > 0:
                    cell_rect = pygame.Rect(
                        int(col * FOG_CELL_SIZE * scale_x),
                        int(row * FOG_CELL_SIZE * scale_y),
                        max(1, int(FOG_CELL_SIZE * scale_x)) + 1,
                        max(1, int(FOG_CELL_SIZE * scale_y)) + 1,
                    )
                    if state == FogOfWar.VISIBLE:
                        fog_surf.fill((0, 0, 0, 0), cell_rect)
                    else:
                        fog_surf.fill((0, 0, 0, 150), cell_rect)
        screen.blit(fog_surf, (rect.left, rect.top))

        for entity in manager.all_entities:
            cx, cy = entity.get_center()
            is_visible = manager.fog.is_visible(cx, cy)
            is_explored = manager.fog.is_explored(cx, cy)
            is_allied = getattr(entity, "team", None) == manager.current_team
            is_resource = isinstance(entity, Resource)

            should_draw = False
            if is_allied:
                should_draw = True
            elif is_resource:
                should_draw = is_explored or is_visible
            else:
                should_draw = is_visible

            if should_draw:
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

    def _draw_main_menu(self, screen: pygame.Surface, manager: GameManager) -> None:
        """Draw the F10 pause menu."""
        screen_width = manager.screen_width
        screen_height = manager.screen_height

        overlay = pygame.Surface((screen_width, screen_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        screen.blit(overlay, (0, 0))

        menu_width = 300
        button_height = 50
        spacing = 20
        total_height = len(manager.menu_options) * (button_height + spacing) - spacing
        start_x = (screen_width - menu_width) // 2
        start_y = (screen_height - total_height) // 2

        font = pygame.font.SysFont(None, 40)

        for i, option in enumerate(manager.menu_options):
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
