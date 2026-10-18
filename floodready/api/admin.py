"""Admin endpoints (WP8; contract in docs/api-contract.md): login, statistics, report, suggestions, answers, notes,
and the read-only photo route.

Reads need any valid token; every write needs the `admin` role (see auth.py). Installed by `create_app`.
"""

import logging
import os
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal

import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..db import repo
from ..stats import report as report_mod
from ..stats import statistics
from . import auth

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]
PHOTO_NAME = r"^[A-Za-z0-9_-]{1,64}\.(jpg|jpeg|png|webp)$"
MEDIA = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


class LoginRequest(BaseModel):
    email: str = Field(max_length=200)
    password: str = Field(max_length=1000)


class SuggestionUpdate(BaseModel):
    status: Literal["open", "accepted", "dismissed", "done"]
    note: str | None = Field(default=None, max_length=2000)


class AnswerReview(BaseModel):
    review_status: Literal["valid", "spam"]


class OpsNoteRequest(BaseModel):
    street_id: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=2000)


def events_path() -> Path:
    return Path(os.environ.get("EVENTS_CSV") or ROOT / "data" / "events" / "events.csv")


def load_events() -> pd.DataFrame | None:
    """Labelled events (data/events/events.csv, or $EVENTS_CSV); None when the file does not exist or cannot be read."""
    path = events_path()
    if not path.is_file():
        return None
    try:
        return pd.read_csv(path, dtype={"street_id": str})
    except Exception:
        log.exception("could not read %s", path)
        return None


def answer_view(row: dict) -> dict:
    out = {k: v for k, v in row.items() if k != "photo_path"}
    out["photo_url"] = f"/uploads/{row['photo_path']}" if row.get("photo_path") else None
    return out


def station_frame(ctx) -> pd.DataFrame:
    """graph_id, kind (rf/wl), name for the township's configured stations."""
    names = {}
    for gid, name in zip(ctx.stations["graph_id"], ctx.stations["name"]):
        names.setdefault(str(gid), name)
    rows = [{"graph_id": str(s["graph_id"]), "kind": k.lower(), "name": names.get(str(s["graph_id"]))}
            for s in ctx.township.get("stations", []) for k in s.get("types", [])]
    return pd.DataFrame(rows, columns=["graph_id", "kind", "name"])


