import numpy as np

from floodready.ml import train


def test_saved_models_are_compressed_and_load_back(tmp_path):
    """Trigger bundles are committed to git, so they are stored compressed (like the forecast bundles)."""
    model = {"weights": np.zeros(500_000)}          # 4 MB raw
    path = tmp_path / "trigger.joblib"
    train.save_model(model, path, ["x"], {})
    assert path.stat().st_size < 400_000
    bundle = train.load_model(path)
    assert bundle["features"] == ["x"] and np.array_equal(bundle["model"]["weights"], model["weights"])
