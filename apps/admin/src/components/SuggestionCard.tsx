import { useState } from 'react';
import type { Suggestion, SuggestionStatus } from '@floodready/shared';
import { dateLabel, ensureSuffix } from '../lib/format';

const STATUSES: { value: SuggestionStatus; label: string }[] = [
  { value: 'open', label: 'Open' },
  { value: 'accepted', label: 'Accepted' },
  { value: 'dismissed', label: 'Dismissed' },
  { value: 'done', label: 'Done' },
];

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

/** One suggestion with its evidence and the ops status buttons. */
export function SuggestionCard({ s, busy, onStatus }: { s: Suggestion; busy: boolean; onStatus: (status: SuggestionStatus, note: string) => void }) {
  const [note, setNote] = useState(s.note ?? '');
  return (
    <article className="card suggestion">
      <header className="sug-head">
        <h2>{s.street_name}</h2>
        <span className={`tag prio-${s.priority}`}>{s.priority} priority</span>
        <span className="tag">{s.rule}</span>
      </header>
      <p>{ensureSuffix(s.text)}</p>
      <EvidenceList s={s} />
      <label className="note-field">
        <span className="small">Note (optional)</span>
        <input type="text" value={note} onChange={(e) => setNote(e.target.value)} />
      </label>
      <button type="button" className="secondary fit" disabled={busy} onClick={() => onStatus(s.status, note.trim())}>Save note</button>
      <div className="seg" role="group" aria-label={`Status for ${s.street_name}`}>
        {STATUSES.map((o) => (
          <button key={o.value} type="button" aria-pressed={s.status === o.value} disabled={busy} onClick={() => onStatus(o.value, note.trim())}>
            {o.label}
          </button>
        ))}
      </div>
    </article>
  );
}
