import type { AlertSummary, Lang, Outcome } from '@floodready/shared';
import { dayTime } from '../lib/format';
import { t, type StringKey } from '../lib/i18n';
import { LevelBadge } from './LevelBadge';

const OUTCOME: Record<Outcome, StringKey> = {
  confirmed: 'outConfirmed',
  not_confirmed: 'outNotConfirmed',
  unverified: 'outUnverified',
};

/** Past alerts for one street. Unverified means "no answers yet", never "false alarm". */
export function AlertHistory({ history, lang }: { history: AlertSummary[]; lang: Lang }) {
  const alerts = history.filter((a) => a.kind === 'alert');
  const hasUnverified = alerts.some((a) => a.outcome === 'unverified');
  return (
    <section className="card" aria-labelledby="alert-history">
      <h2 id="alert-history">{t(lang, 'historyTitle')}</h2>
      {alerts.length === 0 ? (
        <p className="muted">{t(lang, 'historyEmpty')}</p>
      ) : (
        <ul className="history">
          {alerts.map((a) => (
            <li key={a.alert_id}>
              <LevelBadge level={a.level} lang={lang} />
              <span className="history-time">{dayTime(a.issued_at)}</span>
              <span className={`outcome outcome-${a.outcome}`}>{t(lang, OUTCOME[a.outcome])}</span>
              {a.is_replay && <span className="tag-replay">{t(lang, 'replayTag')}</span>}
            </li>
          ))}
        </ul>
      )}
      {hasUnverified && <p className="muted small">{t(lang, 'outUnverifiedNote')}</p>}
    </section>
  );
}
