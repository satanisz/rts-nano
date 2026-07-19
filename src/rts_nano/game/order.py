"""Descriptive order model for units.

This is an additive descriptive layer over the existing low-level unit state
machine (``state``, ``target_entity``, ``path``, ``attack_move_destination``,
``source_resource``). It records the high-level intent that produced the current
behavior so UI, observations, and AI agents can read a unit's order directly
instead of inferring it from scattered flags.

The low-level fields remain the execution mechanism; ``Order`` does not replace
them. Keeping this module free of entity imports avoids a circular dependency
with simulation entities and order systems.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

type OrderKind = Literal[
    "move",
    "attack_move",
    "attack",
    "gather",
    "return_cargo",
    "stop",
    "hold",
    "patrol",
]


@dataclass(frozen=True, slots=True)
class Order:
    """High-level intent currently driving a unit.

    Args:
        kind: The order family that produced the unit's current behavior.
        destination: Optional world-space goal associated with the order.
    """

    kind: OrderKind
    destination: tuple[float, float] | None = None
