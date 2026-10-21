import { useEffect, useRef, type CSSProperties, type ReactNode } from 'react';
import { LEVEL_LABEL, type Lang, type Level, type StreetDetail } from '@floodready/shared';
import { t } from '../lib/i18n';
import { skyGradient, type Sky, type WeatherHour, type WeatherKind } from '../lib/weather';
import { WeatherIcon } from './Icons';
import { SkyBackdrop } from './SkyHero';
import { RainCurve } from './StreetTiles';

export interface SkyViewProps {
  lang: Lang;
  sky: Sky;
  name: string;
  level: Level;
  word: string;
  headline: string;
  kind: WeatherKind | null;
  weatherLine: string | null;
  keys: { rain: string; river: string; flood: string };
  rain: StreetDetail['rain_next_12h'];
  hours: WeatherHour[] | null;
  /** CSS variables from the street view: level colour and word colour. */
  vars: CSSProperties;
  onClose: () => void;
  /** The street page's panels and technical details, shown under the curve on white cards. */
  children?: ReactNode;
}

/**
 * Full-screen sky view, opened from the street hero card: the weather-app look with the condition
 * filling the screen, the canvas at full strength, glass key-point chips and the white-on-sky curve,
 * then everything else the street page shows (panels, tide, technical details) on white cards.
 * A modal dialog: focus moves to × on open; the street view handles ×, Escape and Back.
 */
export function SkyView({ lang, sky, name, level, word, headline, kind, weatherLine, keys, rain, hours, vars, onClose, children }: SkyViewProps) {
  const close = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    close.current?.focus();
  }, []);
  const [top, mid, bottom] = skyGradient(sky);
  const style = { ...vars, '--sky-top': top, '--sky-mid': mid, '--sky-bottom': bottom } as CSSProperties;

  return (
    <section className={`sky-view sky-view-${sky}`} role="dialog" aria-modal="true" aria-label={t(lang, 'skyViewLabel')} style={style}>
      <SkyBackdrop sky={sky} full />
      <div className="sky-view-top">
        <button ref={close} type="button" className="sky-close" aria-label={t(lang, 'close')} onClick={onClose}>×</button>
        <span className="level-pill"><i aria-hidden="true" />{LEVEL_LABEL[lang][level]}</span>
      </div>
      <div className="sky-view-hero">
        <h2>{name}</h2>
        <p className="sky-view-word">{word}</p>
        <p className="sky-view-headline">{headline}</p>
        {kind && weatherLine && (
          <p className="sky-view-weather">
            <WeatherIcon kind={kind} />
            <span>{weatherLine}</span>
          </p>
        )}
      </div>
      <div className="sky-view-chips">
        {([['keyRain', keys.rain], ['keyRiver', keys.river], ['keyFlood', keys.flood]] as const).map(([label, value]) => (
          <div key={label}><b>{t(lang, label)}</b><span>{value}</span></div>
        ))}
      </div>
      <h3 className="sky-view-sec">{t(lang, 'skyRainTitle')}</h3>
      <RainCurve lang={lang} rain={rain} weather={hours} tone="sky" />
      {children && <div className="sky-view-body">{children}</div>}
      <p className="sky-view-note">{t(lang, 'skyNote')}</p>
    </section>
  );
}
