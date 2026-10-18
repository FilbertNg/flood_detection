import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import type { Answer, AnswerReview } from '@floodready/shared';
import { api } from '../lib/api';
import { dayTime } from '../lib/chart';

const KEY = ['answers', 'pending'];

export function ReviewPage() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: KEY, queryFn: () => api.pendingAnswers() });
  const review = useMutation({
    mutationFn: ({ id, body }: { id: string; body: AnswerReview }) => api.reviewAnswer(id, body),
    onSuccess: (done) => qc.setQueryData<Answer[]>(KEY, (old) => old?.filter((a) => a.answer_id !== done.answer_id)),
  });

  return (
    <main className="page">
      <h1>Review queue</h1>
      <p className="muted small">Resident answers and photos waiting for review. Valid reports go into the training labels; spam is ignored.</p>
      {q.isLoading && <p className="muted">Loading…</p>}
      {q.isError && <p role="alert" className="error">Could not load the review queue.</p>}
      {review.isError && <p role="alert" className="error">Could not save the review. Try again.</p>}
      {q.data && q.data.length === 0 && <p className="muted">No answers waiting for review.</p>}
      {q.data?.map((a) => (
        <article key={a.answer_id} className="card review">
          {a.photo_url && <img className="thumb" src={a.photo_url} alt="Photo from resident report" loading="lazy" />}
          <div className="review-body">
            <h2>{a.street_id}</h2>
            <p>
              <span>Answer: {a.answer.replace('_', ' ')}</span>
              {a.depth && <span> · Depth: {a.depth.replace('_', ' ')}</span>}
              {a.distance_m !== null && <span> · {Math.round(a.distance_m)} m from the street</span>}
            </p>
            <p className="muted small">
              {dayTime(a.answered_at)}
              {a.source === 'demo' && <> <span className="tag demo">Demo</span></>}
            </p>
            <div className="seg">
              <button type="button" disabled={review.isPending} onClick={() => review.mutate({ id: a.answer_id, body: { review_status: 'valid' } })}>Valid</button>
              <button type="button" disabled={review.isPending} onClick={() => review.mutate({ id: a.answer_id, body: { review_status: 'spam' } })}>Spam</button>
            </div>
          </div>
        </article>
      ))}
    </main>
  );
}
