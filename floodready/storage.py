"""File storage: raw downloads kept gzipped and untouched; parsed rows in
daily parquet files that are appended to and de-duplicated."""
from __future__ import annotations

import gzip
from pathlib import Path

import pandas as pd


def save_raw(path: Path, text: str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")          # atomic: a crash never leaves a half-written file
    with gzip.open(tmp, "wt", encoding="utf-8") as handle:
        handle.write(text)
    tmp.replace(path)
    return path


def read_raw(path: Path) -> str:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return handle.read()


def append_parquet(df: pd.DataFrame, path: Path, keys: list[str], keep: str = "first") -> Path:
    """Append rows to a parquet file, de-duplicated on `keys`.

    keep="first" keeps what was stored earlier; keep="last" lets a newer copy replace it
    (live tables: JPS sometimes publishes a 0.00 placeholder and corrects it later)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        df = pd.concat([pd.read_parquet(path), df], ignore_index=True)
    df = df.drop_duplicates(subset=keys, keep=keep)
    tmp = path.with_suffix(".tmp")
    df.to_parquet(tmp, index=False)
    tmp.replace(path)
    return path
