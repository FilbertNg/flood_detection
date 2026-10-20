"""Resident answers, reports and the water-level sensor (build plan B4; WP4).

`install(app, ...)` adds POST /answers (multipart) and POST /sensor/readings. Privacy: the photo is re-encoded so no
metadata survives and is stored under a random name; coordinates are rounded to 3 decimals; no names or addresses.
"""
from __future__ import annotations

import hmac
import io
import logging
import math
import os
import warnings
from contextlib import contextmanager
from collections import defaultdict, deque
import time
import uuid
from datetime import timedelta
from pathlib import Path
from typing import Annotated, Callable

from fastapi import FastAPI, File, Form, Header, HTTPException, Request, Response, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field

from ..db import repo, schema
from ..jobs import now_myt

log = logging.getLogger(__name__)

ANSWERS = ("yes", "no", "not_sure", "report")
DEPTHS = ("ankle", "knee", "above_knee")
MAX_PHOTO_BYTES = 10 * 1024 * 1024
MAX_PHOTO_SIDE = 2048
MAX_PIXELS = 40_000_000
MAX_BODY_BYTES = 11 * 1024 * 1024
RATE_LIMIT = (10, 60.0)      # answers per IP per window (seconds)
SENSOR_WINDOW = timedelta(hours=3)


class SensorBody(BaseModel):
    device_id: str = Field(min_length=1, max_length=64)
    level_cm: float          # range checked in the handler: FastAPI cannot render a 422 whose input is inf/nan
    simulated: bool


_ROTATE = {3: Image.Transpose.ROTATE_180, 6: Image.Transpose.ROTATE_270, 8: Image.Transpose.ROTATE_90,
           2: Image.Transpose.FLIP_LEFT_RIGHT, 4: Image.Transpose.FLIP_TOP_BOTTOM,
           5: Image.Transpose.TRANSPOSE, 7: Image.Transpose.TRANSVERSE}
from PIL import JpegImagePlugin, PngImagePlugin, WebPImagePlugin  # noqa: E402,F401  (phone MPO files open through the JPEG plugin)

Image.MAX_IMAGE_PIXELS = MAX_PIXELS    # Pillow only errors beyond 2x this, so the warning below is made an error too


def clean_image(data: bytes) -> bytes:
    """Decode and re-encode as a fresh JPEG: pixels only, so EXIF/GPS/XMP and any trailing data are dropped.

    Cheap against hostile files: only JPEG/MPO/PNG/WEBP decoders, a 40 MP limit checked before decoding (the bomb
    warning is an error), JPEG draft mode and a thumbnail before any full-size copy is made."""
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data), formats=["JPEG", "PNG", "WEBP"]) as src:
                if src.width * src.height > MAX_PIXELS:
                    raise HTTPException(status_code=422, detail="The photo has too many pixels")
                orientation = src.getexif().get(0x0112)
                if src.format in ("JPEG", "MPO"):
                    src.draft("RGB", (MAX_PHOTO_SIDE, MAX_PHOTO_SIDE))
                src.load()
                if src.mode in ("RGBA", "LA", "P", "PA"):
                    rgba = src.convert("RGBA")
                    img = Image.new("RGB", rgba.size, (255, 255, 255))
                    img.paste(rgba, mask=rgba.getchannel("A"))
                else:
                    img = src.convert("RGB")
            img.thumbnail((MAX_PHOTO_SIDE, MAX_PHOTO_SIDE))
            if orientation in _ROTATE:                  # bake the rotation in before the orientation tag is dropped
                img = img.transpose(_ROTATE[orientation])
            clean = Image.new("RGB", img.size)
            clean.paste(img)
            out = io.BytesIO()
            clean.save(out, "JPEG", quality=85)
            return out.getvalue()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise HTTPException(status_code=422, detail="The photo is not a readable image") from exc


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371000 * 2 * math.asin(math.sqrt(a))


def street_centroids(streets) -> dict[str, tuple[float, float]]:
    """street_id -> (lat, lon) of the street's centroid (computed in Web Mercator, fine at 3 degrees N)."""
    proj = streets.to_crs(3857)
    cent = proj.geometry.centroid
    back = cent.set_crs(3857).to_crs(4326)
    return {sid: (pt.y, pt.x) for sid, pt in zip(streets["street_id"], back)}


