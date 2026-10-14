"""Polite HTTP: one shared session, a clear User-Agent, retries with backoff."""
from __future__ import annotations

import time

import requests

USER_AGENT = "FloodReadyTownship/0.1 (SDP University Hackathon 2026; student research; polite polling)"


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT
    return session


def fetch_text(session, url: str, params: dict | None = None, retries: int = 3,
               backoff_s: float = 5.0, timeout: float = 120.0) -> str:
    """GET a URL, retrying on network or HTTP errors (backoff doubles each try)."""
    for attempt in range(1, retries + 1):
        try:
            response = session.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException:
            if attempt == retries:
                raise
            time.sleep(backoff_s * 2 ** (attempt - 1))
    raise AssertionError("unreachable")
