"""File storage: raw downloads kept gzipped and untouched; parsed rows in
daily parquet files that are appended to and de-duplicated."""
from __future__ import annotations

import gzip
from pathlib import Path

import pandas as pd


def save_raw(path: Path, text: str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf-8") as handle:
        handle.write(text)
    return path


def read_raw(path: Path) -> str:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return handle.read()


def append_parquet(df: pd.DataFrame, path: Path, keys: list[str]) -> Path:
    """Append rows to a parquet file, keeping the first copy of each key."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        df = pd.concat([pd.read_parquet(path), df], ignore_index=True)
    df = df.drop_duplicates(subset=keys, keep="first")
    tmp = path.with_suffix(".tmp")
    df.to_parquet(tmp, index=False)
    tmp.replace(path)
    return path
