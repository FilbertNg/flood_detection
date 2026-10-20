import { useEffect, useRef, type CSSProperties } from 'react';
import { skyGradient, type Sky } from '../lib/weather';

/** Rain drops per sky: sparse and short, like the prototype. */
const DROPS: Partial<Record<Sky, number>> = { drizzle: 45, rain: 90, storm: 170 };

/** Cloud cover per sky, 0 (none) to 1 (full). */
const CLOUDS: Record<Sky, number> = {
  'clear-day': 0.2, 'clear-night': 0.1, 'partly-day': 0.8, 'partly-night': 0.6, cloudy: 1, fog: 1,
  drizzle: 0.6, rain: 0.5, storm: 0.9, alert: 0, none: 0.4,
};

interface Cloud { x: number; y: number; s: number; v: number; puffs: [number, number, number][] }
interface Drop { x: number; y: number; l: number; v: number; a: number }

/**
 * Weather backdrop behind the street page: a 3-stop gradient plus a canvas of soft drifting clouds
 * and sparse rain. Decoration only (aria-hidden). Reduced motion draws one still frame; the loop stops
 * when the tab is hidden and on unmount. Warning and Danger ("alert") get no canvas: no rain, no motion.
 */
export function SkyBackdrop({ sky }: { sky: Sky }) {
  const [top, mid, bottom] = skyGradient(sky);
  const style = { '--sky-top': top, '--sky-mid': mid, '--sky-bottom': bottom } as CSSProperties;
  return (
    <div className={`sky sky-${sky}`} style={style} aria-hidden="true">
      {sky !== 'alert' && <SkyCanvas key={sky} clouds={CLOUDS[sky]} drops={DROPS[sky] ?? 0} flash={sky === 'storm'} />}
    </div>
  );
}

function SkyCanvas({ clouds: cover, drops: dropCount, flash: storm }: { clouds: number; drops: number; flash: boolean }) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const cv = ref.current;
    let ctx: CanvasRenderingContext2D | null = null;
    try {
      ctx = cv?.getContext('2d') ?? null;
    } catch {
      ctx = null;
    }
    if (!cv || !ctx) return;
    const c2d = ctx;
    const still = typeof window.matchMedia === 'function' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    let W = 0, H = 0, raf = 0, flash = 0;

    const size = () => {
      const r = cv.getBoundingClientRect();
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      W = r.width; H = r.height;
      cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
      c2d.setTransform(dpr, 0, 0, dpr, 0, 0);
    };
    size();

    const makeCloud = (x?: number): Cloud => ({
      x: x ?? Math.random() * W,
      y: 20 + Math.random() * 200,
      s: 0.5 + Math.random() * 0.8,
      v: 0.06 + Math.random() * 0.12,
      puffs: Array.from({ length: 5 + Math.floor(Math.random() * 4) }, () => [Math.random() * 120 - 60, Math.random() * 30 - 15, 30 + Math.random() * 40]),
    });
    const makeDrop = (): Drop => ({ x: Math.random() * (W + 80), y: Math.random() * H, l: 8 + Math.random() * 10, v: 7 + Math.random() * 6, a: 0.12 + Math.random() * 0.25 });
    const clouds = Array.from({ length: Math.round(3 + cover * 6) }, () => makeCloud());
    const drops = Array.from({ length: dropCount }, makeDrop);

    const frame = () => {
      c2d.clearRect(0, 0, W, H);
      for (const c of clouds) {
        if (!still) {
          c.x += c.v;
          if (c.x - 120 * c.s > W) Object.assign(c, makeCloud(-140 * c.s));
        }
        for (const [dx, dy, r] of c.puffs) {
          const x = c.x + dx * c.s, y = c.y + dy * c.s, R = r * c.s;
          const g = c2d.createRadialGradient(x, y, 0, x, y, R);
          g.addColorStop(0, `rgba(255,255,255,${0.22 * cover})`);
          g.addColorStop(1, 'rgba(255,255,255,0)');
          c2d.fillStyle = g;
          c2d.beginPath(); c2d.arc(x, y, R, 0, Math.PI * 2); c2d.fill();
        }
      }
      c2d.lineCap = 'round';
      c2d.lineWidth = 1;
      for (const d of drops) {
        if (!still) {
          d.y += d.v; d.x -= d.v * 0.18;
          if (d.y > H) { d.y = -d.l; d.x = Math.random() * (W + 80); }
        }
        c2d.strokeStyle = `rgba(220,235,255,${d.a})`;
        c2d.beginPath(); c2d.moveTo(d.x, d.y); c2d.lineTo(d.x - d.l * 0.18, d.y + d.l); c2d.stroke();
      }
      // A rare, soft flash that fades over about a second and a half: never a strobe.
      if (storm && !still) {
        if (flash <= 0 && Math.random() < 0.003) flash = 0.18;
        if (flash > 0) { c2d.fillStyle = `rgba(255,255,255,${flash})`; c2d.fillRect(0, 0, W, H); flash -= 0.01; }
      }
      if (!still) raf = requestAnimationFrame(frame);
    };

    const start = () => { cancelAnimationFrame(raf); if (still) frame(); else raf = requestAnimationFrame(frame); };
    const onVisible = () => (document.hidden ? cancelAnimationFrame(raf) : start());
    const onResize = () => { size(); if (still) frame(); };
    document.addEventListener('visibilitychange', onVisible);
    window.addEventListener('resize', onResize);
    start();
    return () => {
      cancelAnimationFrame(raf);
      document.removeEventListener('visibilitychange', onVisible);
      window.removeEventListener('resize', onResize);
    };
  }, [cover, dropCount, storm]);

  return <canvas ref={ref} className="sky-canvas" data-drops={dropCount} data-flash={storm} />;
}
