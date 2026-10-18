import pytest


@pytest.fixture(autouse=True)
def _no_real_vapid_keys(monkeypatch):
    """Tests never use VAPID keys exported in the developer's shell."""
    for name in ("VAPID_PUBLIC_KEY", "VAPID_PRIVATE_KEY", "VAPID_SUBJECT"):
        monkeypatch.delenv(name, raising=False)
