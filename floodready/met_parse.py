"""Read the saved MET Malaysia warning payload (data.gov.my) into land rain warnings with the areas they name.

The payload is the list that `jobs.run_met_warnings` stores under `data/raw/met_warnings/json/`. A thunderstorm text reads
`... expected over the states of Perlis • Selangor (Petaling, Klang) • Melaka • Sarawak: Miri (Marudi) • ... until 9:00 PM; ...`.
A state with no bracket means the whole state. Times are naive MYT.
"""
from __future__ import annotations

import re
from datetime import datetime

_RAIN_TITLE = re.compile(r"thunderstorm|heavy rain|continuous rain", re.I)
_LEAD = re.compile(r"expected over the (?:states?|areas?) of\s+", re.I)
_UNTIL = re.compile(r"\s+until\s+\d", re.I)


def _dt(text: str | None) -> datetime | None:
    return datetime.fromisoformat(text) if text else None


def _areas(text: str) -> dict[str, set[str]]:
    m = _LEAD.search(text)
    if not m:
        return {}
    body = text[m.end():]
    cut = _UNTIL.search(body)
    if cut:
        body = body[:cut.start()]
    areas: dict[str, set[str]] = {}
    for item in body.split("•"):
        item = item.strip()
        if not item:
            continue
        if ":" in item.split("(")[0]:                      # "Sarawak: Miri (Marudi), Sibu": state-level only
            areas.setdefault(item.split(":", 1)[0].strip(), set())
            continue
        name, _, rest = item.partition("(")
        districts = {d.strip() for d in re.split(r",|\band\b", rest.rsplit(")", 1)[0]) if d.strip()}
        areas.setdefault(name.strip(), set()).update(districts)
    return areas


def parse_warnings(payload: list[dict]) -> list[dict]:
    """Land thunderstorm / heavy-rain warnings: title_en/ms, valid_from/to, areas {state: districts (empty = whole state)}."""
    out = []
    for item in payload or []:
        issue = item.get("warning_issue") or {}
        title = issue.get("title_en") or ""
        text = item.get("text_en") or ""
        if not _RAIN_TITLE.search(title) or not text:
            continue
        out.append({"title_en": title, "title_ms": issue.get("title_bm") or title,
                    "valid_from": _dt(item.get("valid_from")), "valid_to": _dt(item.get("valid_to")),
                    "areas": _areas(text)})
    return out


def names_area(warning: dict, state: str, district: str | None = None) -> bool:
    """True when the warning names the whole state, or lists `district` under it."""
    districts = {k.lower(): v for k, v in warning["areas"].items()}.get(state.lower())
    if districts is None:
        return False
    return not districts or (district is not None and district.lower() in {d.lower() for d in districts})


def overlaps(warning: dict, start: datetime, end: datetime) -> bool:
    """The warning's validity overlaps [start, end]."""
    vf, vt = warning.get("valid_from"), warning.get("valid_to")
    return (vt is None or vt > start) and (vf is None or vf <= end)


def load_latest(root) -> list[dict]:
    """Parsed warnings from the newest saved payload under `<root>/json/<day>/<hhmm>.json.gz` ([] when none or unreadable)."""
    import gzip
    import json
    from pathlib import Path
    files = sorted(Path(root).glob("json/*/*.json.gz"))
    if not files:
        return []
    try:
        return parse_warnings(json.loads(gzip.open(files[-1], "rt", encoding="utf-8").read()))
    except (OSError, ValueError):
        return []
