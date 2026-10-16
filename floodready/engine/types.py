"""Engine records shared by the engine, API, replay and backfill (build plan §4.4).

Contract: changing anything here needs a PR labelled `contract` (build plan §9).
Times are naive MYT (UTC+8) inside the engine.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import IntEnum


class Level(IntEnum):
    NORMAL = 0
    WATCH = 1
    WARNING = 2
    DANGER = 3

    @property
    def json(self) -> str:
        """Lowercase name used in JSON, config and the frontends."""
        return self.name.lower()

    @classmethod
    def parse(cls, name: str) -> "Level":
        try:
            return cls[name.upper()]
        except KeyError:
            raise ValueError(f"unknown level {name!r}; expected one of {[lv.json for lv in cls]}") from None


@dataclass(frozen=True)
class Reason:
    code: str            # e.g. rain_1h, rain_2to4h, river_level, ml_probability, tide_high, stale_data, radar_approaching
    value: float
    unit: str            # mm, m, p, h, min
    station: str | None
    text_en: str
    text_ms: str


@dataclass(frozen=True)
class TriggerResult:
    level: Level
    confidence: str                  # high | medium | low
    fired_by: tuple[str, ...]        # rule_rain | rule_river | model | outlook
    reasons: tuple[Reason, ...]
    data_time: datetime
    stale_stations: tuple[str, ...]


@dataclass(frozen=True)
class MLResult:
    p: float                         # probability the river crosses warning within horizon_h
    level: Level
    station: str
    horizon_h: int
    reasons: tuple[Reason, ...]


@dataclass(frozen=True)
class StreetState:
    street_id: str
    level: Level
    trigger_level: Level
    confidence: str
    flood_probability: float | None
    fired_by: tuple[str, ...]
    window_start: datetime | None
    window_end: datetime | None
    reasons: tuple[Reason, ...]
    data_time: datetime


@dataclass(frozen=True)
class Alert:
    street_id: str
    level: Level
    kind: str                        # alert | all_clear
    issued_at: datetime
    window_start: datetime | None
    window_end: datetime | None
    reasons: tuple[Reason, ...]
    fired_by: tuple[str, ...]
