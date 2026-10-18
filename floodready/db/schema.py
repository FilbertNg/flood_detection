"""Database tables (build plan §4.3, frozen contract). SQLAlchemy 2 Core, portable across SQLite and Postgres.

JSON columns are TEXT holding json.dumps output; datetimes are naive MYT (UTC+8).
"""
from __future__ import annotations

from sqlalchemy import (Boolean, Column, Date, DateTime, Float, Index, Integer, MetaData, String, Table, Text,
                        PrimaryKeyConstraint)

metadata = MetaData()

stations = Table(
    "stations", metadata,
    Column("graph_id", String(32), nullable=False), Column("kind", String(4), nullable=False),
    Column("name", String(200)), Column("district", String(100)), Column("state", String(100)),
    Column("lat", Float), Column("lon", Float),
    Column("wl_alert_m", Float), Column("wl_warning_m", Float), Column("wl_danger_m", Float),
    PrimaryKeyConstraint("graph_id", "kind"),
)

readings = Table(
    "readings", metadata,
    Column("graph_id", String(32), nullable=False), Column("kind", String(4), nullable=False),
    Column("time_local", DateTime, nullable=False),
    Column("rain_15min_mm", Float), Column("wl_m", Float), Column("source", String(32)), Column("fetched_at", DateTime),
    PrimaryKeyConstraint("graph_id", "kind", "time_local"),
)

streets = Table(
    "streets", metadata,
    Column("street_id", String(200), primary_key=True), Column("township_id", String(32), nullable=False, index=True),
    Column("name", String(200)), Column("susceptibility", Integer),
    Column("centroid_lat", Float), Column("centroid_lon", Float), Column("geometry_geojson", Text),
)

street_state = Table(
    "street_state", metadata,
    Column("street_id", String(200), nullable=False), Column("mode", String(16), nullable=False),
    Column("level", String(16), nullable=False), Column("trigger_level", String(16), nullable=False),
    Column("confidence", String(16)), Column("flood_probability", Float),
    Column("fired_by_json", Text), Column("window_start", DateTime), Column("window_end", DateTime),
    Column("reasons_json", Text), Column("data_time", DateTime), Column("updated_at", DateTime),
    PrimaryKeyConstraint("street_id", "mode"),
)

alerts = Table(
    "alerts", metadata,
    Column("alert_id", String(260), primary_key=True),
    Column("street_id", String(200), nullable=False, index=True), Column("township_id", String(32)),
    Column("horizon", String(16), nullable=False), Column("level", String(16), nullable=False),
    Column("kind", String(16), nullable=False), Column("issued_at", DateTime, nullable=False, index=True),
    Column("window_start", DateTime), Column("window_end", DateTime),
    Column("fired_by_json", Text), Column("reasons_json", Text), Column("inputs_json", Text),
    Column("recipients", Integer, nullable=False, default=0),
    Column("is_replay", Boolean, nullable=False, default=False),
    Column("is_backfill", Boolean, nullable=False, default=False),
    Index("ix_alerts_street_issued", "street_id", "issued_at"),
    Index("ix_alerts_mode_issued", "is_backfill", "is_replay", "issued_at"),
)

answers = Table(
    "answers", metadata,
    Column("answer_id", String(40), primary_key=True),
    Column("device_id", String(64), nullable=False, index=True), Column("alert_id", String(260), index=True),
    Column("street_id", String(200), nullable=False, index=True),
    Column("answer", String(16), nullable=False), Column("depth", String(16)), Column("photo_path", String(500)),
    Column("lat3", Float), Column("lon3", Float), Column("distance_m", Float),
    Column("answered_at", DateTime, nullable=False),
    Column("review_status", String(16), nullable=False, default="pending"),
    Column("source", String(16), nullable=False, default="resident"),
    # one answer per device per alert; NULL alert_id (free reports) never collides
    Index("uq_answers_device_alert", "device_id", "alert_id", unique=True),
)

subscriptions = Table(
    "subscriptions", metadata,
    Column("device_id", String(64), primary_key=True), Column("endpoint", Text, nullable=False),
    Column("p256dh", Text, nullable=False), Column("auth", Text, nullable=False),
    Column("lang", String(4), nullable=False, default="en"), Column("created_at", DateTime),
)

subscription_streets = Table(
    "subscription_streets", metadata,
    Column("device_id", String(64), nullable=False), Column("street_id", String(200), nullable=False, index=True),
    PrimaryKeyConstraint("device_id", "street_id"),
)

sensor_readings = Table(
    "sensor_readings", metadata,
    Column("device_id", String(64), nullable=False), Column("time_local", DateTime, nullable=False),
    Column("level_cm", Float, nullable=False), Column("simulated", Boolean, nullable=False, default=False),
    PrimaryKeyConstraint("device_id", "time_local"),
)

suggestions = Table(
    "suggestions", metadata,
    Column("id", String(40), primary_key=True), Column("street_id", String(200)),
    Column("rule", String(16), nullable=False), Column("priority", String(16), nullable=False),
    Column("text", Text, nullable=False), Column("evidence_json", Text),
    Column("status", String(16), nullable=False, default="open"), Column("note", Text),
    Column("period_from", Date), Column("period_to", Date), Column("created_at", DateTime),
)

ops_notes = Table(
    "ops_notes", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True), Column("street_id", String(200), index=True),
    Column("text", Text, nullable=False), Column("author", String(200)), Column("created_at", DateTime),
)

admin_users = Table(
    "admin_users", metadata,
    Column("email", String(200), primary_key=True), Column("password_hash", String(200), nullable=False),
    Column("role", String(16), nullable=False, default="viewer"),
)
