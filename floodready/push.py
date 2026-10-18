"""Web Push (build plan B2; WP3 interface §3.2).

`payload` builds the exact `PushPayload`; `notify` sends one alert to the subscribers of its street;
`PushService` owns the VAPID keys and sends on a background worker so neither the engine tick nor an API
request waits on a push service.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable

from sqlalchemy import Engine

from .db import repo

log = logging.getLogger(__name__)

GONE = (404, 410)
SEND_TIMEOUT_S = 10
TTL_S = 3600   # a flood alert older than an hour is stale

_TITLE = {
    "en": {"watch": "Flood Watch: {street}", "warning": "Flood Warning: {street}", "danger": "Flood Danger: {street}"},
    "ms": {"watch": "Awasan Banjir: {street}", "warning": "Amaran Banjir: {street}", "danger": "Bahaya Banjir: {street}"},
}
_BODY = {
    "en": {"watch": "Conditions are building near {street}. Stay alert and check the street page.",
           "warning": "Flooding is expected near {street}. Move vehicles and valuables to higher ground.",
           "danger": "Severe flooding is expected near {street}. Avoid the area and follow official instructions."},
    "ms": {"watch": "Keadaan semakin buruk berhampiran {street}. Berwaspada dan semak halaman jalan.",
           "warning": "Banjir dijangka berhampiran {street}. Alihkan kenderaan dan barang berharga ke tempat tinggi.",
           "danger": "Banjir teruk dijangka berhampiran {street}. Elakkan kawasan ini dan ikut arahan rasmi."},
}
_WINDOW = {"en": " Expected {a} to {b}.", "ms": " Dijangka {a} hingga {b}."}


def payload(alert: dict, street_name: str, lang: str) -> dict:
    """PushPayload {title, body, url, alert_id, level}. `alert` is an AlertSummary (optionally with
    `reason_text` {en, ms}); replay alerts get a "[Replay] " title prefix."""
    lang = lang if lang in _TITLE else "en"
    level = alert["level"]
    title = _TITLE[lang].get(level, _TITLE[lang]["watch"]).format(street=street_name)
    if alert.get("is_replay"):
        title = "[Replay] " + title
    body = _BODY[lang].get(level, _BODY[lang]["watch"]).format(street=street_name)
    window = alert.get("window")
    if window and window.get("start") and window.get("end"):
        body += _WINDOW[lang].format(a=window["start"][11:16], b=window["end"][11:16])
    reason = (alert.get("reason_text") or {}).get(lang)
    if reason:
        body += f" ({reason})"
    return {"title": title, "body": body, "url": f"/street/{alert['street_id']}", "alert_id": alert["alert_id"], "level": level}


def _status(exc: Exception) -> int | None:
    return getattr(getattr(exc, "response", None), "status_code", None)


def notify(conn, alert: dict, street_name: str, send: Callable[[dict, str], None]) -> int:
    """Send `alert` to every subscriber of its street, in their language. Returns the number sent.

    Nothing is sent unless `alert["push"]` is true (alert kind and a level in `alerts.push_levels`).
    404/410 from the push service deletes that subscription; any other error is logged and the loop continues.
    `send(subscriber, json_text)` raises on failure."""
    if not alert.get("push") or alert.get("kind", "alert") != "alert":
        return 0
    sent = 0
    for sub in repo.list_subscribers(conn, alert["street_id"]):
        data = json.dumps(payload(alert, street_name, sub["lang"]), ensure_ascii=False)
        try:
            send(sub, data)
            sent += 1
        except Exception as exc:  # noqa: BLE001 - one bad endpoint must never stop the others or the tick
            if _status(exc) in GONE:
                repo.delete_subscription(conn, sub["device_id"])
                log.info("push subscription %s is gone (%s); deleted", sub["device_id"], _status(exc))
            else:
                log.warning("push failed for device %s: %s", sub["device_id"], exc.__class__.__name__)
    return sent


def make_sender(private_key: str, subject: str) -> Callable[[dict, str], None]:
    """pywebpush sender signed with the VAPID key (kept in this closure; never logged)."""
    from pywebpush import webpush

    def send(sub: dict, data: str) -> None:
        webpush(subscription_info={"endpoint": sub["endpoint"], "keys": {"p256dh": sub["p256dh"], "auth": sub["auth"]}},
                data=data, vapid_private_key=private_key, vapid_claims={"sub": subject}, ttl=TTL_S, timeout=SEND_TIMEOUT_S)
    return send


class PushService:
    """VAPID config plus a single background worker. Without keys push is disabled (one warning) and the API still serves."""

    def __init__(self, engine: Engine, send: Callable[[dict, str], None] | None = None, public_key: str | None = None):
        self.engine = engine
        self._futures: list[Future] = []
        self._lock = threading.Lock()
        self._pool: ThreadPoolExecutor | None = None
        if send is not None:                      # injected sender (tests)
            self.public_key, self._send = public_key, send
        else:
            pub, priv, subject = (os.environ.get(k) for k in ("VAPID_PUBLIC_KEY", "VAPID_PRIVATE_KEY", "VAPID_SUBJECT"))
            if pub and priv and subject:
                self.public_key, self._send = pub, make_sender(priv, subject)
            else:
                self.public_key, self._send = None, None
        self._warned = False

    @property
    def enabled(self) -> bool:
        return self._send is not None

    def warn_if_disabled(self) -> None:
        if not self.enabled and not self._warned:
            self._warned = True
            log.warning("push disabled: set VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY and VAPID_SUBJECT (scripts/gen_vapid.py)")

    def enqueue(self, alerts: list[dict], street_names: dict[str, str]) -> None:
        """Queue alerts for sending on the worker thread; returns immediately."""
        if not alerts:
            return
        if not self.enabled:
            self.warn_if_disabled()
            return
        with self._lock:
            if self._pool is None:
                self._pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="push")
            self._futures = [f for f in self._futures if not f.done()]
            self._futures.append(self._pool.submit(self._run, list(alerts), dict(street_names)))

    def _run(self, alerts: list[dict], names: dict[str, str]) -> None:
        for alert in alerts:
            try:
                with self.engine.begin() as conn:
                    notify(conn, alert, names.get(alert["street_id"], alert["street_id"]), self._send)
            except Exception:  # noqa: BLE001
                log.exception("push job failed for %s", alert.get("alert_id"))

    def flush(self, timeout: float | None = 30) -> None:
        """Wait for queued sends (tests, shutdown)."""
        with self._lock:
            futures = list(self._futures)
        for f in futures:
            f.result(timeout=timeout)

    def shutdown(self) -> None:
        if self._pool is not None:
            self._pool.shutdown(wait=False, cancel_futures=True)
