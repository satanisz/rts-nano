"""Cached Pygame assets resolved from pure entity presentation keys."""

from __future__ import annotations

import logging
from pathlib import Path

import pygame

from rts_nano.simulation.entities.base import Building, Entity, Resource, Unit

ASSET_ROOT = Path(__file__).resolve().parents[2] / "assets"
SPRITES_DIR = ASSET_ROOT / "sprites"
PORTRAITS_DIR = ASSET_ROOT / "portraits"

_BUILDING_GLYPHS: dict[str, tuple[str, tuple[int, int, int]]] = {
    "house": ("H", (95, 140, 90)),
    "arsenal": ("A", (80, 120, 190)),
    "spire": ("S", (120, 110, 200)),
    "bastion": ("D", (90, 130, 170)),
    "pit": ("P", (150, 80, 70)),
    "chem_vat": ("C", (110, 160, 70)),
    "spiker": ("X", (150, 90, 70)),
}


def building_glyph(content_id: str) -> tuple[str, tuple[int, int, int]]:
    """Return the presentation-only placeholder label and accent color."""
    return _BUILDING_GLYPHS.get(content_id, ("?", (110, 110, 120)))


class PygameAssets:
    """Load each source image and fitted presentation variant at most once."""

    def __init__(self) -> None:
        """Initialize empty source and transformed-surface caches."""
        self._raw: dict[Path, pygame.Surface | None] = {}
        self._fitted: dict[tuple[Path, int], pygame.Surface | None] = {}
        self._flipped: dict[tuple[Path, int], pygame.Surface | None] = {}

    def sprite(self, entity: Entity, *, flipped: bool = False) -> pygame.Surface | None:
        """Return a cached world sprite without storing it on the entity."""
        sprite_path, _ = self.paths_for(entity)
        if sprite_path is None:
            return None
        if flipped:
            key = (sprite_path, int(entity.size))
            if key not in self._flipped:
                original = self._load_fitted(sprite_path, int(entity.size))
                self._flipped[key] = pygame.transform.flip(original, True, False) if original else None
            return self._flipped[key]
        return self._load_fitted(sprite_path, int(entity.size))

    def portrait(self, entity: Entity, size: int = 120) -> pygame.Surface | None:
        """Return a cached portrait, falling back to the world sprite."""
        sprite_path, portrait_path = self.paths_for(entity)
        if portrait_path is not None:
            portrait = self._load_fitted(portrait_path, size)
            if portrait is not None:
                return portrait
        return self._load_fitted(sprite_path, size) if sprite_path is not None else None

    @staticmethod
    def paths_for(entity: Entity) -> tuple[Path | None, Path | None]:
        """Resolve sprite and portrait paths from category, team, and visual key."""
        visual_key = entity.visual_key
        if isinstance(entity, Unit):
            team = entity.team.value.lower()
            return SPRITES_DIR / f"{team}_{visual_key}.png", PORTRAITS_DIR / f"{visual_key}.png"
        if isinstance(entity, Resource):
            return SPRITES_DIR / f"{visual_key}.png", PORTRAITS_DIR / f"{visual_key}.png"
        if isinstance(entity, Building):
            if visual_key == "base":
                team = entity.team.value.lower()
                return SPRITES_DIR / f"{team}_base.png", PORTRAITS_DIR / "base.png"
            path = SPRITES_DIR / f"{visual_key}.png"
            return path, path
        return None, None

    def _load_fitted(self, path: Path, size: int) -> pygame.Surface | None:
        resolved_path = path.resolve()
        key = (resolved_path, size)
        if key in self._fitted:
            return self._fitted[key]

        raw = self._load_raw(resolved_path)
        fitted = self._fit_to_square(raw, size) if raw is not None else None
        self._fitted[key] = fitted
        return fitted

    def _load_raw(self, path: Path) -> pygame.Surface | None:
        if path in self._raw:
            return self._raw[path]
        try:
            image = pygame.image.load(path)
        except Exception as exc:
            logging.warning("Could not load presentation asset %s: %s", path, exc)
            image = None
        self._raw[path] = image
        return image

    @staticmethod
    def _fit_to_square(surface: pygame.Surface, size: int) -> pygame.Surface:
        source_width, source_height = surface.get_size()
        canvas = pygame.Surface((size, size), pygame.SRCALPHA)
        if source_width <= 0 or source_height <= 0:
            return canvas

        scale = min(size / source_width, size / source_height)
        scaled_size = (
            max(1, round(source_width * scale)),
            max(1, round(source_height * scale)),
        )
        scaled = pygame.transform.smoothscale(surface, scaled_size)
        canvas.blit(scaled, scaled.get_rect(center=(size // 2, size // 2)))
        return canvas
