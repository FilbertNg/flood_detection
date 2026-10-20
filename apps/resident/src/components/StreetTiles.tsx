import type { ReactElement, ReactNode } from 'react';
import type { Lang, Station, StreetDetail, Susceptibility } from '@floodready/shared';
import { hhmm, metres } from '../lib/format';
import { t } from '../lib/i18n';
import { weatherKind, type GaugeRain, type WeatherHour } from '../lib/weather';
import { Icon, WeatherIcon } from './Icons';

/** Rain forecast hour by hour: our API's mm, with Open-Meteo's icon and chance of rain when known. */
export function HourlyStrip({ lang, rain, weather }: { lang: Lang; rain: StreetDetail['rain_next_12h']; weather: WeatherHour[] | null }) {
  if (rain.length === 0) return <p className="tile-empty">{t(lang, 'noForecast')}</p>;
  return (
    <ol className="hourly">
      {rain.map((p) => {
        const w = weather?.find((h) => h.hour === p.time.slice(0, 13));
        return (
          <li key={p.time}>
            <span className="hourly-time">{hhmm(p.time)}</span>
            <span className="hourly-icon">{w ? <WeatherIcon kind={weatherKind(w.code, w.isDay)} /> : null}</span>
            <span className="hourly-chance">{w?.rainChance != null ? `${w.rainChance}%` : ''}</span>
            <span className="hourly-mm">{p.mm} mm</span>
          </li>
        );
      })}
    </ol>
  );
}

function Tile({ icon, title, children }: { icon: Parameters<typeof Icon>[0]['name']; title: string; children: ReactNode }) {
  return (
    <section className="tile tile-sm">
      <h2 className="tile-title"><Icon name={icon} />{title}</h2>
      {children}
    </section>
  );
}

/** Rain measured in the last hour at the wettest JPS gauge for this street. */
export function RainNowTile({ lang, gauge }: { lang: Lang; gauge: GaugeRain | null }) {
  return (
    <Tile icon="drop" title={t(lang, 'rainNow')}>
      {gauge ? (
        <>
          <p className="tile-value">{gauge.mm} mm</p>
          <p className="tile-note">{t(lang, 'inLastHour')} · {gauge.station}</p>
        </>
      ) : (
        <p className="tile-empty">{t(lang, 'noGaugeRain')}</p>
      )}
    </Tile>
  );
}

/** The street's river station: current level and where it sits against the JPS marks. */
export function RiverTile({ lang, stations, ids }: { lang: Lang; stations: unknown; ids: string[] }) {
  const list = Array.isArray(stations) ? (stations as Station[]) : [];
  const river = ids
    .map((id) => list.find((s) => s.graph_id === id))
    .find((s): s is Station => !!s && s.kind === 'wl' && !s.is_stale && typeof s.latest?.wl_m === 'number');
  if (!river) {
    return <Tile icon="river" title={t(lang, 'river')}><p className="tile-empty">{t(lang, 'noRiver')}</p></Tile>;
  }
  const wl = river.latest!.wl_m!;
  const th = river.thresholds;
  let gauge: ReactElement | null = null;
  if (th) {
    // Scale from well below the alert mark to a little above danger, so normal levels still show movement.
    const lo = th.alert - (th.danger - th.alert) * 3;
    const hi = th.danger + (th.danger - th.alert) * 0.75;
    const at = (v: number) => `${Math.min(100, Math.max(0, ((v - lo) / (hi - lo)) * 100))}%`;
    gauge = (
      <div className="river-gauge" aria-hidden="true">
        <span className="river-band band-alert" style={{ left: at(th.alert), width: `calc(${at(th.warning)} - ${at(th.alert)})` }} />
        <span className="river-band band-warning" style={{ left: at(th.warning), width: `calc(${at(th.danger)} - ${at(th.warning)})` }} />
        <span className="river-band band-danger" style={{ left: at(th.danger), right: 0 }} />
        <span className="river-now" style={{ left: at(wl) }} />
      </div>
    );
  }
  return (
    <Tile icon="river" title={t(lang, 'river')}>
      <p className="tile-value">{metres(wl)}</p>
      {gauge}
      <p className="tile-note">{river.name}</p>
      {th && (
        <p className="tile-note">
          {`${t(lang, 'markAlert')} ${th.alert.toFixed(2)} · ${t(lang, 'markWarning')} ${th.warning.toFixed(2)} · ${t(lang, 'markDanger')} ${th.danger.toFixed(2)} m`}
        </p>
      )}
    </Tile>
  );
}

/** Port Klang tide: a small curve with "now" marked, and the next high water after the data time. */
export function TideTile({ lang, tide, dataTime }: { lang: Lang; tide: StreetDetail['tide']; dataTime: string }) {
  if (tide.length < 2) return <Tile icon="tide" title={t(lang, 'tide')}><p className="tile-empty">{t(lang, 'noTide')}</p></Tile>;
  const now = Math.max(0, tide.findIndex((p) => p.time >= dataTime.slice(0, 13)));
  let high = -1;
  for (let i = Math.max(1, now); i < tide.length - 1; i++) {
    if (tide[i].height_m >= tide[i - 1].height_m && tide[i].height_m >= tide[i + 1].height_m) { high = i; break; }
  }
  const w = 140, h = 44;
  const ys = tide.map((p) => p.height_m);
  const lo = Math.min(...ys), span = Math.max(...ys) - lo || 1;
  const x = (i: number) => (i / (tide.length - 1)) * w;
  const y = (v: number) => h - 4 - ((v - lo) / span) * (h - 8);
  const path = tide.map((p, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)},${y(p.height_m).toFixed(1)}`).join(' ');
  return (
    <Tile icon="tide" title={t(lang, 'tide')}>
      <svg viewBox={`0 0 ${w} ${h}`} className="tide-mini" aria-hidden="true">
        <path d={path} fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
        <circle cx={x(now)} cy={y(tide[now].height_m)} r="4.5" fill="#fff" />
      </svg>
      {high >= 0 && <p className="tile-note">{`${t(lang, 'highTide')} ${hhmm(tide[high].time)} · ${tide[high].height_m.toFixed(1)} m`}</p>}
    </Tile>
  );
}

/** Terrain flood-prone rating 1 to 5 as a five-step meter. */
export function ProneTile({ lang, rating }: { lang: Lang; rating: Susceptibility }) {
  return (
    <Tile icon="home" title={t(lang, 'susceptibility')}>
      <p className="tile-value">{`${rating} ${t(lang, 'of5')}`}</p>
      <div className="prone-meter" aria-hidden="true">
        {[1, 2, 3, 4, 5].map((n) => <span key={n} data-on={n <= rating} />)}
      </div>
    </Tile>
  );
}
