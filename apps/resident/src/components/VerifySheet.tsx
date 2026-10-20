import { useEffect, useRef, useState, type ChangeEvent } from 'react';
import type { AnswerKind, Depth, Lang } from '@floodready/shared';
import { AnswerError, postAnswer } from '../lib/api';
import { currentPosition, type Place } from '../lib/geo';
import { t, type StringKey } from '../lib/i18n';

const ANSWERS: { kind: AnswerKind; label: StringKey }[] = [
  { kind: 'yes', label: 'ansYes' },
  { kind: 'no', label: 'ansNo' },
  { kind: 'not_sure', label: 'ansNotSure' },
];
const DEPTHS: { kind: Depth; label: StringKey }[] = [
  { kind: 'ankle', label: 'depthAnkle' },
  { kind: 'knee', label: 'depthKnee' },
  { kind: 'above_knee', label: 'depthAboveKnee' },
];

interface Props {
  lang: Lang;
  deviceId: string;
  streetId: string;
  /** verify: answer an active alert. report: a flood with no alert (answer=report, no alert_id). */
  mode: 'verify' | 'report';
  alertId?: string;
}

const MAX_PHOTO_BYTES = 10 * 1024 * 1024;

type Status = 'form' | 'sending' | 'done';
type ErrorKey = 'alreadyAnswered' | 'sendFailed' | 'locationDenied' | 'photoType' | 'photoTooBig';

/** "Is it flooding here?" sheet (RES-4) and the "Report a flood" form (RES-5). */
export function VerifySheet({ lang, deviceId, streetId, mode, alertId }: Props) {
  const report = mode === 'report';
  const [answer, setAnswer] = useState<AnswerKind | null>(null);
  const [depth, setDepth] = useState<Depth | null>(null);
  const [photo, setPhoto] = useState<{ file: File; url: string } | null>(null);
  const [fileKey, setFileKey] = useState(0);
  const [share, setShare] = useState(false);
  const [place, setPlace] = useState<Place | null>(null);
  const [status, setStatus] = useState<Status>('form');
  const [error, setError] = useState<ErrorKey | null>(null);
  const thanks = useRef<HTMLHeadingElement>(null);
  const photoUrl = useRef<string | null>(null);
  const locating = useRef<Promise<Place | null> | null>(null);

  const kind: AnswerKind | null = report ? 'report' : answer;
  const showDetails = report || answer === 'yes';

  function dropPhotoUrl() {
    if (photoUrl.current) URL.revokeObjectURL(photoUrl.current);
    photoUrl.current = null;
  }
  useEffect(() => dropPhotoUrl, []);
  useEffect(() => {
    if (status === 'done') thanks.current?.focus();
  }, [status]);

  function pick(file: File | undefined) {
    dropPhotoUrl();
    setError(null);
    if (!file) {
      setPhoto(null);
      return;
    }
    if (!file.type.startsWith('image/') || file.size > MAX_PHOTO_BYTES) {
      setPhoto(null);
      setFileKey((k) => k + 1);
      setError(file.type.startsWith('image/') ? 'photoTooBig' : 'photoType');
      return;
    }
    const url = URL.createObjectURL(file);
    photoUrl.current = url;
    setPhoto({ file, url });
  }
  function removePhoto() {
    dropPhotoUrl();
    setPhoto(null);
    setFileKey((k) => k + 1);
  }
  function choose(next: AnswerKind) {
    setAnswer(next);
    setError(null);
    if (next !== 'yes') {
      setDepth(null);
      removePhoto();
    }
  }

  async function toggleShare(event: ChangeEvent<HTMLInputElement>) {
    if (!event.target.checked) {
      setShare(false);
      setPlace(null);
      locating.current = null;
      return;
    }
    setShare(true);
    setError(null);
    const lookup = currentPosition().then(
      (found) => {
        setPlace(found);
        return found;
      },
      () => {
        setShare(false);
        setPlace(null);
        setError('locationDenied');
        return null;
      },
    );
    locating.current = lookup;
    await lookup;
  }

  async function send() {
    if (!kind || status === 'sending') return;
    setStatus('sending');
    setError(null);
    try {
      // A quick tap on Send must still wait for the position the resident agreed to share.
      const where = share ? (place ?? (await locating.current)) : null;
      await postAnswer({
        device_id: deviceId,
        street_id: streetId,
        answer: kind,
        ...(!report && alertId ? { alert_id: alertId } : {}),
        ...(showDetails && depth ? { depth } : {}),
        ...(showDetails && photo ? { photo: photo.file } : {}),
        ...(where ? { lat: where.lat, lon: where.lon } : {}),
      });
      removePhoto();
      setStatus('done');
    } catch (e) {
      setError(e instanceof AnswerError && e.status === 409 ? 'alreadyAnswered' : 'sendFailed');
      setStatus('form');
    }
  }

  if (status === 'done') {
    return (
      <section className="card sheet" aria-labelledby="sheet-thanks">
        <h2 id="sheet-thanks" ref={thanks} tabIndex={-1}>{t(lang, 'thanks')}</h2>
        <p>{t(lang, 'thanksBody')}</p>
      </section>
    );
  }

  return (
    <section className="card sheet" aria-labelledby="sheet-title">
      <h2 id="sheet-title">{t(lang, report ? 'reportTitle' : 'verifyTitle')}</h2>
      <p className="muted small">{t(lang, report ? 'reportIntro' : 'verifyIntro')}</p>

      {!report && (
        <div className="choices" role="group" aria-labelledby="sheet-title">
          {ANSWERS.map((a) => (
            <button key={a.kind} type="button" className="choice" aria-pressed={answer === a.kind} onClick={() => choose(a.kind)}>
              {t(lang, a.label)}
            </button>
          ))}
        </div>
      )}

      {showDetails && (
        <>
          <p className="field-label" id="depth-label">{t(lang, 'depthLabel')}</p>
          <div className="choices" role="group" aria-labelledby="depth-label">
            {DEPTHS.map((d) => (
              <button key={d.kind} type="button" className="choice" aria-pressed={depth === d.kind} onClick={() => setDepth(depth === d.kind ? null : d.kind)}>
                {t(lang, d.label)}
              </button>
            ))}
          </div>

          <label className="field-label" htmlFor="photo-input">{t(lang, 'photoLabel')}</label>
          <input
            key={fileKey}
            id="photo-input"
            className="file-input"
            type="file"
            accept="image/*"
            capture="environment"
            onChange={(e) => pick(e.target.files?.[0])}
          />
          {photo && (
            <div className="photo-preview">
              <img src={photo.url} alt={t(lang, 'photoAlt')} />
              <button type="button" className="secondary" onClick={removePhoto}>{t(lang, 'photoRemove')}</button>
            </div>
          )}
        </>
      )}

      {(report || answer) && (
        <label className="consent">
          <input type="checkbox" checked={share} onChange={toggleShare} />
          <span>{t(lang, 'locationLabel')}</span>
        </label>
      )}

      {error && <p role="alert" className="form-error">{t(lang, error)}</p>}

      <button type="button" className="primary" disabled={!kind || status === 'sending'} onClick={send}>
        {status === 'sending' ? t(lang, 'sending') : t(lang, report ? 'sendReport' : 'sendAnswer')}
      </button>
    </section>
  );
}