def install(app: FastAPI, *, ctx, runner, api: str = "/api/v1") -> tuple:
    """Add the admin routes; returns the (read, write) auth dependencies for other admin routes (replay)."""
    read, write = auth.make_dependencies(lambda: runner.db)
    names = dict(zip(ctx.streets["street_id"], ctx.streets["name"]))
    with runner.db.connect() as conn:
        auth.warn_if_dev(conn)

    def readings_for(date_from: date, date_to: date) -> pd.DataFrame:
        start = datetime.combine(date_from, datetime.min.time())
        end = datetime.combine(date_to, datetime.min.time()) + timedelta(days=1)
        frame = ctx.load_readings(start, end)
        if ctx.load_live_readings is not None:
            try:
                live = ctx.load_live_readings(start)
                if live is not None and not live.empty:
                    keep = ["graph_id", "kind", "time_local", "rain_15min_mm", "wl_m"]
                    frame = pd.concat([frame, live[[c for c in keep if c in live.columns]]], ignore_index=True)
                    frame = frame.drop_duplicates(["graph_id", "kind", "time_local"], keep="first")
            except Exception:
                log.exception("live readings unavailable for station health")
        return frame

    @app.post(f"{api}/admin/login")
    def login(body: LoginRequest):
        with runner.db.connect() as conn:
            who = auth.authenticate(conn, body.email, body.password)
            if who is None:
                raise HTTPException(status_code=401, detail="Wrong email or password")
            key = auth.secret(conn)
        if key is None:
            raise HTTPException(status_code=503, detail="JWT_SECRET is not set on this server")
        return {"token": auth.issue_token(who.email, who.role, key)}

    @app.get(f"{api}/admin/stats")
    def get_stats(_who: Annotated[auth.Principal, Depends(read)], date_from: Annotated[date, Query(alias="from")],
                  date_to: Annotated[date, Query(alias="to")]):
        if date_from > date_to:
            raise HTTPException(status_code=422, detail="from must be on or before to")
        with runner.db.connect() as conn:
            return statistics.stats(conn, date_from, date_to, street_names=names, events=load_events(),
                                    readings=readings_for(date_from, date_to), stations=station_frame(ctx),
                                    street_stations=ctx.street_stations)

    @app.get(f"{api}/admin/report")
    def get_report(_who: Annotated[auth.Principal, Depends(read)], month: str):
        try:
            date_from, date_to = report_mod.month_range(month)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None
        with runner.db.connect() as conn:
            return report_mod.monthly_report(conn, month, street_names=names, events=load_events(),
                                             readings=readings_for(date_from, date_to), stations=station_frame(ctx),
                                             street_stations=ctx.street_stations)

    @app.get(f"{api}/admin/suggestions")
    def get_suggestions(_who: Annotated[auth.Principal, Depends(read)],
                        date_from: Annotated[date | None, Query(alias="from")] = None,
                        date_to: Annotated[date | None, Query(alias="to")] = None):
        with runner.db.connect() as conn:
            return [report_mod.suggestion_view(r, names) for r in repo.list_suggestions(conn, date_from, date_to)]

    @app.patch(f"{api}/admin/suggestions/{{suggestion_id}}")
    def patch_suggestion(suggestion_id: str, body: SuggestionUpdate, _who: Annotated[auth.Principal, Depends(write)]):
        with runner.db.begin() as conn:
            old = repo.get_suggestion(conn, suggestion_id)
            if old is None:
                raise HTTPException(status_code=404, detail="Unknown suggestion")
            repo.update_suggestion(conn, suggestion_id, body.status,
                                   body.note if "note" in body.model_fields_set else old["note"])
            return report_mod.suggestion_view(repo.get_suggestion(conn, suggestion_id), names)

    @app.get(f"{api}/admin/answers")
    def get_answers(_who: Annotated[auth.Principal, Depends(read)],
                    review_status: Literal["pending", "valid", "spam"] | None = None):
        with runner.db.connect() as conn:
            return [answer_view(r) for r in repo.list_answers(conn, review_status=review_status)]

    @app.patch(f"{api}/admin/answers/{{answer_id}}")
    def patch_answer(answer_id: str, body: AnswerReview, _who: Annotated[auth.Principal, Depends(write)]):
        with runner.db.begin() as conn:
            if repo.get_answer(conn, answer_id) is None:
                raise HTTPException(status_code=404, detail="Unknown answer")
            repo.set_answer_review(conn, answer_id, body.review_status)
            return answer_view(repo.get_answer(conn, answer_id))

    @app.post(f"{api}/admin/notes", status_code=204)
    def post_note(body: OpsNoteRequest, who: Annotated[auth.Principal, Depends(write)]):
        if body.street_id not in names:
            raise HTTPException(status_code=404, detail=f"Unknown street {body.street_id}")
        with runner.db.begin() as conn:
            repo.insert_note(conn, body.street_id, body.text.strip(), who.email)
        return Response(status_code=204)

    @app.get("/uploads/{name}")
    def get_upload(name: str):
        """Resident photos, read-only. File names are random (uuid4), the pattern allows no path separators and the
        resolved file must sit directly inside UPLOADS_DIR."""
        if not re.fullmatch(PHOTO_NAME, name):
            raise HTTPException(status_code=404, detail="Not found")
        base = repo.uploads_dir().resolve()
        path = (base / name).resolve()
        if path.parent != base or not path.is_file():
            raise HTTPException(status_code=404, detail="Not found")
        return FileResponse(path, media_type=MEDIA[path.suffix.lower()],
                            headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, max-age=3600"})

    return read, write
