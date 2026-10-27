"""Programmatic eval scoring for safe-things-mcp test fixtures."""
from __future__ import annotations

from .scorer import TaskState, load_key, score

__all__ = ["load_key", "score", "TaskState"]
