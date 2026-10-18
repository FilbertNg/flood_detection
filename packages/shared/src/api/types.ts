/**
 * API contract types for the Resident and Admin apps (build plan §4.2, docs/api-contract.md).
 * Base path: /api/v1. Times: ISO 8601 with +08:00 (MYT).
 *
 * Contract: changing anything here needs a PR labelled `contract`, approved by one
 * backend and one frontend owner, with the mocks updated (build plan §9).
 */

// ---------- enums ----------

export type Level = 'normal' | 'watch' | 'warning' | 'danger';
export type Lang = 'en' | 'ms';
export type Confidence = 'high' | 'medium' | 'low';
export type FiredBy = 'rule_rain' | 'rule_river' | 'model' | 'outlook';
export type Mode = 'live' | 'replay';
export type Horizon = 'nowcast' | 'outlook';
export type AlertKind = 'alert' | 'all_clear';
export type Outcome = 'confirmed' | 'not_confirmed' | 'unverified';
export type AnswerKind = 'yes' | 'no' | 'not_sure' | 'report';
export type Depth = 'ankle' | 'knee' | 'above_knee';
export type AnswerSource = 'resident' | 'news' | 'demo';
export type ReviewStatus = 'pending' | 'valid' | 'spam';
export type StationKind = 'rf' | 'wl';
export type SuggestionRule = 'SUG-1' | 'SUG-2' | 'SUG-3' | 'SUG-4' | 'SUG-5' | 'SUG-6' | 'SUG-7';
export type Priority = 'high' | 'medium' | 'low';
export type SuggestionStatus = 'open' | 'accepted' | 'dismissed' | 'done';
export type Susceptibility = 1 | 2 | 3 | 4 | 5;

/** ISO 8601 date-time with offset, e.g. "2024-11-12T09:00:00+08:00". */
export type ISODateTime = string;
/** ISO date, e.g. "2024-11-12". */
export type ISODate = string;

// ---------- shared pieces ----------

export interface LocalizedText {
  en: string;
  ms: string;
}

export interface Reason {
  /** rain_1h | rain_2to4h | river_level | ml_probability | tide_high | forecast_rain | met_warning | stale_data | radar_approaching (informational; unit "min" = ETA; never changes the level) */
  code: string;
  value: number;
  /** mm | m | p | h | min */
  unit: string;
  station: string | null;
  text: LocalizedText;
}

export interface TimeWindow {
  start: ISODateTime;
  end: ISODateTime;
}

// ---------- GET /status ----------

export interface Status {
  mode: Mode;
  now: ISODateTime;
  data_time: ISODateTime;
  replay: { event: ISODate; speed: number } | null;
  sources: { jps_wl_stale: number; jps_rf_stale: number };
}

// ---------- GET /streets (GeoJSON) ----------

export interface StreetProperties {
  street_id: string;
  name: string;
  township_id: string;
  susceptibility: Susceptibility;
  level: Level;
  updated_at: ISODateTime;
}

export type Position = [lon: number, lat: number];

export interface StreetFeature {
  type: 'Feature';
  geometry:
    | { type: 'LineString'; coordinates: Position[] }
    | { type: 'MultiLineString'; coordinates: Position[][] };
  properties: StreetProperties;
}

export interface StreetCollection {
  type: 'FeatureCollection';
  features: StreetFeature[];
}

// ---------- GET /streets/{street_id} ----------

export interface AlertSummary {
  alert_id: string;
  street_id: string;
  horizon: Horizon;
  kind: AlertKind;
  level: Level;
  issued_at: ISODateTime;
  window: TimeWindow | null;
  outcome: Outcome;
  is_replay: boolean;
  /** Whether a notifier should push this alert (alerts.push_levels: watch, warning and danger; never all-clears). */
  push: boolean;
}

export interface RiverForecast {
  graph_id: string;
  /** Station name, e.g. "Sg. Binjai di Pekan Meru". */
  name: string;
  /** Latest observed level (m). */
  wl_now_m: number;
  /** When that level was read; a forecast is only made when it is at most 30 min old. */
  wl_now_time: ISODateTime;
  /** The station's own JPS warning level (m), for reference; null if unknown. */
  warning_m: number | null;
  /** +1 h and +2 h: median and the p10-p90 range (m). wl_m_p10 <= wl_m <= wl_m_p90. */
  points: { time: ISODateTime; wl_m: number; wl_m_p10: number; wl_m_p90: number }[];
}

export interface StreetDetail {
  street_id: string;
  name: string;
  township_id: string;
  susceptibility: Susceptibility;
  level: Level;
  trigger_level: Level;
  confidence: Confidence;
  /** ML trigger probability (0-1); null if the model is unavailable. */
  flood_probability: number | null;
  fired_by: FiredBy[];
  window: TimeWindow | null;
  /** Ranked: most important first. */
  reasons: Reason[];
  data_time: ISODateTime;
  rain_next_12h: { time: ISODateTime; mm: number }[];
  tide: { time: ISODateTime; height_m: number }[];
  /** River-level forecast (improvement #12); null when no model or no current level. */
  river_forecast: RiverForecast | null;
  /** graph_ids of the stations that decide this street (its river station first, then its rain gauges); the township's stations when no mapping is loaded. */
  stations: string[];
  active_alert: { alert_id: string; level: Level; issued_at: ISODateTime } | null;
  history: AlertSummary[];
  is_replay: boolean;
}

