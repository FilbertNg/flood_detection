"""FastAPI app (build plan B1, B3; contract in docs/api-contract.md).

Run: uvicorn floodready.api.app:app --reload   (see scripts/serve_api.py)
"""
from __future__ import annotations

import hmac
import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from . import serialize
from .runner import Runner

log = logging.getLogger(__name__)
DEV_ADMIN = ("admin@floodready.local", "floodready-demo")
bearer = HTTPBearer(auto_error=False)


class LoginRequest(BaseModel):
    email: str
    password: str


class ReplayRequest(BaseModel):
    event: date
    speed: float = 60
    start: str = "06:00"
    end: str = "14:00"
    stop_at: str | None = None


def _secret() -> str:
    return os.environ.get("JWT_SECRET", "dev-only-secret-change-me-before-any-deployment")


def _admin_credentials() -> tuple[str, str]:
    email, password = os.environ.get("ADMIN_EMAIL"), os.environ.get("ADMIN_PASSWORD")
    if not email or not password:
        log.warning("ADMIN_EMAIL / ADMIN_PASSWORD not set: using the development login")
        return DEV_ADMIN
    return email, password


def require_admin(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]) -> str:
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        return jwt.decode(credentials.credentials, _secret(), algorithms=["HS256"])["sub"]
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token") from None


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


def create_app(runner: Runner, start_live_loop: bool = True) -> FastAPI:
    stop = threading.Event()

    def live_loop():
        while not stop.is_set():
            try:
                runner.refresh_live()
            except Exception:
                log.exception("live refresh failed")
            stop.wait(900 - time.time() % 900 + 150)  # 2.5 min after each quarter hour (loggers run at +2)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        thread = threading.Thread(target=live_loop, daemon=True, name="live") if start_live_loop else None
        if thread:
            thread.start()
        yield
        stop.set()
        runner.stop_replay(keep_mode=True)

    app = FastAPI(title="Flood-Ready Township API", version="0.1.0", lifespan=lifespan)
    origins = [o for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173,http://127.0.0.1:5174").split(",") if o]
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])
    ctx = runner.ctx
    api = "/api/v1"

    @app.get(f"{api}/status")
    def get_status():
        return serialize.status(runner.snapshot(), ctx)

    @app.get(f"{api}/streets")
    def get_streets(township: str = "BBR"):
        if township != ctx.township["id"]:
            raise HTTPException(status_code=404, detail=f"Unknown township {township}")
        return serialize.streets_geojson(ctx, runner.snapshot())

    @app.get(f"{api}/streets/{{street_id}}")
    def get_street(street_id: str):
        detail = serialize.street_detail(ctx, runner.snapshot(), street_id)
        if detail is None:
            raise HTTPException(status_code=404, detail=f"Unknown street {street_id}")
        return detail

    @app.get(f"{api}/stations")
    def get_stations(township: str = "BBR"):
        return serialize.stations(ctx, runner.snapshot())

    @app.get(f"{api}/stations/{{graph_id}}/series")
    def get_series(graph_id: str, start: Annotated[str | None, Query(alias="from")] = None,
                   end: Annotated[str | None, Query(alias="to")] = None):
        return serialize.series(runner.snapshot(), graph_id, _parse_time(start), _parse_time(end))

    @app.get(f"{api}/alerts")
    def get_alerts(street_id: str | None = None, active: bool = False):
        alerts = runner.snapshot().alerts
        if street_id:
            alerts = [a for a in alerts if a["street_id"] == street_id]
        if active:
            latest = {}
            for a in alerts:
                latest.setdefault(a["street_id"], a)
            alerts = [a for a in latest.values() if a["kind"] == "alert"]
        return alerts

    @app.post(f"{api}/admin/login")
    def login(body: LoginRequest):
        email, password = _admin_credentials()
        if not (hmac.compare_digest(body.email, email) and hmac.compare_digest(body.password, password)):
            raise HTTPException(status_code=401, detail="Wrong email or password")
        token = jwt.encode({"sub": email, "exp": datetime.now(timezone.utc) + timedelta(hours=12)}, _secret(), algorithm="HS256")
        return {"token": token}

    @app.post(f"{api}/admin/replay")
    def start_replay(body: ReplayRequest, _admin: Annotated[str, Depends(require_admin)]):
        runner.start_replay(body.event, speed=body.speed or None, start=body.start, end=body.end, stop_at=body.stop_at)
        return serialize.status(runner.snapshot(), ctx)

    @app.delete(f"{api}/admin/replay")
    def stop_replay(_admin: Annotated[str, Depends(require_admin)]):
        runner.stop_replay()
        threading.Thread(target=runner.refresh_live, daemon=True).start()
        return serialize.status(runner.snapshot(), ctx)

    return app
