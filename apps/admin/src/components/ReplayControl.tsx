import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, REPLAY_EVENT } from '../lib/api';
import { dayTime } from '../lib/chart';

/** Ribbon showing live or replay mode (from GET /status). */
export function ModeRibbon() {
  const { data: status } = useQuery({ queryKey: ['status'], queryFn: api.status, refetchInterval: 10_000 });
  if (!status) return null;
  return status.mode === 'replay' ? (
    <div className="ribbon replay">▶ Replay: {dayTime(status.data_time)}. Alerts and answers are flagged as replay and excluded from statistics.</div>
  ) : (
    <div className="ribbon live">● Live · data time {dayTime(status.data_time)}</div>
  );
}

/** Start the verified 12 Nov 2024 replay, or stop it and return to live. */
export function ReplayControl() {
  const client = useQueryClient();
  const { data: status } = useQuery({ queryKey: ['status'], queryFn: api.status, refetchInterval: 10_000 });
  const toggle = useMutation({
    mutationFn: () => (status?.mode === 'replay' ? api.stopReplay() : api.startReplay(REPLAY_EVENT)),
    onSuccess: () => client.invalidateQueries(),
  });
  if (!status) return null;
  const replaying = status.mode === 'replay';
  return (
    <div className="replay-control">
      <button type="button" className={replaying ? 'danger-btn' : 'primary'} disabled={toggle.isPending} onClick={() => toggle.mutate()}>
        {replaying ? 'Stop replay' : 'Start replay: 12 Nov 2024'}
      </button>
      {toggle.isError && <p role="alert" className="error small">{toggle.error.message}</p>}
    </div>
  );
}
