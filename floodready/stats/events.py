"""The one reader of the labelled events file (`data/events/events.csv`, WP6) for statistics, reports and news outcomes.

Real format (PR #43): one row per observation; `street_ids` is a ';'-joined list (may be blank for area rows);
`event_date` is always filled, `start_time_local` is blank unless the time is known; `checked_by` is empty and
`status` is `draft` until a human has checked the row. Rules, all enforced here and nowhere else:

- only checked rows count: `checked_by` non-empty and `status` not `draft`. Unchecked drafts produce nothing;
- only `flooded == 1` rows;
- only this township: a row with streets keeps just those on the township's streets; a row without streets is kept
  when `sdp_township` equals the township name (an "(adjacent)" row is not the township). With no filter given
  (`street_ids` and `township_name` both None) every checked row is kept;
- the date is the `start_time_local` date, else `event_date` (day precision, `YYYY-MM-DD`); month or season rows
  have no day and are dropped. The onset time exists only when `start_time_local` is filled and precision is
  minute or hour; without it there is no lead time or rain figure.

`normalise` returns one row per (event, street): event_id, street_id (None for an area row), date, onset (Timestamp or
NaT, also exposed as `start_time_local` for `outcomes.news_outcomes`), date_precision, flooded, place_name,
source_type, source_url. Pass its result around; calling `normalise` on it again returns it unchanged.
"""
from __future__ import annotations

import re

import pandas as pd

PRECISE = ("minute", "hour")
COLUMNS = ["event_id", "street_id", "date", "onset", "start_time_local", "date_precision", "flooded", "place_name",
           "source_type", "source_url"]
_DAY = re.compile(r"\d{4}-\d{2}-\d{2}")


def _text(value) -> str:
    return "" if value is None or (isinstance(value, float) and pd.isna(value)) else str(value).strip()


def _empty() -> pd.DataFrame:
    out = pd.DataFrame(columns=COLUMNS)
    out.attrs["normalised"] = True
    return out


def normalise(events: pd.DataFrame | None, *, street_ids: set[str] | None = None,
              township_name: str | None = None) -> pd.DataFrame:
    """See the module docstring. Never raises on a missing column; a frame without `checked_by` yields nothing."""
    if events is None:
        return _empty()
    if events.attrs.get("normalised"):
        return events
    if events.empty or "checked_by" not in events.columns:
        return _empty()
    filtering = street_ids is not None or township_name is not None
    town = _text(township_name).casefold()
    rows = []
    for _, r in events.iterrows():
        if not _text(r.get("checked_by")) or _text(r.get("status")).casefold() == "draft":
            continue
        if _text(r.get("flooded")) not in ("1", "1.0", "True", "true"):
            continue
        streets = [s.strip() for s in _text(r.get("street_ids") if "street_ids" in events.columns else r.get("street_id")).split(";") if s.strip()]
        if filtering:
            if streets:
                streets = [s for s in streets if street_ids is not None and s in street_ids]
                if not streets:
                    continue
            elif not town or _text(r.get("sdp_township")).casefold() != town:
                continue
        start = pd.to_datetime(_text(r.get("start_time_local")) or None, errors="coerce")
        precision = _text(r.get("date_precision"))
        day = start.date() if pd.notna(start) else (pd.Timestamp(_text(r.get("event_date"))).date()
                                                    if _DAY.fullmatch(_text(r.get("event_date"))) else None)
        if day is None:
            continue
        onset = start if pd.notna(start) and (not precision or precision in PRECISE) else pd.NaT
        for street in streets or [None]:
            rows.append({"event_id": _text(r.get("event_id")), "street_id": street, "date": day, "onset": onset,
                         "start_time_local": onset, "date_precision": precision, "flooded": 1,
                         "place_name": _text(r.get("place_name")), "source_type": _text(r.get("source_type")) or "news",
                         "source_url": _text(r.get("source_url")) or None})
    out = pd.DataFrame(rows, columns=COLUMNS)
    # keep street_id an object column: pandas 3 would turn None into NaN in a mixed str/None column
    out["street_id"] = pd.Series([r["street_id"] for r in rows], dtype=object, index=out.index)
    out.attrs["normalised"] = True
    return out
