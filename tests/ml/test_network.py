from pathlib import Path

import yaml

from floodready.ml import dataset, network

ROOT = Path(__file__).resolve().parents[2]


def test_load_network_returns_downstream_to_upstream_ids(tmp_path):
    p = tmp_path / "n.yaml"
    p.write_text(yaml.safe_dump({"B": [{"id": "A", "method": "flow", "path_km": 3.2}, {"id": "C", "method": "name", "path_km": 9.0}],
                                 "D": []}), encoding="utf-8")
    assert network.load_network(p) == {"B": ["A", "C"], "D": []}


def test_shipped_network_is_well_formed():
    net = network.load_network(ROOT / "config" / "river_network.yaml")
    assert net
    for down, ups in net.items():
        assert down not in ups and len(ups) == len(set(ups))
        for up in ups:
            assert down not in net.get(up, [])          # no two-way links


def test_default_network_is_the_shipped_file():
    assert dataset.default_network() == network.load_network(ROOT / "config" / "river_network.yaml")
