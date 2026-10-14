/**
 * MOCK DATA for UI development (MSW / VITE_USE_MOCKS=1) — one example per endpoint.
 *
 * Station readings below are real 12 Nov 2024 JPS values (Kg. Perepat rain, Sg. Binjai level).
 * Everything else (geometry, probabilities, statistics, answers) is ILLUSTRATIVE.
 * Apps must show a "Mock data" ribbon when using these, and mock screens must never
 * appear in the deck or video (CLAUDE.md: no fabricated data).
 */
import type {
  AlertSummary,
  Answer,
  Report,
  SeriesPoint,
  Station,
  Stats,
  Status,
  StreetCollection,
  StreetDetail,
  Suggestion,
} from '../api/types';

const T = (hhmm: string) => `2024-11-12T${hhmm}:00+08:00`;

export const status: Status = {
  mode: 'replay',
  now: T('09:00'),
  data_time: T('09:00'),
  replay: { event: '2024-11-12', speed: 60 },
  sources: { jps_wl_stale: 3, jps_rf_stale: 9 },
};

// Approximate mock geometry near Bandar Bukit Raja (not the real street shapes).
export const streets: StreetCollection = {
  type: 'FeatureCollection',
  features: [
    {
      type: 'Feature',
      geometry: { type: 'LineString', coordinates: [[101.4236, 3.0893], [101.4251, 3.0899], [101.4266, 3.0905]] },
      properties: { street_id: 'BBR-jalan-makyong', name: 'Jalan Makyong', township_id: 'BBR', susceptibility: 5, level: 'warning', updated_at: T('09:00') },
    },
    {
      type: 'Feature',
      geometry: { type: 'LineString', coordinates: [[101.4040, 3.0822], [101.4065, 3.0830], [101.4090, 3.0838]] },
      properties: { street_id: 'BBR-persiaran-sungai-keramat', name: 'Persiaran Sungai Keramat', township_id: 'BBR', susceptibility: 5, level: 'warning', updated_at: T('09:00') },
    },
    {
      type: 'Feature',
      geometry: { type: 'LineString', coordinates: [[101.4300, 3.0870], [101.4320, 3.0880]] },
      properties: { street_id: 'BBR-persiaran-batu-belah', name: 'Persiaran Batu Belah', township_id: 'BBR', susceptibility: 3, level: 'watch', updated_at: T('09:00') },
    },
    {
      type: 'Feature',
      geometry: { type: 'LineString', coordinates: [[101.4400, 3.0950], [101.4420, 3.0960]] },
      properties: { street_id: 'BBR-jalan-mock-normal', name: 'Jalan Mock (normal)', township_id: 'BBR', susceptibility: 1, level: 'normal', updated_at: T('09:00') },
    },
  ],
};

export const alertSummary: AlertSummary = {
  alert_id: 'a_01',
  street_id: 'BBR-jalan-makyong',
  horizon: 'nowcast',
  kind: 'alert',
  level: 'warning',
  issued_at: T('09:00'),
  window: { start: T('09:30'), end: T('10:30') },
  outcome: 'unverified',
  is_replay: true,
};

export const alerts: AlertSummary[] = [alertSummary];

export const streetDetail: StreetDetail = {
  street_id: 'BBR-jalan-makyong',
  name: 'Jalan Makyong',
  township_id: 'BBR',
  susceptibility: 5,
  level: 'warning',
  trigger_level: 'warning',
  confidence: 'high',
  flood_probability: 0.62,
  fired_by: ['rule_rain', 'model'],
  window: { start: T('09:30'), end: T('10:30') },
  reasons: [
    {
      code: 'rain_1h', value: 61.5, unit: 'mm', station: 'Kg. Perepat, Kapar',
      text: { en: '61.5 mm of rain in 1 h at Kg. Perepat, Kapar', ms: 'Hujan 61.5 mm dalam 1 jam di Kg. Perepat, Kapar' },
    },
    {
      code: 'ml_probability', value: 0.62, unit: 'p', station: 'Sg. Binjai di Pekan Meru',
      text: {
        en: '62% chance the river at Sg. Binjai di Pekan Meru crosses warning level within 2 h',
        ms: '62% kemungkinan paras Sg. Binjai di Pekan Meru melepasi paras amaran dalam 2 jam',
      },
    },
  ],
  data_time: T('09:00'),
  rain_next_12h: [
    { time: T('10:00'), mm: 2.1 },
    { time: T('11:00'), mm: 0.4 },
    { time: T('12:00'), mm: 0.0 },
  ],
  tide: [
    { time: T('10:00'), height_m: 1.9 },
    { time: T('11:00'), height_m: 2.2 },
    { time: T('12:00'), height_m: 2.0 },
  ],
  river_forecast: null,
  stations: ['26558', 'PEKANMERU'],
  active_alert: { alert_id: 'a_01', level: 'warning', issued_at: T('09:00') },
  history: [alertSummary],
  is_replay: true,
};

