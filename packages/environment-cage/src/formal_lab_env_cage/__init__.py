"""CAGE Challenge 4 environment bridge (phase 3B, D5): run the official CybORG 4.0 scripted baseline in an isolated
venv through a typed subprocess, keeping CybORG's heavy dependencies out of the frozen platform environment."""

from __future__ import annotations

from . import bridge

__all__ = ["bridge"]
