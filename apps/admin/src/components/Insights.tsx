import type { Stats } from '@floodready/shared';
import { StatIcon, type StatIconName } from './StatIcons';

interface Insight {
  text: string;
  icon: StatIconName;
  tone: 'alert' | 'warn' | 'info';
}

const plural = (n: number, one: string, many: string) => (n === 1 ? one : many);

/**
 * "Needs attention": plain sentences read straight from the period's statistics (nothing estimated),
 * most serious first: missed floods, mostly offline stations, then the busiest street and week.
 */
export function insightsFor(s: Stats): Insight[] {
  const out: Insight[] = [];
  const missed = s.kpis.missed_floods;
  if (missed > 0) {
    out.push({ icon: 'alert', tone: 'alert', text: `${missed} ${plural(missed, 'flood was', 'floods were')} reported without an alert.` });
  }
  const offline = s.station_health.filter((r) => r.stale_pct >= 0.5).sort((a, b) => b.stale_pct - a.stale_pct);
  if (offline.length > 0) {
    out.push({
      icon: 'gauge', tone: 'warn',
      text: `${offline.length} ${plural(offline.length, 'station was', 'stations were')} offline more than half the time: ${offline.map((r) => r.name).join(', ')}.`,
    });
  }
  const top = [...s.by_street].filter((r) => r.alerts > 0).sort((a, b) => b.alerts - a.alerts)[0];
  if (top) {
    out.push({ icon: 'pin', tone: 'info', text: `Most alerts: ${top.name}, ${top.alerts} ${plural(top.alerts, 'alert', 'alerts')} (${top.confirmed} confirmed).` });
  }
  const week = [...s.by_week].filter((w) => w.alerts > 0).sort((a, b) => b.alerts - a.alerts)[0];
  if (week) {
    out.push({ icon: 'calendar', tone: 'info', text: `Busiest week: ${week.week}, ${week.alerts} ${plural(week.alerts, 'alert', 'alerts')}.` });
  }
  return out;
}

export function Insights({ stats }: { stats: Stats }) {
  const items = insightsFor(stats);
  return (
    <section className="card insights" aria-labelledby="insights-title">
      <h2 id="insights-title">Needs attention</h2>
      {items.length === 0 ? (
        <p className="insights-clear"><StatIcon name="check" />Nothing needs attention in this period.</p>
      ) : (
        <ul>
          {items.map((it) => (
            <li key={it.text} data-tone={it.tone}><StatIcon name={it.icon} />{it.text}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
