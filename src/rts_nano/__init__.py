"""RTS Nano public Python API with lazy imports for lightweight submodules."""

from __future__ import annotations

__all__ = [
    "Action",
    "ActionSpec",
    "AttackMoveAction",
    "AttackAction",
    "BuildingType",
    "BuildAction",
    "CancelConstructionAction",
    "CancelProductionAction",
    "ConstructAction",
    "DepositAction",
    "EntitySnapshot",
    "GatherAction",
    "HoldAction",
    "MoveAction",
    "NoOpAction",
    "Observation",
    "ProductionSnapshot",
    "ReturnCargoAction",
    "RtsNanoEnv",
    "SelectAction",
    "StepResult",
    "StopAction",
    "TeamSnapshot",
]


def __getattr__(name: str) -> object:
    """Load the environment API only when a public facade symbol is requested."""
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from rts_nano import env

    value = getattr(env, name)
    globals()[name] = value
    return value
