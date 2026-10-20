import { useQuery } from '@tanstack/react-query';
import type { Lang } from '@floodready/shared';
import { api } from '../lib/api';
import { dayTime } from '../lib/format';
import { t } from '../lib/i18n';

/**
 * The small line under the red header: "● Live · Data as of …", or the replay label. A replay is
 * always shown (replayed data must be labelled on screen); `live={false}` hides only the live line.
 */
export function StatusLine({ lang, live = true }: { lang: Lang; live?: boolean }) {
  const { data } = useQuery({ queryKey: ['status'], queryFn: api.status, refetchInterval: 10_000 });
  // A reply without a data time draws no line rather than breaking the page.
  const status = typeof data?.data_time === 'string' ? data : null;
  if (status?.mode === 'replay') {
    return <p className="ribbon replay"><span aria-hidden="true">▶ </span>{t(lang, 'replay')}: {dayTime(status.data_time)}</p>;
  }
  if (status && live) {
    return <p className="ribbon live"><i aria-hidden="true" />{t(lang, 'live')} · {t(lang, 'dataTime')} {dayTime(status.data_time)}</p>;
  }
  return null;
}
