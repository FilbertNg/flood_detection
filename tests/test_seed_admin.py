import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import select

from floodready.api import auth
from floodready.db import repo, schema

ROOT = Path(__file__).resolve().parents[1]


def load():
    spec = importlib.util.spec_from_file_location("seed_admin", ROOT / "scripts" / "seed_admin.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def user(db, email):
    with repo.connect(f"sqlite:///{db.as_posix()}").begin() as c:
        return auth.get_user(c, email)


def test_seed_from_env_creates_a_bcrypt_admin(tmp_path, monkeypatch):
    db = tmp_path / "x.db"
    monkeypatch.setenv("ADMIN_EMAIL", "Boss@Example.org")
    monkeypatch.setenv("ADMIN_PASSWORD", "a-long-enough-pass")
    assert load().main(["--url", f"sqlite:///{db.as_posix()}"]) == 0
    u = user(db, "boss@example.org")
    assert u["role"] == "admin" and u["password_hash"].startswith("$2") and "a-long-enough-pass" not in u["password_hash"]
    assert auth.check_password("a-long-enough-pass", u["password_hash"])


def test_reseed_replaces_password_and_role(tmp_path, monkeypatch, capsys):
    db = tmp_path / "x.db"
    url = f"sqlite:///{db.as_posix()}"
    monkeypatch.delenv("ADMIN_EMAIL", raising=False)
    monkeypatch.setenv("ADMIN_PASSWORD", "first-password-1")
    seed = load()
    seed.main(["--email", "a@b.org", "--url", url])
    monkeypatch.setenv("ADMIN_PASSWORD", "second-password-2")
    seed.main(["--email", "a@b.org", "--role", "viewer", "--url", url])
    u = user(db, "a@b.org")
    assert u["role"] == "viewer" and auth.check_password("second-password-2", u["password_hash"])
    assert "second-password-2" not in capsys.readouterr().out
    with repo.connect(url).begin() as c:
        assert len(c.execute(select(schema.admin_users)).all()) == 1


def test_overlong_password_fails_cleanly(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("ADMIN_PASSWORD", "x" * 80)
    assert load().main(["--email", "a@b.org", "--url", f"sqlite:///{(tmp_path / 'x.db').as_posix()}"]) == 1
    assert "password" in capsys.readouterr().err


def test_script_runs_as_a_command(tmp_path):
    env = {"ADMIN_PASSWORD": "command-line-pass-1", "PATH": "", "SYSTEMROOT": "C:\\Windows"}
    out = subprocess.run([sys.executable, "scripts/seed_admin.py", "--email", "c@d.org", "--url",
                          f"sqlite:///{(tmp_path / 'y.db').as_posix()}"], cwd=ROOT, env=env, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert "command-line-pass-1" not in out.stdout