def install(app: FastAPI, *, ctx, runner, api: str = "/api/v1",
            on_confirmed: Callable[[dict], None] | None = None, rate_limit: tuple[int, float] = RATE_LIMIT) -> None:
    street_names = dict(zip(ctx.streets.street_id, ctx.streets.name))

    def push_confirmed(alert: dict) -> None:
        runner.push.enqueue_confirmed([alert], street_names)       # on the push worker thread, never in the request

    hook = on_confirmed or push_confirmed

    @contextmanager
    def transaction():
        """The runner's database, under its lock (one SQLite connection is shared across threads)."""
        with runner._db_lock, runner.db.begin() as conn:
            yield conn
    centroids = street_centroids(ctx.streets)
    hits: dict[str, deque] = defaultdict(deque)

    @app.middleware("http")
    async def limit_answer_body(request: Request, call_next):
        # Starlette spools a whole multipart body before the handler runs, so refuse oversized ones up front
        if request.method == "POST" and request.url.path == f"{api}/answers":
            length = request.headers.get("content-length")
            if length is not None and length.isdigit() and int(length) > MAX_BODY_BYTES:
                return JSONResponse({"detail": "Request too large"}, status_code=413)
        return await call_next(request)

    def rate_limited(ip: str) -> bool:
        limit, window = rate_limit
        q, now = hits[ip], time.monotonic()
        while q and now - q[0] > window:
            q.popleft()
        if len(q) >= limit:
            return True
        q.append(now)
        return False

    def subscribed_confirmer(conn, alert: dict) -> bool:
        """The push goes out only if a device that said yes is subscribed to the street (anti-abuse)."""
        devices = [r.device_id for r in conn.execute(select(schema.answers.c.device_id).where(
            schema.answers.c.alert_id == alert["alert_id"], schema.answers.c.answer == "yes"))]
        return bool(devices) and conn.execute(select(schema.subscription_streets.c.device_id).where(
            schema.subscription_streets.c.device_id.in_(devices),
            schema.subscription_streets.c.street_id == alert["street_id"])).first() is not None

    def fire(alert: dict) -> None:
        try:
            hook(alert)
        except Exception:   # a push failure must never fail the resident's answer
            log.exception("confirmed-push hook failed for %s", alert.get("alert_id"))

    def find_alert(conn, alert_id: str) -> dict | None:
        found = repo.list_alerts(conn, alert_id=alert_id)       # live and replay rows; backfill is excluded
        return found[0] if found else None

    @app.post(f"{api}/answers")
    def post_answer(
        request: Request,
        device_id: Annotated[str, Form(min_length=1, max_length=64)],
        street_id: Annotated[str, Form()],
        answer: Annotated[str, Form()],
        alert_id: Annotated[str | None, Form()] = None,
        depth: Annotated[str | None, Form()] = None,
        lat: Annotated[float | None, Form(ge=-90, le=90)] = None,
        lon: Annotated[float | None, Form(ge=-180, le=180)] = None,
        photo: Annotated[UploadFile | None, File()] = None,
    ):
        if rate_limited(request.client.host if request.client else "?"):
            raise HTTPException(status_code=429, detail="Too many answers, try again in a minute")
        if street_id not in centroids:
            raise HTTPException(status_code=404, detail=f"Unknown street {street_id}")
        if answer not in ANSWERS:
            raise HTTPException(status_code=422, detail=f"answer must be one of {', '.join(ANSWERS)}")
        if depth in ("",):
            depth = None
        if depth is not None and depth not in DEPTHS:
            raise HTTPException(status_code=422, detail=f"depth must be one of {', '.join(DEPTHS)}")
        if (lat is None) != (lon is None):
            raise HTTPException(status_code=422, detail="lat and lon go together")
        alert_id = alert_id or None

        data = None
        if photo is not None and (photo.filename or photo.size):
            if not (photo.content_type or "").startswith("image/"):
                raise HTTPException(status_code=422, detail="The photo must be an image")
            raw = photo.file.read(MAX_PHOTO_BYTES + 1)
            if len(raw) > MAX_PHOTO_BYTES:
                raise HTTPException(status_code=413, detail="The photo is larger than 10 MB")
            data = clean_image(raw)

        distance = None
        if lat is not None:
            c_lat, c_lon = centroids[street_id]
            distance = round(_haversine_m(lat, lon, c_lat, c_lon), 1)

        path: Path | None = None
        confirmed_alert = None
        try:
            with transaction() as conn:
                source = "demo" if runner.snapshot().mode == "replay" and alert_id is None else "resident"
                alert = None
                if alert_id is not None:
                    alert = find_alert(conn, alert_id)
                    if alert is None or alert["street_id"] != street_id:
                        raise HTTPException(status_code=422, detail="alert_id does not belong to this street")
                    if alert.get("is_replay"):
                        source = "demo"          # replay answers are demo rows: shown, never counted in statistics
                    before = repo.outcomes_for(conn, [alert])[alert_id]
                if data is not None:
                    directory = repo.uploads_dir()
                    directory.mkdir(parents=True, exist_ok=True)
                    path = directory / f"{uuid.uuid4().hex}.jpg"
                    path.write_bytes(data)
                try:
                    answer_id = repo.insert_answer(conn, {
                        "device_id": device_id, "alert_id": alert_id, "street_id": street_id, "answer": answer,
                        "depth": depth, "photo_path": path.name if path else None,
                        "lat3": None if lat is None else round(lat, 3), "lon3": None if lon is None else round(lon, 3),
                        "distance_m": distance, "source": source})
                except repo.DuplicateAnswer:
                    raise HTTPException(status_code=409, detail="This device already answered this alert") from None
                if alert is not None and before != "confirmed" and answer == "yes":
                    if repo.outcomes_for(conn, [alert])[alert_id] == "confirmed" and subscribed_confirmer(conn, alert):
                        # a confirmation is not a repeated Watch: the Watch push cap does not apply to it
                        confirmed_alert = {**alert, "outcome": "confirmed", "push": repo.push_eligible(conn, alert_id)}
        except BaseException:
            if path is not None:
                path.unlink(missing_ok=True)
            raise
        if confirmed_alert is not None:
            fire(confirmed_alert)
        return {"answer_id": answer_id}

    def sensor_candidates(conn, device_id: str) -> list[dict]:
        """Live DB alerts on the sensor's streets that are still inside the 3 h window."""
        streets = repo.sensor_devices().get(device_id, set())
        horizon = now_myt() - SENSOR_WINDOW
        found = {a["alert_id"]: a for a in repo.list_alerts(conn, active=True, include_replay=False) if a["street_id"] in streets}
        return [a for a in found.values() if repo._naive(a["issued_at"]) >= horizon]

    @app.post(f"{api}/sensor/readings", status_code=204)
    def post_sensor(body: SensorBody, authorization: Annotated[str | None, Header()] = None):
        token = os.environ.get("SENSOR_TOKEN", "")
        scheme, _, given = (authorization or "").partition(" ")
        if not token or scheme.lower() != "bearer" or not hmac.compare_digest(given.encode(), token.encode()):
            raise HTTPException(status_code=401, detail="Invalid sensor token")
        if not (math.isfinite(body.level_cm) and -100 <= body.level_cm <= 1000):
            raise HTTPException(status_code=422, detail="level_cm must be a finite number between -100 and 1000")
        if body.device_id not in repo.sensor_devices():
            raise HTTPException(status_code=422, detail=f"Unknown sensor {body.device_id}")
        newly = []
        with transaction() as conn:
            candidates = [] if body.simulated else sensor_candidates(conn, body.device_id)
            before = repo.outcomes_for(conn, candidates)
            try:
                with conn.begin_nested():
                    repo.insert_sensor_reading(conn, body.device_id, now_myt(), body.level_cm, body.simulated)
            except IntegrityError:
                raise HTTPException(status_code=409, detail="This sensor already reported at this time") from None
            # simulated readings never touch live alerts (they could not be labelled) and never push
            after = repo.outcomes_for(conn, candidates)
            newly = [{**a, "outcome": "confirmed", "push": repo.push_eligible(conn, a["alert_id"])} for a in candidates
                     if before[a["alert_id"]] != "confirmed" and after[a["alert_id"]] == "confirmed"]
        for a in newly:
            fire(a)
        return Response(status_code=204)
