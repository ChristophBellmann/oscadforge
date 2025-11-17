"""
OSCADForge tooling entrypoint.

This package hosts the engine/CLI scaffolding described in setup-strategy.md.
"""

from .core.engine import build_model, EngineResult  # re-export for convenience

__all__ = ["build_model", "EngineResult"]
