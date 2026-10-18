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


def test_write_env_keeps_existing_values_unless_forced(tmp_path):
    env = tmp_path / ".env"
    env.write_text("DATABASE_URL=sqlite:///x.db\nVAPID_PUBLIC_KEY=old\n", encoding="utf-8")
    written = gen.write_env(env, {"VAPID_PUBLIC_KEY": "new", "VAPID_PRIVATE_KEY": "p"})
    text = env.read_text(encoding="utf-8")
    assert written == ["VAPID_PRIVATE_KEY"] and "VAPID_PUBLIC_KEY=old" in text and "DATABASE_URL=sqlite:///x.db" in text
    gen.write_env(env, {"VAPID_PUBLIC_KEY": "new"}, force=True)
    assert "VAPID_PUBLIC_KEY=new" in env.read_text(encoding="utf-8")
