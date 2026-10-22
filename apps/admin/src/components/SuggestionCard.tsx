import { useEffect, useRef, useState } from 'react';
import type { Suggestion, SuggestionStatus } from '@floodready/shared';
import { dateLabel } from '../lib/format';
import { NEXT_STEPS, STATUS_LABEL, dateMonths, datesInWords, splitText, statTiles } from '../lib/suggestion';

export function EvidenceList({ s }: { s: Suggestion }) {
  const e = s.evidence;
  const episodeDates = Array.isArray(e.episode_dates) ? (e.episode_dates as string[]) : [];
  return (
    <ul className="evidence">
      {e.flood_dates && e.flood_dates.length > 0 && <li>Flood dates: {e.flood_dates.map(dateLabel).join(', ')}</li>}
      {episodeDates.length > 0 && <li>Alert episode dates: {episodeDates.map(dateLabel).join(', ')}</li>}
      {typeof e.max_depth === 'string' && <li>Deepest reported: {e.max_depth.replace('_', ' ')}</li>}
      {e.rain_at_onset_mm && e.rain_at_onset_mm.length > 0 && (
        <li>Rain at onset: {e.rain_at_onset_mm.map((v) => `${v.toFixed(1)} mm`).join(', ')}</li>
      )}
      {e.notes && <li><span>{e.notes}</span></li>}
    </ul>
  );
}

/** Save the note this long after typing stops. */
const NOTE_DEBOUNCE_MS = 800;

/** The dates as a month strip (one bar per day, red on a date), or a plain list beyond three months. */
function DateStrip({ label, dates }: { label: string; dates: string[] }) {
  const months = dateMonths(dates);
  if (!months) return <p className="sug-datelist">{label}: {dates.map(dateLabel).join(', ')}</p>;
  return (
    <div className="sug-strip" role="group" aria-label={`${label}: ${datesInWords(dates)}`}>
      {months.map((m, i) => (
        <div key={m.key} className="sug-month">
          <div className="sug-month-h"><span>{i === 0 ? label : ''}</span><b>{m.label}</b></div>
          <div className="sug-days" aria-hidden="true" style={{ gridTemplateColumns: `repeat(${m.days}, minmax(0, 1fr))` }}>
            {Array.from({ length: m.days }, (_, d) => <span key={d} className={m.on.includes(d + 1) ? 'sug-d on' : 'sug-d'} />)}
          </div>
          <div className="sug-ticks" aria-hidden="true" style={{ gridTemplateColumns: `repeat(${m.days}, minmax(0, 1fr))` }}>
            {Array.from({ length: m.days }, (_, d) => {
              const day = d + 1, edge = day === 1 || day === m.days;
              return <span key={d} className={edge ? 'edge' : undefined}>{edge || m.on.includes(day) ? day : ''}</span>;
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

/**
 * One suggestion (docs/design/suggestion-card-proposal.html): the street with its priority, rule and
 * status; the action and the screening caveat; tiles and a date strip from the structured evidence; the
 * method folded away; a note that saves itself; buttons for the next step only.
 */
export function SuggestionCard({ s, busy, onSave, readOnly = false }: {
  s: Suggestion; busy: boolean; onSave: (status: SuggestionStatus, note: string) => Promise<unknown>; readOnly?: boolean;
}) {
  const [note, setNote] = useState(s.note ?? '');
  const [saved, setSaved] = useState(false);
  const current = useRef(note);
  const lastSaved = useRef(s.note ?? '');
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => () => clearTimeout(timer.current), []);

  const { action, caveat } = splitText(s.text);
  const tiles = statTiles(s);
  const episodes = Array.isArray(s.evidence.episode_dates) ? (s.evidence.episode_dates as string[]) : [];
  const floods = s.evidence.flood_dates ?? [];
  // SUG-5 dates are alert episode starts, never floods.
  const strip = episodes.length ? { label: 'Alert episode starts', dates: episodes } : floods.length ? { label: 'Flood dates', dates: floods } : null;

  // The note saves with the current status: after a pause in typing, or when the field is left; only when it changed.
  const saveNote = () => {
    clearTimeout(timer.current);
    const n = current.current.trim();
    if (n === lastSaved.current) return;
    onSave(s.status, n).then(() => { lastSaved.current = n; setSaved(true); }, () => {});
  };
  const move = (to: SuggestionStatus) => {
    clearTimeout(timer.current);
    const n = current.current.trim();
    onSave(to, n).then(() => { lastSaved.current = n; }, () => {});
  };

  return (
    <article className="sug-card" aria-labelledby={`sug-${s.id}`}>
      <header className="sug-top">
        <h2 id={`sug-${s.id}`}>{s.street_name}</h2>
        <span className="sug-prio">{s.priority[0].toUpperCase() + s.priority.slice(1)} priority</span>
        <span className="sug-id">{s.rule}</span>
        <span className="sug-status" data-s={s.status}>{STATUS_LABEL[s.status]}</span>
      </header>
      <p className="sug-action">{action}</p>
      <p className="sug-caveat">{caveat}</p>

      {tiles.length > 0 && (
        <div className="sug-stats">
          {tiles.map((t) => (
            <div key={t.key} className={`sug-stat${t.wide ? ' wide' : ''}`} data-k={t.key}>
              <b>{t.value}{t.of && <small>{t.of}</small>}</b>
              <span>{t.label}</span>
            </div>
          ))}
        </div>
      )}
      {strip && <DateStrip label={strip.label} dates={strip.dates} />}

      {typeof s.evidence.notes === 'string' && s.evidence.notes.trim() && (
        <details className="sug-method">
          <summary>How this was ranked</summary>
          <p>{s.evidence.notes}</p>
        </details>
      )}

      {readOnly ? (
        s.note && <p className="sug-note-text">Note: {s.note}</p>
      ) : (
      <div className="sug-foot">
        <div className="sug-note">
          <label htmlFor={`note-${s.id}`}>Note (optional)</label>
          <input
            id={`note-${s.id}`} type="text" value={note} placeholder="e.g. Survey booked for Monday"
            onChange={(e) => {
              setNote(e.target.value);
              current.current = e.target.value;
              setSaved(false);
              clearTimeout(timer.current);
              timer.current = setTimeout(saveNote, NOTE_DEBOUNCE_MS);
            }}
            onBlur={saveNote}
          />
          {saved && <span className="sug-saved" role="status">Saved</span>}
        </div>
        <div className="sug-btns">
          {NEXT_STEPS[s.status].map((b) => (
            <button key={b.label} type="button" className={`sug-btn ${b.kind}`} disabled={busy} onClick={() => move(b.to)}>{b.label}</button>
          ))}
        </div>
      </div>
      )}
    </article>
  );
}
