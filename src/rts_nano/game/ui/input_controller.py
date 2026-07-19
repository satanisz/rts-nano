"""Input layer: translates pygame events into GameSession interactions.

The controller owns event/key/click dispatch and camera scrolling. It holds no
game state — it reads and mutates the manager through the manager's interaction
API (selection, placement/targeting modes, orders, camera helpers). Keeping this
out of ``GameSession`` means the core has no pygame event handling.

Only the double-click timing lives here, as it is input-internal and read
nowhere else.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from rts_nano.content import CONTENT
from rts_nano.game.rules import distance_between_points
from rts_nano.game.ui.effects import ClickMarker
from rts_nano.game.ui.selection_panel import build_selection_panel_layout
from rts_nano.game.ui.state import PresentationState
from rts_nano.simulation.entities import Base, TeamColor
from rts_nano.simulation.entities.base import Unit

if TYPE_CHECKING:
    from rts_nano.application import GameSession
    from rts_nano.game.ui.command_panel import CommandButton

FULLSCREEN_TOGGLE_EVENT = pygame.USEREVENT + 1
CAMERA_SPEED = 12
EDGE_SCROLL_MARGIN = 24
DOUBLE_CLICK_MS = 350


class InputController:
    """Translate pygame events and held keys into manager interactions."""

    def __init__(self, presentation: PresentationState | None = None) -> None:
        """Initialize transient input state (double-click tracking)."""
        self.presentation = presentation or PresentationState()
        self._last_click_ms = 0
        self._last_click_pos: tuple[int, int] = (0, 0)

    def update_camera(self, manager: GameSession) -> None:
        """Scroll the viewport with keyboard keys or screen-edge mouse position."""
        if manager.menu_active:
            return

        keys = pygame.key.get_pressed()
        dx = 0
        dy = 0
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            dx -= CAMERA_SPEED
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            dx += CAMERA_SPEED
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            dy -= CAMERA_SPEED
        if keys[pygame.K_DOWN] or keys[pygame.K_s]:
            dy += CAMERA_SPEED

        mouse_x, mouse_y = manager.mouse_pos
        if 0 <= mouse_y < manager.screen_height:
            if mouse_x <= EDGE_SCROLL_MARGIN:
                dx -= CAMERA_SPEED
            elif mouse_x >= manager.screen_width - EDGE_SCROLL_MARGIN:
                dx += CAMERA_SPEED
            if mouse_y <= EDGE_SCROLL_MARGIN:
                dy -= CAMERA_SPEED
            elif mouse_y >= manager.screen_height - EDGE_SCROLL_MARGIN:
                dy += CAMERA_SPEED

        manager.camera_x += dx
        manager.camera_y += dy
        manager._clamp_camera()

    def handle_event(self, manager: GameSession, event: pygame.event.Event) -> None:
        """Process one pygame event for team control, selection, and orders."""
        if event.type == pygame.KEYDOWN:
            self._handle_keydown(manager, event)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            self._handle_mouse_down(manager, event)
        elif event.type == pygame.MOUSEBUTTONUP:
            self._handle_mouse_up(manager, event)
        elif event.type == pygame.MOUSEMOTION:
            self._handle_mouse_motion(manager, event)

    def _handle_keydown(self, manager: GameSession, event: pygame.event.Event) -> None:
        if event.key == pygame.K_TAB:
            manager.cancel_pending_construction_placement()
            manager.cancel_pending_unit_command()
            manager.current_team = TeamColor.RED if manager.current_team == TeamColor.BLUE else TeamColor.BLUE
            manager.selected_entities.clear()
        elif event.key == pygame.K_q:
            pygame.event.post(pygame.event.Event(pygame.QUIT))
        elif event.key == pygame.K_p:
            if not manager.menu_active:
                manager.paused = not manager.paused
        elif event.key == pygame.K_F10:
            manager.menu_active = not manager.menu_active
            manager.paused = manager.menu_active
        elif event.key == pygame.K_F11 or (event.key == pygame.K_RETURN and event.mod & pygame.KMOD_ALT):
            self._request_fullscreen_toggle(manager)
        elif event.key == pygame.K_b:
            if manager._selected_construction_builder() is not None:
                manager.begin_construction_placement(self._faction_building(manager, "military"))
            else:
                self._try_build_peasant_from_selection(manager)
        elif event.key == pygame.K_y:
            manager.begin_construction_placement("house")
        elif event.key == pygame.K_m:
            manager.begin_construction_placement(self._faction_building(manager, "tech"))
        elif event.key == pygame.K_s:
            selected_units = [entity for entity in manager.selected_entities if isinstance(entity, Unit)]
            manager.issue_stop_order(manager.current_team, selected_units)
        elif event.key == pygame.K_h:
            selected_units = [entity for entity in manager.selected_entities if isinstance(entity, Unit)]
            manager.issue_hold_order(manager.current_team, selected_units)
        elif event.key == pygame.K_c:
            selected_units = [entity for entity in manager.selected_entities if isinstance(entity, Unit)]
            manager.issue_return_cargo_order(manager.current_team, selected_units)
        elif event.key == pygame.K_a:
            manager.begin_attack_move_targeting()
        elif event.key == pygame.K_t:
            manager.begin_patrol_targeting()
        elif event.key == pygame.K_g:
            manager.begin_gather_targeting()
        elif pygame.K_1 <= event.key <= pygame.K_9:
            group_id = event.key - pygame.K_0
            if event.mod & pygame.KMOD_CTRL:
                manager.assign_control_group(group_id)
            else:
                manager.recall_control_group(group_id)

    def _handle_mouse_down(self, manager: GameSession, event: pygame.event.Event) -> None:
        mouse_pos = event.pos
        manager.set_mouse_pos(mouse_pos)

        if manager.menu_active:
            if event.button == 1:
                self._handle_menu_click(manager, mouse_pos)
            return  # Block world interaction while menu is open

        if event.button == 1:
            self._handle_left_click(manager, mouse_pos)
        elif event.button == 3:
            self._handle_right_click(manager, mouse_pos)

    def _handle_left_click(self, manager: GameSession, mouse_pos: tuple[int, int]) -> None:
        minimap_rect = manager._minimap_rect()
        if minimap_rect.collidepoint(mouse_pos):
            manager.minimap_dragging = True
            manager._center_camera_from_minimap_pos(mouse_pos)
            return

        if self._handle_selection_panel_click(manager, mouse_pos):
            return
        if self._handle_command_panel_click(manager, mouse_pos):
            return
        if mouse_pos[1] >= manager.play_area_height:
            return

        world_pos = manager._screen_to_world(mouse_pos)
        if manager.pending_construction_type is not None:
            manager.place_pending_construction(world_pos)
            return
        if manager.pending_unit_command == "attack_move":
            selected_units = [entity for entity in manager.selected_entities if isinstance(entity, Unit)]
            manager.issue_attack_move_order(manager.current_team, world_pos, selected_units)
            manager.cancel_pending_unit_command()
            return
        if manager.pending_unit_command == "patrol":
            selected_units = [entity for entity in manager.selected_entities if isinstance(entity, Unit)]
            manager.issue_patrol_order(manager.current_team, world_pos, selected_units)
            manager.cancel_pending_unit_command()
            return
        if manager.pending_unit_command == "gather":
            resource = manager._resource_at_position(world_pos)
            if resource is None:
                manager.menu_status = "Choose resource"
                return
            selected_units = [entity for entity in manager.selected_entities if isinstance(entity, Unit)]
            manager.issue_gather_order(manager.current_team, resource, selected_units)
            manager.cancel_pending_unit_command()
            return

        clicked_unit = manager._unit_at_world_pos(world_pos)
        now_ms = pygame.time.get_ticks()
        is_double_click = (
            clicked_unit is not None
            and clicked_unit.team == manager.current_team
            and now_ms - self._last_click_ms <= DOUBLE_CLICK_MS
            and distance_between_points(self._last_click_pos, mouse_pos) <= 6
        )
        self._last_click_ms = now_ms
        self._last_click_pos = mouse_pos
        if is_double_click and clicked_unit is not None:
            manager.select_units_like(clicked_unit)
            return

        manager.dragging = True
        manager.drag_start = world_pos
        manager.drag_end = world_pos

    def _handle_right_click(self, manager: GameSession, mouse_pos: tuple[int, int]) -> None:
        if manager.pending_construction_type is not None:
            manager.cancel_pending_construction_placement()
            return
        if manager.pending_unit_command is not None:
            manager.cancel_pending_unit_command()
            return
        if mouse_pos[1] >= manager.play_area_height:
            return
        order_pos = manager._screen_to_world(mouse_pos)
        if manager.terrain.blocks_movement(order_pos):
            return
        target_entity = None
        for entity in manager.all_entities:
            if entity.contains_point(order_pos):
                target_entity = entity
                break

        marker_color = (255, 80, 80) if target_entity else (80, 255, 120)
        self.presentation.click_markers.append(
            ClickMarker(order_pos[0], order_pos[1], marker_color, pygame.time.get_ticks())
        )

        selected_units = [entity for entity in manager.selected_entities if isinstance(entity, Unit)]
        if target_entity is None:
            manager._assign_group_move_order(selected_units, order_pos)
        else:
            for entity in selected_units:
                manager._assign_unit_target(entity, order_pos, target_entity)

    def _handle_mouse_up(self, manager: GameSession, event: pygame.event.Event) -> None:
        if event.button == 1 and manager.minimap_dragging:
            manager.minimap_dragging = False
        elif event.button == 1 and manager.dragging:
            manager.dragging = False
            manager.select_units_in_box()
            manager.drag_start = None
            manager.drag_end = None

    def _handle_mouse_motion(self, manager: GameSession, event: pygame.event.Event) -> None:
        manager.set_mouse_pos(event.pos)
        if manager.minimap_dragging:
            manager._center_camera_from_minimap_pos(event.pos)
        elif manager.dragging:
            manager.drag_end = manager._screen_to_world(event.pos)

    def _handle_command_panel_click(self, manager: GameSession, mouse_pos: tuple[int, int]) -> bool:
        """Dispatch a click on a command-panel button. Return True if handled."""
        for button in self.presentation.command_panel.build(manager, manager.screen_width, manager.screen_height):
            if not button.enabled or button.action is None or not button.rect.collidepoint(mouse_pos):
                continue
            self._dispatch_command_button(manager, button)
            return True
        return False

    @staticmethod
    def _handle_selection_panel_click(manager: GameSession, mouse_pos: tuple[int, int]) -> bool:
        """Select the entity represented by a multi-selection icon."""
        layout = build_selection_panel_layout(
            len(manager.selected_entities),
            manager.screen_width,
            manager.screen_height,
        )
        for entity, rect in zip(manager.selected_entities, layout.icon_rects, strict=False):
            if rect.collidepoint(mouse_pos):
                manager.selected_entities = [entity]
                return True
        return False

    def _dispatch_command_button(self, manager: GameSession, button: CommandButton) -> None:
        """Run the manager action behind an enabled command-panel button."""
        action = button.action
        if action == "produce" and button.producer is not None and button.unit_type:
            manager.produce_unit(button.producer, button.unit_type)
        elif action == "cancel" and button.producer is not None:
            manager.cancel_production(button.producer)
        elif action == "construct" and button.building_type:
            manager.begin_construction_placement(button.building_type)
        elif action == "cancel_construction" and button.producer is not None:
            manager.cancel_construction(button.producer)
        elif action in {"stop", "hold", "attack_move", "patrol", "gather", "return_cargo"}:
            manager._handle_unit_command_button(action)

    def _faction_building(self, manager: GameSession, role: str) -> str:
        """Return the building type the current team builds for a hotkey role."""
        faction = manager.state.faction_for_team(manager.current_team)
        definition_role = {"military": "military_production", "tech": "advanced_production"}[role]
        return next(
            key
            for key, definition in CONTENT.buildings_for_faction(faction).items()
            if definition.role == definition_role
        )

    def _try_build_peasant_from_selection(self, manager: GameSession) -> None:
        """Attempt to build a peasant from the first selected base."""
        for entity in manager.selected_entities:
            if isinstance(entity, Base) and entity.team == manager.current_team:
                manager.build_peasant(entity)
                break

    def _handle_menu_click(self, manager: GameSession, mouse_pos: tuple[int, int]) -> None:
        """Process clicks on the F10 main menu."""
        menu_width = 300
        button_height = 50
        spacing = 20
        total_height = len(manager.menu_options) * (button_height + spacing) - spacing
        start_x = (manager.screen_width - menu_width) // 2
        start_y = (manager.screen_height - total_height) // 2

        for i, option in enumerate(manager.menu_options):
            rect = pygame.Rect(start_x, start_y + i * (button_height + spacing), menu_width, button_height)
            if not rect.collidepoint(mouse_pos):
                continue
            if option == "CONTINUE":
                manager.menu_active = False
                manager.paused = False
            elif option == "SAVE":
                manager.menu_status = "Save is not implemented yet."
            elif option == "LOAD":
                manager.menu_status = "Load is not implemented yet."
            elif option.startswith("SPEED:"):
                manager.menu_status = None
                if manager.fps_multiplier == 1.0:
                    manager.fps_multiplier = 2.0
                    manager._set_menu_option("SPEED:", "SPEED: FAST")
                elif manager.fps_multiplier == 2.0:
                    manager.fps_multiplier = 0.5
                    manager._set_menu_option("SPEED:", "SPEED: SLOW")
                else:
                    manager.fps_multiplier = 1.0
                    manager._set_menu_option("SPEED:", "SPEED: NORMAL")
            elif option.startswith("FULLSCREEN:"):
                self._request_fullscreen_toggle(manager)
            elif option == "EXIT":
                pygame.event.post(pygame.event.Event(pygame.QUIT))

    def _request_fullscreen_toggle(self, manager: GameSession) -> None:
        """Ask the application shell to toggle fullscreen mode."""
        manager.set_fullscreen_enabled(not manager.fullscreen_enabled)
        pygame.event.post(pygame.event.Event(FULLSCREEN_TOGGLE_EVENT, enabled=manager.fullscreen_enabled))
