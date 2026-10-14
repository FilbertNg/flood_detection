"""MET Malaysia warnings from the data.gov.my Weather API (current warnings only)."""
from __future__ import annotations

from datetime import datetime

WARNING_URL = "https://api.data.gov.my/weather/warning/"


def _dt(text: str | None) -> datetime | None:
    return datetime.fromisoformat(text) if text else None


def flatten_warnings(payload: list[dict]) -> list[dict]:
    rows = []
    for item in payload:
        issue = item.get("warning_issue") or {}
        rows.append({
            "issued": _dt(issue.get("issued")),
            "title_en": issue.get("title_en"),
            "title_bm": issue.get("title_bm"),
            "valid_from": _dt(item.get("valid_from")),
            "valid_to": _dt(item.get("valid_to")),
            "heading_en": item.get("heading_en"),
            "text_en": item.get("text_en"),
            "instruction_en": item.get("instruction_en"),
            "heading_bm": item.get("heading_bm"),
            "text_bm": item.get("text_bm"),
            "instruction_bm": item.get("instruction_bm"),
        })
    return rows
