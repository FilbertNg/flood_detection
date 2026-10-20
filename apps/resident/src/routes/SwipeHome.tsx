import { useQuery } from '@tanstack/react-query';
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react';
import { useNavigate, useParams } from 'react-router';
import type { Lang, Level } from '@floodready/shared';
import { BottomBar } from '../components/BottomBar';
import { StreetView } from '../components/StreetView';
import { api } from '../lib/api';
import { t } from '../lib/i18n';
import { orderStreets } from '../lib/order';
import { FindStreetPage } from './FindStreet';

const LAST_KEY = 'floodready.lastStreet';

function readLast(): string | null {
  try {
    return sessionStorage.getItem(LAST_KEY);
  } catch {
    return null;
  }
}

function writeLast(id: string) {
  try {
    sessionStorage.setItem(LAST_KEY, id);
  } catch {
    // storage blocked: the pager then opens on the first street next time
  }
}

const reducedMotion = () => typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

interface ShellProps {
  lang: Lang;
  deviceId: string;
  saved: string[];
  onSave: (ids: string[]) => void;
}

/**
 * Layout route for `/` and `/street/:id`, so a swipe can change the URL without remounting the pager.
 * No saved street: the start screen. A street that is not saved: that street alone, with an Add button.
 * Otherwise: the pager over the saved streets.
 */
export function SwipeShell({ lang, deviceId, saved, onSave }: ShellProps) {
  const { id } = useParams();
  if (!id && saved.length === 0) return <FindStreetPage lang={lang} onSave={onSave} />;
  if (id && !saved.includes(id)) {
    return (
      <div className="pager single">
        <StreetView
          id={id}
          lang={lang}
          deviceId={deviceId}
          showBack={false}
          topLeft={<button type="button" className="add-street" onClick={() => onSave([...saved, id])}>{t(lang, 'addStreet')}</button>}
        />
        <BottomBar lang={lang} />
      </div>
    );
  }
  // A new saved list (a street added or removed) starts a fresh pager with a fresh order.
  return <Pager key={saved.join(',')} lang={lang} deviceId={deviceId} saved={saved} openId={id} />;
}

const ALERTING: Level[] = ['danger', 'warning'];

function Pager({ lang, deviceId, saved, openId }: { lang: Lang; deviceId: string; saved: string[]; openId?: string }) {
  const navigate = useNavigate();
  const streets = useQuery({ queryKey: ['streets'], queryFn: () => api.streets(), refetchInterval: 10_000 });
  const props = useMemo(() => new Map((streets.data?.features ?? []).map((f) => [f.properties.street_id, f.properties])), [streets.data]);

  // The order is fixed when the pager opens, so pages never jump under the resident's finger while
  // levels change; it is worked out again the next time the pager opens or the saved list changes.
  const [order, setOrder] = useState<string[] | null>(null);
  const [active, setActive] = useState(0);
  useEffect(() => {
    if (order) return;
    if (!streets.data && !streets.isError) return;
    const levels = Object.fromEntries([...props].map(([id, p]) => [id, p.level]));
    const next = orderStreets(saved, levels);
    const last = readLast();
    let start = 0;
    if (openId && next.includes(openId)) start = next.indexOf(openId);
    else if (!ALERTING.includes(levels[next[0]])) start = last && next.includes(last) ? next.indexOf(last) : 0;
    setOrder(next);
    setActive(start);
  }, [order, streets.data, streets.isError, props, saved, openId]);

  const scroller = useRef<HTMLDivElement>(null);
  const panels = useRef<(HTMLElement | null)[]>([]);

  // Jump (no animation) to the opening page once the panels exist.
  const opened = useRef(false);
  useLayoutEffect(() => {
    const el = scroller.current;
    if (!order || !el || opened.current) return;
    opened.current = true;
    el.scrollLeft = active * el.clientWidth;
  }, [order, active]);

  // The page that is at least 60 % on screen is the active one.
  useEffect(() => {
    const el = scroller.current;
    if (!order || !el || typeof IntersectionObserver === 'undefined') return;
    const io = new IntersectionObserver(
      (entries) => {
        for (const e of entries) {
          if (e.isIntersecting && e.intersectionRatio >= 0.6) setActive(Number((e.target as HTMLElement).dataset.index));
        }
      },
      { root: el, threshold: 0.6 },
    );
    panels.current.forEach((p) => p && io.observe(p));
    return () => io.disconnect();
  }, [order]);

  // Keep the URL on the visible street (replace, so swipes add no history) and remember it for next time.
  useEffect(() => {
    if (!order) return;
    const id = order[active];
    writeLast(id);
    navigate(`/street/${encodeURIComponent(id)}`, { replace: true });
  }, [order, active, navigate]);

  const goTo = useCallback((i: number) => {
    if (!order) return;
    const next = Math.max(0, Math.min(order.length - 1, i));
    const el = scroller.current;
    if (el) {
      const left = next * el.clientWidth;
      if (typeof el.scrollTo === 'function') el.scrollTo({ left, behavior: reducedMotion() ? 'auto' : 'smooth' });
      else el.scrollLeft = left;
    }
    setActive(next);
  }, [order]);

  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'ArrowRight') { e.preventDefault(); goTo(active + 1); }
    if (e.key === 'ArrowLeft') { e.preventDefault(); goTo(active - 1); }
  };

  if (!order) return <p className="pad">{t(lang, 'loading')}</p>;

  const dots = order.map((id) => ({ id, name: props.get(id)?.name ?? id, level: props.get(id)?.level ?? 'normal' }));

  return (
    <div className="pager">
      <div className="pager-track" ref={scroller} tabIndex={0} onKeyDown={onKey} aria-label={t(lang, 'pagerLabel')} aria-roledescription="carousel">
        {order.map((id, i) => (
          <section
            key={id}
            ref={(node) => { panels.current[i] = node; }}
            className="pager-panel"
            data-index={i}
            data-street={id}
            aria-label={dots[i].name}
            aria-hidden={i !== active ? 'true' : undefined}
          >
            {Math.abs(i - active) <= 1 && (
              <StreetView id={id} lang={lang} deviceId={deviceId} active={i === active} showBack={false} />
            )}
          </section>
        ))}
      </div>
      <BottomBar lang={lang} dots={dots} active={active} onDot={goTo} />
    </div>
  );
}
