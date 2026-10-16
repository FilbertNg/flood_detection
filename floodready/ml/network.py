"""River network between river stations: which stations lie upstream of which (built by scripts/build_river_network.py)."""
from __future__ import annotations

from pathlib import Path

import yaml

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "config" / "river_network.yaml"


def load_network(path: Path | str = DEFAULT_PATH) -> dict[str, list[str]]:
    """Downstream station id -> ids of the stations upstream of it."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return {str(down): [u for u in dict.fromkeys(str(link["id"]) for link in (links or [])) if u != str(down)]
            for down, links in raw.items()}