export const stations: Station[] = [
  {
    graph_id: '26558', name: 'Kg. Perepat, Kapar', kind: 'rf', lat: 3.107821, lon: 101.355571,
    latest: { time: T('09:00'), rain_1h_mm: 61.5, wl_m: null }, thresholds: null, is_stale: false,
  },
  {
    graph_id: 'PEKANMERU', name: 'Sg. Binjai di Pekan Meru', kind: 'wl', lat: 3.136456, lon: 101.438946,
    latest: { time: T('09:00'), rain_1h_mm: null, wl_m: 3.52 }, thresholds: { alert: 3.8, warning: 4.0, danger: 4.2 }, is_stale: false,
  },
];

// Real JPS readings, 12 Nov 2024 (station coordinates from the JPS station list).
export const rainSeries26558: SeriesPoint[] = [
  { time: T('08:15'), rain_15min_mm: 0, wl_m: null },
  { time: T('08:30'), rain_15min_mm: 14, wl_m: null },
  { time: T('08:45'), rain_15min_mm: 31, wl_m: null },
  { time: T('09:00'), rain_15min_mm: 16.5, wl_m: null },
  { time: T('09:15'), rain_15min_mm: 6, wl_m: null },
  { time: T('09:30'), rain_15min_mm: 0, wl_m: null },
  { time: T('09:45'), rain_15min_mm: 11, wl_m: null },
];

export const levelSeriesPekanMeru: SeriesPoint[] = [
  { time: T('08:00'), rain_15min_mm: null, wl_m: 2.94 },
  { time: T('08:30'), rain_15min_mm: null, wl_m: 3.26 },
  { time: T('09:00'), rain_15min_mm: null, wl_m: 3.52 },
  { time: T('09:15'), rain_15min_mm: null, wl_m: 3.81 },
  { time: T('09:30'), rain_15min_mm: null, wl_m: 4.06 },
  { time: T('09:45'), rain_15min_mm: null, wl_m: 4.16 },
  { time: T('10:00'), rain_15min_mm: null, wl_m: 4.21 },
];

export const suggestions: Suggestion[] = [
  {
    id: 's_01', street_id: 'BBR-persiaran-sungai-keramat', street_name: 'Persiaran Sungai Keramat', rule: 'SUG-2', priority: 'high',
    text: 'Check outfall flap gates / backflow valves draining Persiaran Sungai Keramat: floods coincide with high tide. Screening suggestion; site survey needed.',
    evidence: { flood_dates: ['2024-11-12'], notes: 'MOCK evidence' },
    status: 'open', note: null,
  },
];

export const stats: Stats = {
  period: { from: '2024-01-01', to: '2026-10-14' },
  kpis: { alerts: 12, confirmed: 5, not_confirmed: 1, unverified: 6, confirmation_rate: 0.42, missed_floods: 2, median_lead_min: 55 },
  by_week: [
    { week: '2024-W45', alerts: 1, confirmed: 0 },
    { week: '2024-W46', alerts: 3, confirmed: 2 },
  ],
  by_street: [{ street_id: 'BBR-jalan-makyong', name: 'Jalan Makyong', alerts: 4, confirmed: 2, floods: 3 }],
  rain_at_onset: [{ street_id: 'BBR-jalan-makyong', event_date: '2024-11-12', rain_2to4h_mm: 61.5 }],
  station_health: [{ graph_id: '26558', name: 'Kg. Perepat, Kapar', stale_pct: 0.04 }],
  sources: { outcomes_from_news: 5, outcomes_from_residents: 0 },
};

export const report: Report = {
  month: '2024-11',
  summary: stats.kpis,
  events: [
    {
      event_id: 'BBR-2024-11-12-01', date: '2024-11-12', place: 'Persiaran Sungai Keramat, Klang',
      street_ids: ['BBR-persiaran-sungai-keramat'], source_type: 'news',
      source_url: 'https://berita.rtm.gov.my/nasional/senarai-berita-nasional/senarai-artikel/banjir-kilat-tujuh-laluan-di-klang-dinaiki-air/',
    },
  ],
  top_streets: stats.by_street,
  suggestions,
  data_health: stats.station_health,
};

export const pendingAnswers: Answer[] = [
  {
    answer_id: 'ans_01', device_id: 'dev_mock', alert_id: 'a_01', street_id: 'BBR-jalan-makyong', answer: 'yes', depth: 'knee',
    photo_url: null, lat3: 3.09, lon3: 101.425, distance_m: 40, answered_at: T('09:40'), review_status: 'pending', source: 'demo',
  },
];
