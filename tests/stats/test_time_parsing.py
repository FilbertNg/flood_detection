"""The statistics time helpers (outcomes._dt, statistics.naive) give the same naive MYT datetime as pandas for every
form the database, the API and events.csv use."""
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import pytest

from floodready.stats.outcomes import _dt
from floodready.stats.statistics import naive

MYT = timezone(timedelta(hours=8))
VALUES = [
    "2024-11-12T08:15:00+08:00",
    "2024-11-12T08:15:00.123456+08:00",
    "2024-11-12 08:15:00",
    "2024-11-12T08:15:00",
    "2024-11-12T00:15:00Z",
    "2024-11-12T00:15:00+00:00",
    "2024-11-12",
    "2024-11-12 08:15",
    datetime(2024, 11, 12, 8, 15),
    datetime(2024, 11, 12, 0, 15, tzinfo=timezone.utc),
    datetime(2024, 11, 12, 8, 15, tzinfo=MYT),
    pd.Timestamp("2024-11-12 08:15"),
    pd.Timestamp("2024-11-12 00:15", tz="UTC"),
    date(2024, 11, 12),
]


def reference(value):
    ts = pd.Timestamp(value)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("Asia/Kuala_Lumpur").tz_localize(None)
    return ts.to_pydatetime()


@pytest.mark.parametrize("fn", [_dt, naive])
@pytest.mark.parametrize("value", VALUES, ids=repr)
def test_matches_pandas(fn, value):
    got = fn(value)
    assert got == reference(value)
    assert type(got) is datetime and got.tzinfo is None


@pytest.mark.parametrize("fn", [_dt, naive])
@pytest.mark.parametrize("value", [None, float("nan")])
def test_missing_is_none(fn, value):
    assert fn(value) is None


def test_naive_nat_is_none():
    assert naive(pd.NaT) is None


@pytest.mark.parametrize("fn", [_dt, naive])
def test_unparseable_string_still_raises(fn):
    with pytest.raises(ValueError):
        fn("not a time")
