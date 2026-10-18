import importlib.util
from pathlib import Path

from py_vapid import Vapid

spec = importlib.util.spec_from_file_location("gen_vapid", Path(__file__).resolve().parents[1] / "scripts" / "gen_vapid.py")
gen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gen)


def test_generated_keys_are_usable_by_pywebpush():
    public, private = gen.generate()
    v = Vapid.from_string(private)          # what pywebpush does with vapid_private_key
    headers = v.sign({"sub": "mailto:a@b.co", "aud": "https://push.example"})
    assert "Authorization" in headers and len(public) == 87      # 65-byte uncompressed point, base64url


def vals(env):
    return dict(ln.split("=", 1) for ln in env.read_text(encoding="utf-8").splitlines() if "=" in ln)


def test_write_env_keeps_a_complete_pair_unless_forced(tmp_path):
    env = tmp_path / ".env"
    env.write_text("DATABASE_URL=sqlite:///x.db\nVAPID_PUBLIC_KEY=oldpub\nVAPID_PRIVATE_KEY=oldpriv\nVAPID_SUBJECT=mailto:a@b.co\n", encoding="utf-8")
    assert gen.write_env(env, "newpub", "newpriv", "mailto:x@y.co") is False
    v = vals(env)
    assert v["VAPID_PUBLIC_KEY"] == "oldpub" and v["VAPID_PRIVATE_KEY"] == "oldpriv" and v["DATABASE_URL"] == "sqlite:///x.db"
    assert gen.write_env(env, "newpub", "newpriv", "mailto:x@y.co", force=True) is True
    v = vals(env)
    assert (v["VAPID_PUBLIC_KEY"], v["VAPID_PRIVATE_KEY"], v["VAPID_SUBJECT"]) == ("newpub", "newpriv", "mailto:x@y.co")


def test_empty_values_from_the_example_are_filled(tmp_path):
    env = tmp_path / ".env"
    env.write_text((Path(__file__).resolve().parents[1] / ".env.example").read_text(encoding="utf-8"), encoding="utf-8")
    assert gen.write_env(env, "pub", "priv", "mailto:x@y.co") is True
    v = vals(env)
    assert v["VAPID_PUBLIC_KEY"] == "pub" and v["VAPID_PRIVATE_KEY"] == "priv" and v["DATABASE_URL"]


def test_a_half_pair_is_replaced_by_a_fresh_matching_pair(tmp_path):
    env = tmp_path / ".env"
    env.write_text("VAPID_PUBLIC_KEY=oldpub\n", encoding="utf-8")
    gen.write_env(env, "newpub", "newpriv", "mailto:x@y.co")
    v = vals(env)
    assert v["VAPID_PUBLIC_KEY"] == "newpub" and v["VAPID_PRIVATE_KEY"] == "newpriv"
    assert env.read_text(encoding="utf-8").count("VAPID_PUBLIC_KEY") == 1


def test_env_file_is_private_where_supported(tmp_path):
    import os
    import stat
    env = tmp_path / ".env"
    gen.write_env(env, "pub", "priv", "mailto:x@y.co")
    if os.name == "posix":
        assert stat.S_IMODE(env.stat().st_mode) == 0o600
