import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("fetch_fabdem", Path(__file__).parents[2] / "scripts" / "fetch_fabdem.py")
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)


def test_zip_name_for_klang_tile():
    assert fetch.zip_name("N03E101") == "N00E100-N10E110_FABDEM_V1-2.zip"
    assert fetch.zip_name("N12E103") == "N10E100-N20E110_FABDEM_V1-2.zip"


def test_bad_tile_rejected():
    with pytest.raises(ValueError):
        fetch.zip_name("x")
