"""English selection-panel labels for active and queued unit orders."""

from __future__ import annotations

from typing import TYPE_CHECKING

from rts_nano.content import CONTENT

if TYPE_CHECKING:
    from rts_nano.game.order import Order
    from rts_nano.simulation.entities.base import Unit

_ORDER_NAMES = {
    "move": "Move",
    "attack_move": "Attack Move",
    "attack": "Attack",
    "gather": "Gather",
    "build": "Build",
    "return_cargo": "Return Cargo",
    "stop": "Stop",
    "hold": "Hold",
    "patrol": "Patrol",
}


def format_order(order: Order) -> str:
    """Return a compact player-facing label for one order."""
    label = _ORDER_NAMES[order.kind]
    if order.target_content_id is None:
        return label
    content_id = str(order.target_content_id)
    definition = CONTENT.resources.get(content_id) or CONTENT.buildings.get(content_id) or CONTENT.units.get(content_id)
    target_name = definition.display_name if definition is not None else content_id.replace("_", " ").title()
    return f"{label} {target_name}"


def unit_order_lines(unit: Unit) -> list[str]:
    """Return active/queued order lines that fit the selection details panel."""
    lines: list[str] = []
    if unit.current_order is not None and unit.state != "IDLE":
        lines.append(f"Order: {format_order(unit.current_order)}")
    if unit.order_queue:
        visible = [format_order(order) for order in unit.order_queue[:3]]
        if len(unit.order_queue) > len(visible):
            visible.append(f"+{len(unit.order_queue) - len(visible)}")
        lines.append(f"Queue: {' -> '.join(visible)}")
    return lines
