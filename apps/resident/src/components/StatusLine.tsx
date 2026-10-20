import { useQuery } from '@tanstack/react-query';
import type { Lang } from '@floodready/shared';
import { api } from '../lib/api';
import { day, dayTime, hhmm } from '../lib/format';
import { t, tf } from '../lib/i18n';

/**
 * The live / replay chip on the flood map: "● Live · 09:15", or "REPLAY · 12 Nov 2024 flood · 09:15".
 * It floats on the map, so it takes no room of its own; the parent places it.
 * The replay clock is left out when it is not on the flood's day, so a replay never shows today's date
 * as if it were the flood.
 */
export function StatusLine({ lang }: { lang: Lang }) {
  const { data } = useQuery({ queryKey: ['status'], queryFn: api.status, refetchInterval: 10_000 });
  // A reply without a data time draws no line rather than breaking the page.
  const status = typeof data?.data_time === 'string' ? data : null;
  if (status?.mode === 'replay') {
    const event = status.replay?.event ?? status.data_time.slice(0, 10);
    const onDay = status.data_time.slice(0, 10) === event;
    return (
      <p className="status-chip replay" aria-label={`${t(lang, 'replay')}: ${day(event)}${onDay ? `, ${hhmm(status.data_time)}` : ''}`}>
        <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true" className="replay-icon">
          <path fill="currentColor" d="M12 3a9 9 0 1 1-8.95 10h2.02A7 7 0 1 0 7.05 7.05L9 9H3V3l2.64 2.64A8.97 8.97 0 0 1 12 3zm-1 5h2v4.6l3.2 1.9-1 1.7L11 13.7z" />
        </svg>
        <span className="replay-tag">{t(lang, 'replayTag')}</span>
        <span className="replay-what">{tf(lang, 'replayFlood', { date: day(event) })}</span>
        {onDay && <time dateTime={status.data_time}>{hhmm(status.data_time)}</time>}
      </p>
    );
  }
  if (status) {
    return (
      <p className="status-chip live" aria-label={`${t(lang, 'live')} · ${t(lang, 'dataTime')} ${dayTime(status.data_time)}`}>
        <i aria-hidden="true" />{t(lang, 'live')} · {hhmm(status.data_time)}
      </p>
    );
  }
  return null;
}
