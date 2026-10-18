import type { Kpis } from '@floodready/shared';
import { leadMin, pct } from '../lib/format';

/** Headline counts. Unverified is shown on its own: no answer yet is not a false alarm. */
export function KpiTiles({ kpis }: { kpis: Kpis }) {
  const tiles: { label: string; value: string; hint?: string }[] = [
    { label: 'Alerts', value: String(kpis.alerts) },
    { label: 'Confirmed', value: String(kpis.confirmed), hint: 'flood reported or reported in the news' },
    { label: 'Not confirmed', value: String(kpis.not_confirmed), hint: 'residents said no flood' },
    { label: 'Unverified', value: String(kpis.unverified), hint: 'no answers yet — not a false alarm' },
    { label: 'Confirmation rate', value: kpis.alerts > 0 ? pct(kpis.confirmation_rate) : 'n/a' },
    { label: 'Missed floods', value: String(kpis.missed_floods), hint: 'floods reported without an alert' },
    { label: 'Median lead time', value: leadMin(kpis.median_lead_min) },
  ];
  return (
    <section aria-label="Key figures" className="kpis">
      {tiles.map((t) => (
        <div key={t.label} className="kpi">
          <span className="kpi-label">{t.label}</span>
          <strong className="kpi-value">{t.value}</strong>
          {t.hint && <small className="muted">{t.hint}</small>}
        </div>
      ))}
    </section>
  );
}
