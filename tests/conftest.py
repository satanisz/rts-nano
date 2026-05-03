"""Shared pytest setup for pygame-based tests."""

from __future__ import annotations

import os

import pygame
import pytest


@pytest.fixture(autouse=True)
def pygame_headless() -> None:
    """Initialize pygame with SDL's dummy video driver for every test."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    yield
    pygame.quit()
