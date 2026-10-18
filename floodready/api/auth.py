"""Admin authentication: bcrypt password hashes in `admin_users`, HS256 JWTs, roles, login limits, signed photo links.

Roles: `admin` can read and write; `viewer` can only read (every write route depends on the `write` dependency). The
token's `role` claim is only a hint: the role is read from `admin_users` on every request, so a downgraded or deleted
user loses access at once.

Login sources, in order:
1. the `admin_users` table (create users with scripts/seed_admin.py);
2. the `ADMIN_EMAIL` + `ADMIN_PASSWORD` environment pair (admin role; needs a valid `JWT_SECRET`);
3. the development login, ONLY when FLOODREADY_DEV_LOGIN=1 is set explicitly AND ADMIN_EMAIL, ADMIN_PASSWORD and
   JWT_SECRET are unset AND `admin_users` is empty. Absent configuration never turns it on.

`JWT_SECRET` must be at least 32 bytes; a shorter one is treated as unset. Without a usable secret (and without the
dev flag) login answers 503 "admin login not configured" and every token is rejected.
"""
import hashlib
import hmac
import logging
import os
import time
from collections import defaultdict, deque
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
MIN_SECRET_BYTES = 32
MAX_PASSWORD_BYTES = 72          # bcrypt ignores everything after 72 bytes; refuse instead of silently truncating
UPLOAD_URL_TTL = 3600
bearer = HTTPBearer(auto_error=False)
# same cost as real hashes (gensalt default), so a known and an unknown e-mail take about the same time
_DUMMY_HASH = bcrypt.hashpw(b"not-a-real-password", bcrypt.gensalt())


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
    """An unknown user (no hash) is checked against a dummy hash of the same cost, then rejected."""
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

def dev_flag() -> bool:
    return os.environ.get("FLOODREADY_DEV_LOGIN") == "1"


def real_secret() -> str | None:
    """JWT_SECRET when it is at least 32 bytes, else None (a short one is logged and ignored)."""
    s = os.environ.get("JWT_SECRET")
    if not s:
        return None
    if len(s.encode("utf-8")) < MIN_SECRET_BYTES:
        log.error("JWT_SECRET is shorter than %d bytes and is ignored; admin login stays off", MIN_SECRET_BYTES)
        return None
    return s


def dev_mode(conn) -> bool:
    """The development login: explicit FLOODREADY_DEV_LOGIN=1, nothing configured, no admin users."""
    return (dev_flag() and not any(os.environ.get(v) for v in ("ADMIN_EMAIL", "ADMIN_PASSWORD", "JWT_SECRET"))
            and user_count(conn) == 0)


def secret(conn=None) -> str | None:
    real = real_secret()
    if real:
        return real
    return DEV_SECRET if conn is not None and dev_mode(conn) else None


def upload_key(conn) -> str | None:
    """Key for signed photo links: UPLOAD_URL_SECRET (>= 32 bytes) or the JWT secret."""
    s = os.environ.get("UPLOAD_URL_SECRET")
    return s if s and len(s.encode("utf-8")) >= MIN_SECRET_BYTES else secret(conn)


def warn_if_dev(conn) -> None:
    if dev_flag():
        log.warning("*** FLOODREADY_DEV_LOGIN=1: the DEVELOPMENT admin login (%s / %s) and the published dev signing "
                    "secret are %s. Never set this on a reachable host. ***", DEV_ADMIN[0], DEV_ADMIN[1],
                    "ACTIVE" if dev_mode(conn) else "requested but off (real credentials are configured)")
    elif secret(conn) is None:
        log.warning("Admin login is not configured: set JWT_SECRET (>= %d bytes) and run scripts/seed_admin.py", MIN_SECRET_BYTES)


# ---------- tokens ----------

def issue_token(email: str, role: str, key: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=TOKEN_HOURS)
    return jwt.encode({"sub": email, "role": role, "exp": exp}, key, algorithm="HS256")


def authenticate(conn, email: str, password: str) -> Principal | None:
    """Principal for valid credentials, else None. The database check always costs one bcrypt comparison."""
    user = get_user(conn, email)
    if check_password(password, user["password_hash"] if user else None):
        return Principal(user["email"], user["role"] if user["role"] in ROLES else "viewer")
    env_email, env_password = os.environ.get("ADMIN_EMAIL"), os.environ.get("ADMIN_PASSWORD")
    if env_email and env_password:
        if hmac.compare_digest(email.strip().lower().encode(), env_email.strip().lower().encode()) & \
                hmac.compare_digest(password.encode(), env_password.encode()):
            return Principal(env_email.strip().lower(), "admin")
    elif dev_mode(conn):
        log.warning("DEVELOPMENT admin login used")
        if hmac.compare_digest(email.encode(), DEV_ADMIN[0].encode()) & hmac.compare_digest(password.encode(), DEV_ADMIN[1].encode()):
            return Principal(DEV_ADMIN[0], "admin")
    return None


