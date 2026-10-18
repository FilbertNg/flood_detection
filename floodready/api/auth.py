"""Admin authentication: bcrypt password hashes in `admin_users`, HS256 JWTs with a role (WP8).

Roles: `admin` can read and write; `viewer` can only read (every write route depends on `require_admin_role`).

Login sources, in order:
1. the `admin_users` table (create users with scripts/seed_admin.py);
2. the `ADMIN_EMAIL` + `ADMIN_PASSWORD` environment pair (admin role; needs `JWT_SECRET`);
3. the development login, ONLY while ADMIN_EMAIL, ADMIN_PASSWORD and JWT_SECRET are all unset and `admin_users`
   is empty. It logs a loud warning. Never deploy like that.
"""

import hmac
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import func, insert, select, update

from ..db import schema as t

log = logging.getLogger(__name__)

DEV_ADMIN = ("admin@floodready.local", "floodready-demo")
DEV_SECRET = "dev-only-secret-change-me-before-any-deployment"
ROLES = ("admin", "viewer")
TOKEN_HOURS = 12
MAX_PASSWORD_BYTES = 72          # bcrypt ignores everything after 72 bytes; refuse instead of silently truncating
bearer = HTTPBearer(auto_error=False)
_DUMMY_HASH = bcrypt.hashpw(b"not-a-real-password", bcrypt.gensalt(rounds=4))   # equalises timing for unknown users


@dataclass(frozen=True)
class Principal:
    email: str
    role: str

    @property
    def can_write(self) -> bool:
        return self.role == "admin"


# ---------- users ----------

def hash_password(password: str) -> str:
    raw = password.encode("utf-8")
    if not raw or len(raw) > MAX_PASSWORD_BYTES:
        raise ValueError(f"password must be 1 to {MAX_PASSWORD_BYTES} bytes")
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("ascii")


def check_password(password: str, password_hash: str | None) -> bool:
    """Constant-ish time: an unknown user is checked against a dummy hash."""
    raw = password.encode("utf-8")
    target = password_hash.encode("ascii") if password_hash else _DUMMY_HASH
    if len(raw) > MAX_PASSWORD_BYTES:
        return False
    try:
        ok = bcrypt.checkpw(raw, target)
    except ValueError:
        return False
    return ok and password_hash is not None


def create_user(conn, email: str, password: str, role: str = "viewer") -> None:
    """Insert the user, or replace the password hash and role of an existing one."""
    if role not in ROLES:
        raise ValueError(f"role must be one of {ROLES}")
    email = email.strip().lower()
    if not email or "@" not in email:
        raise ValueError("email is required")
    values = {"password_hash": hash_password(password), "role": role}
    if conn.execute(select(t.admin_users.c.email).where(t.admin_users.c.email == email)).first():
        conn.execute(update(t.admin_users).where(t.admin_users.c.email == email).values(**values))
    else:
        conn.execute(insert(t.admin_users).values(email=email, **values))


def get_user(conn, email: str) -> dict | None:
    r = conn.execute(select(t.admin_users).where(t.admin_users.c.email == email.strip().lower())).first()
    return {"email": r.email, "password_hash": r.password_hash, "role": r.role} if r else None


def user_count(conn) -> int:
    return int(conn.execute(select(func.count()).select_from(t.admin_users)).scalar_one())


# ---------- configuration ----------

def dev_mode(conn) -> bool:
    """True only when nothing is configured: no ADMIN_EMAIL / ADMIN_PASSWORD / JWT_SECRET and no admin users."""
    return not any(os.environ.get(v) for v in ("ADMIN_EMAIL", "ADMIN_PASSWORD", "JWT_SECRET")) and user_count(conn) == 0


def secret(conn=None) -> str | None:
    s = os.environ.get("JWT_SECRET")
    if s:
        return s
    return DEV_SECRET if conn is not None and dev_mode(conn) else None


def warn_if_dev(conn) -> None:
    if dev_mode(conn):
        log.warning("*** DEVELOPMENT admin login is ACTIVE (%s / %s) because ADMIN_EMAIL, ADMIN_PASSWORD and JWT_SECRET are "
                    "unset and there are no admin users. Run scripts/seed_admin.py and set JWT_SECRET before any deployment. ***",
                    DEV_ADMIN[0], DEV_ADMIN[1])


# ---------- tokens ----------

def issue_token(email: str, role: str, key: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=TOKEN_HOURS)
    return jwt.encode({"sub": email, "role": role, "exp": exp}, key, algorithm="HS256")


def authenticate(conn, email: str, password: str) -> Principal | None:
    """Principal for valid credentials, else None. Every source is checked in constant time."""
    user = get_user(conn, email)
    db_ok = check_password(password, user["password_hash"] if user else None)
    if db_ok:
        return Principal(user["email"], user["role"] if user["role"] in ROLES else "viewer")
    env_email, env_password = os.environ.get("ADMIN_EMAIL"), os.environ.get("ADMIN_PASSWORD")
    if env_email and env_password:
        if hmac.compare_digest(email.encode(), env_email.encode()) & hmac.compare_digest(password.encode(), env_password.encode()):
            return Principal(env_email, "admin")
    elif dev_mode(conn):
        log.warning("DEVELOPMENT admin login used")
        if hmac.compare_digest(email.encode(), DEV_ADMIN[0].encode()) & hmac.compare_digest(password.encode(), DEV_ADMIN[1].encode()):
            return Principal(DEV_ADMIN[0], "admin")
    return None


def make_dependencies(get_conn_engine):
    """FastAPI dependencies bound to an engine: (require_admin, require_admin_role)."""

    def current(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> Principal:
        if credentials is None:
            raise HTTPException(status_code=401, detail="Missing token")
        with get_conn_engine().connect() as conn:
            key = secret(conn)
        if key is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        try:
            claims = jwt.decode(credentials.credentials, key, algorithms=["HS256"], options={"require": ["exp", "sub"]})
        except jwt.PyJWTError:
            raise HTTPException(status_code=401, detail="Invalid token") from None
        role = claims.get("role")
        return Principal(str(claims["sub"]), role if role in ROLES else "viewer")

    def writer(who: Annotated[Principal, Depends(current)]) -> Principal:
        if not who.can_write:
            raise HTTPException(status_code=403, detail="This account is read-only")
        return who

    return current, writer
