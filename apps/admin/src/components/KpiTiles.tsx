import type { Kpis } from '@floodready/shared';
import { leadMin, pct } from '../lib/format';
import { StatIcon, type StatIconName } from './StatIcons';

interface Tile {
  label: string;
  value: string;
  icon: StatIconName;
  hint?: string;
  /** alert: needs action (red); good / muted colour the icon only. */
  tone?: 'alert' | 'good' | 'slate' | 'ochre';
  /** 0 to 1: drawn as a ring around the value (the confirmation rate). */
  ring?: number;
}

/**
 * Headline figures first (alerts, confirmation rate, lead time, missed floods), then how the alerts
 * ended. Missed floods turn red when there are any: that is the number to act on. Unverified is shown
 * on its own: no answer yet is not a false alarm.
 */
export function KpiTiles({ kpis }: { kpis: Kpis }) {
  const answered = kpis.confirmed + kpis.not_confirmed;
  const hero: Tile[] = [
    { label: 'Alerts', value: String(kpis.alerts), icon: 'bell', hint: 'issued in this period' },
    answered > 0
      ? { label: 'Confirmation rate', value: pct(kpis.confirmation_rate), icon: 'target', hint: 'of answered alerts', ring: kpis.confirmation_rate }
      : { label: 'Confirmation rate', value: 'n/a', icon: 'target', hint: 'no answered alerts yet' },
    { label: 'Median lead time', value: leadMin(kpis.median_lead_min), icon: 'clock', hint: 'from alert to confirmed flood' },
    {
      label: 'Missed floods', value: String(kpis.missed_floods), icon: 'alert', hint: 'floods reported without an alert',
      tone: kpis.missed_floods > 0 ? 'alert' : undefined,
    },
  ];
  const outcomes: Tile[] = [
    { label: 'Confirmed', value: String(kpis.confirmed), icon: 'check', hint: 'flood reported or reported in the news', tone: 'good' },
    { label: 'Not confirmed', value: String(kpis.not_confirmed), icon: 'cross', hint: 'residents said no flood', tone: 'slate' },
    { label: 'Unverified', value: String(kpis.unverified), icon: 'question', hint: 'no answers yet — not a false alarm', tone: 'ochre' },
  ];
  const tile = (t: Tile, size: 'hero' | 'small') => (
    <div key={t.label} className={`kpi kpi-${size}`} data-tone={t.tone}>
      <StatIcon name={t.icon} className="kpi-icon" />
      <span className="kpi-label">{t.label}</span>
      <strong className="kpi-value">{t.value}</strong>
      {t.hint && <small className="muted">{t.hint}</small>}
      {t.ring !== undefined && (
        <svg className="kpi-ring" viewBox="0 0 36 36" aria-hidden="true">
          <circle cx="18" cy="18" r="15" fill="none" stroke="var(--line)" strokeWidth="4" />
          <circle cx="18" cy="18" r="15" fill="none" stroke="#2e7d32" strokeWidth="4" strokeLinecap="round"
            strokeDasharray={`${(Math.max(0, Math.min(1, t.ring)) * 94.25).toFixed(2)} 94.25`} transform="rotate(-90 18 18)" />
        </svg>
      )}
    </div>
  );
  return (
    <section aria-label="Key figures" className="kpis">
      <div className="kpi-row kpi-row-hero">{hero.map((t) => tile(t, 'hero'))}</div>
      <div className="kpi-row kpi-row-small">{outcomes.map((t) => tile(t, 'small'))}</div>
    </section>
  );
}