// ---------- GET /stations, /stations/{graph_id}/series ----------

export interface Station {
  graph_id: string;
  name: string;
  kind: StationKind;
  lat: number;
  lon: number;
  /** rf stations fill rain_1h_mm, wl stations fill wl_m; the other is null. */
  latest: { time: ISODateTime; rain_1h_mm: number | null; wl_m: number | null } | null;
  thresholds: { alert: number; warning: number; danger: number } | null;
  is_stale: boolean;
}

export interface SeriesPoint {
  time: ISODateTime;
  rain_15min_mm: number | null;
  wl_m: number | null;
}

// ---------- push + subscriptions ----------

export interface PushPublicKey {
  key: string;
}

/** Same shape as the browser's PushSubscription.toJSON(). */
export interface WebPushSubscription {
  endpoint: string;
  expirationTime: number | null;
  keys: { p256dh: string; auth: string };
}

export interface SubscriptionRequest {
  device_id: string;
  subscription: WebPushSubscription;
  street_ids: string[];
  lang: Lang;
}

/** Payload of every Web Push message. */
export interface PushPayload {
  title: string;
  body: string;
  /** Path to open, e.g. "/street/BBR-jalan-makyong". */
  url: string;
  alert_id: string;
  level: Level;
}

// ---------- POST /answers (multipart/form-data) ----------

export interface AnswerForm {
  device_id: string;
  street_id: string;
  alert_id?: string;
  answer: AnswerKind;
  depth?: Depth;
  lat?: number;
  lon?: number;
  photo?: Blob;
}

export interface AnswerCreated {
  answer_id: string;
}

// ---------- POST /sensor/readings ----------

export interface SensorReading {
  device_id: string;
  level_cm: number;
  simulated: boolean;
}

// ---------- admin ----------

export interface LoginRequest {
  email: string;
  password: string;
}

export interface LoginResponse {
  token: string;
}

export interface Kpis {
  alerts: number;
  confirmed: number;
  not_confirmed: number;
  unverified: number;
  confirmation_rate: number;
  missed_floods: number;
  median_lead_min: number | null;
  /** `alerts` counts episodes (alert to all-clear, flapping merged); these are additive extras. */
  alert_rows?: number;
  by_level?: { watch: number; warning: number; danger: number };
  street_days_with_alert?: number;
}

export interface StreetStat {
  street_id: string;
  name: string;
  alerts: number;
  confirmed: number;
  floods: number;
}

export interface StationHealth {
  graph_id: string;
  name: string;
  stale_pct: number;
}

export interface Stats {
  period: { from: ISODate; to: ISODate };
  kpis: Kpis;
  by_week: { week: string; alerts: number; confirmed: number }[];
  by_street: StreetStat[];
  rain_at_onset: { street_id: string; event_date: ISODate; rain_2to4h_mm: number }[];
  station_health: StationHealth[];
  sources: { outcomes_from_news: number; outcomes_from_residents: number };
}

export interface SuggestionEvidence {
  flood_dates?: ISODate[];
  rain_at_onset_mm?: number[];
  notes?: string;
  [key: string]: unknown;
}

export interface Suggestion {
  id: string;
  street_id: string;
  street_name: string;
  rule: SuggestionRule;
  priority: Priority;
  /** Always ends with "Screening suggestion; site survey needed." */
  text: string;
  evidence: SuggestionEvidence;
  status: SuggestionStatus;
  note: string | null;
}

export interface SuggestionUpdate {
  status: SuggestionStatus;
  note?: string;
}

export interface ReportEvent {
  event_id: string;
  date: ISODate;
  place: string;
  street_ids: string[];
  source_type: string;
  source_url: string | null;
}

export interface Report {
  month: string;
  summary: Kpis;
  events: ReportEvent[];
  top_streets: StreetStat[];
  suggestions: Suggestion[];
  data_health: StationHealth[];
}

export interface Answer {
  answer_id: string;
  device_id: string;
  alert_id: string | null;
  street_id: string;
  answer: AnswerKind;
  depth: Depth | null;
  photo_url: string | null;
  lat3: number | null;
  lon3: number | null;
  distance_m: number | null;
  answered_at: ISODateTime;
  review_status: ReviewStatus;
  source: AnswerSource;
}

export interface AnswerReview {
  review_status: Exclude<ReviewStatus, 'pending'>;
}

export interface OpsNoteRequest {
  street_id: string;
  text: string;
}

export interface ReplayRequest {
  event: ISODate;
  speed: number;
}

export interface ApiError {
  detail: string;
}
