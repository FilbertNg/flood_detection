import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { api, REPLAY_EVENT } from '../lib/api';
import { hhmm } from '../lib/chart';
import { dateLabel } from '../lib/format';

/**
 * Small live / replay chip (from GET /status): floats on the ops map, sits inline on the street page.
 * A replay names the flood it replays; its clock is shown only on the flood's day, so a replay never
 * shows today's date as if it were the flood (as in the resident app).
 */
export function ModeChip() {
  const { data: status } = useQuery({ queryKey: ['status'], queryFn: api.status, refetchInterval: 10_000 });
  if (!status) return null;
  if (status.mode === 'replay') {
    const event = status.replay?.event ?? status.data_time.slice(0, 10);
    const onDay = status.data_time.slice(0, 10) === event;
    return (
      <p className="mode-chip replay">
        <span className="mode-tag">Replay</span>
        <span>{`${dateLabel(event)} flood`}</span>
        {onDay && <time dateTime={status.data_time}>{hhmm(status.data_time)}</time>}
      </p>
    );
  }
  return (
    <p className="mode-chip live"><i aria-hidden="true" />Live · {hhmm(status.data_time)}</p>
  );
}

/** Start the verified 12 Nov 2024 replay, or stop it and return to live. */
export function ReplayControl() {
  const client = useQueryClient();
  const { data: status } = useQuery({ queryKey: ['status'], queryFn: api.status, refetchInterval: 10_000 });
  const [confirming, setConfirming] = useState(false);
  const toggle = useMutation({
    mutationFn: () => (status?.mode === 'replay' ? api.stopReplay() : api.startReplay(REPLAY_EVENT)),
    onSuccess: () => client.invalidateQueries(),
    onSettled: () => setConfirming(false),
  });
  if (!status) return null;
  const replaying = status.mode === 'replay';
  return (
    <div className="replay-control">
      {confirming ? (
        <div className="confirm">
          <p className="small">
            {replaying
              ? 'Stop the replay? The system returns to live.'
              : 'Start the 12 Nov 2024 replay from 08:30? The first alerts appear within about 15 seconds. Live alerts are paused; everything created is labelled Replay.'}
          </p>
          <button type="button" className="primary" disabled={toggle.isPending} onClick={() => toggle.mutate()}>Confirm</button>
          <button type="button" className="secondary" onClick={() => setConfirming(false)}>Cancel</button>
        </div>
      ) : (
      <button type="button" className={replaying ? 'danger-btn' : 'primary'} disabled={toggle.isPending} onClick={() => setConfirming(true)}>
        {replaying ? 'Stop replay' : 'Start replay: 12 Nov 2024'}
      </button>
      )}
      {replaying && <p className="muted small">Replaying now. Alerts and answers are flagged as replay and excluded from statistics.</p>}
      {toggle.isError && <p role="alert" className="error small">{toggle.error.message}</p>}
    </div>
  );
}
