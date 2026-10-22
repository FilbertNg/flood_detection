import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { Priority, Suggestion } from '@floodready/shared';
import { SuggestionCard } from '../components/SuggestionCard';
import { api } from '../lib/api';
import { todayIso } from '../lib/format';
import { PageLoading } from '../components/LogoFill';

const RANK: Record<Priority, number> = { high: 0, medium: 1, low: 2 };
const FROM = '2024-01-01';

export function SuggestionsPage() {
  const qc = useQueryClient();
  const to = todayIso();
  const key = ['suggestions', FROM, to];
  const q = useQuery({ queryKey: key, queryFn: () => api.suggestions(FROM, to) });
  const save = useMutation({
    mutationFn: ({ id, status, note }: { id: string; status: Suggestion['status']; note: string }) =>
      api.updateSuggestion(id, { status, note }),
    onSuccess: (updated) =>
      qc.setQueryData<Suggestion[]>(key, (old) => old?.map((s) => (s.id === updated.id ? updated : s))),
  });

  const ranked = [...(q.data ?? [])].sort((a, b) => RANK[a.priority] - RANK[b.priority]);

  return (
    <main className="page">
      <h1>Improvement suggestions</h1>
      <p className="muted small">Ranked by priority. Each is a screening suggestion built from collected data; none replaces a site survey.</p>
      {q.isLoading && <PageLoading text="Loading suggestions…" />}
      {q.isError && <p role="alert" className="error">Could not load suggestions.</p>}
      {save.isError && <p role="alert" className="error">Could not save the change. Try again.</p>}
      {q.data && ranked.length === 0 && <p className="muted">No suggestions yet. They appear once enough confirmed events or station history exist.</p>}
      {ranked.map((s) => (
        <SuggestionCard key={s.id} s={s} busy={save.isPending} onSave={(status, note) => save.mutateAsync({ id: s.id, status, note })} />
      ))}
    </main>
  );
}
