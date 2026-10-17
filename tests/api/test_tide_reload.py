import pandas as pd


def test_engine_context_reads_the_tide_through_its_loader(context):
    context.tide = None
    assert context.tide_table() is None
    table = pd.DataFrame({"time_local": [pd.Timestamp("2026-10-16")], "tide_height_m": [1.0]})
    context.tide_loader = lambda: table
    assert context.tide_table() is table