def principal_for(conn, claims: dict) -> Principal | None:
    """The live principal for a verified token: the role comes from the database, not from the token. A user who is
    gone is rejected; the env admin and (in dev mode) the dev admin have no row and keep the admin role."""
    email = str(claims["sub"])
    user = get_user(conn, email)
    if user:
        return Principal(user["email"], user["role"] if user["role"] in ROLES else "viewer")
    env_email = (os.environ.get("ADMIN_EMAIL") or "").strip().lower()
    if os.environ.get("ADMIN_PASSWORD") and env_email and email == env_email:
        return Principal(email, "admin")
    if email == DEV_ADMIN[0] and dev_mode(conn):
        return Principal(email, "admin")
    return None


def make_dependencies(connect):
    """FastAPI dependencies bound to a connection factory `connect()` (a context manager, e.g. under the runner's
    lock): (read, write). `read` needs any valid token; `write` needs the admin role."""

    def current(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> Principal:
        if credentials is None:
            raise HTTPException(status_code=401, detail="Missing token")
        with connect() as conn:
            key = secret(conn)
            if key is None:
                raise HTTPException(status_code=401, detail="Invalid token")
            try:
                claims = jwt.decode(credentials.credentials, key, algorithms=["HS256"], options={"require": ["exp", "sub"]})
            except jwt.PyJWTError:
                raise HTTPException(status_code=401, detail="Invalid token") from None
            who = principal_for(conn, claims)
        if who is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return who

    def writer(who: Annotated[Principal, Depends(current)]) -> Principal:
        if not who.can_write:
            raise HTTPException(status_code=403, detail="This account is read-only")
        return who

    return current, writer


# ---------- login limits ----------

class LoginLimiter:
    """In memory, per process. Failed logins per e-mail (default 5 per 15 min, then 429; cleared by a success) and
    attempts per client IP (default 20 per minute). The e-mail key matters because behind a proxy the client IP may
    be the proxy for everyone."""

    MAX_KEYS = 5000

    def __init__(self, email_limit: int = 5, email_window: float = 900.0, ip_limit: int = 20, ip_window: float = 60.0,
                 clock=time.monotonic):
        self.email_limit, self.email_window, self.ip_limit, self.ip_window, self.clock = \
            email_limit, email_window, ip_limit, ip_window, clock
        self.failures: dict[str, deque] = defaultdict(deque)
        self.attempts: dict[str, deque] = defaultdict(deque)

    @staticmethod
    def _trim(q: deque, window: float, now: float) -> None:
        while q and now - q[0] > window:
            q.popleft()

    def _prune(self, table: dict, window: float, now: float) -> None:
        if len(table) > self.MAX_KEYS:
            for key in list(table):
                self._trim(table[key], window, now)
                if not table[key]:
                    del table[key]

    def allow(self, ip: str, email: str) -> bool:
        """Count this attempt against the IP; False when the IP or the e-mail is over its limit."""
        now = self.clock()
        email = email.strip().lower()[:200]
        self._prune(self.attempts, self.ip_window, now)
        self._prune(self.failures, self.email_window, now)
        q = self.attempts[ip]
        self._trim(q, self.ip_window, now)
        if len(q) >= self.ip_limit:
            return False
        q.append(now)
        f = self.failures[email]
        self._trim(f, self.email_window, now)
        return len(f) < self.email_limit

    def failed(self, email: str) -> None:
        self.failures[email.strip().lower()[:200]].append(self.clock())

    def succeeded(self, email: str) -> None:
        self.failures.pop(email.strip().lower()[:200], None)


# ---------- signed photo links ----------

def _upload_sig(name: str, exp: int, key: str) -> str:
    return hmac.new(key.encode(), f"{name}|{exp}".encode(), hashlib.sha256).hexdigest()[:32]


def sign_upload(name: str, key: str, now: float | None = None, ttl: int = UPLOAD_URL_TTL) -> str:
    exp = int((now if now is not None else time.time()) + ttl)
    return f"/uploads/{name}?exp={exp}&sig={_upload_sig(name, exp, key)}"


def verify_upload(name: str, exp: str | None, sig: str | None, key: str | None, now: float | None = None) -> bool:
    if not key or not exp or not sig or not exp.isdigit():
        return False
    if int(exp) < (now if now is not None else time.time()):
        return False
    return hmac.compare_digest(sig, _upload_sig(name, int(exp), key))
