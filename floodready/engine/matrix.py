"""Risk matrix: susceptibility (1-5) x trigger level -> street level (build plan §2, task E4)."""
from __future__ import annotations

from .types import Level


def street_level(susceptibility: int, trigger: Level, table: dict) -> Level:
    """`table` is config/risk_matrix.yaml["matrix"]: {1: {"normal": "normal", ...}, ...}."""
    row = table[int(min(max(susceptibility, 1), 5))]
    return Level.parse(row[trigger.json])
