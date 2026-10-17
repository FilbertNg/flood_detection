/** Page reserved for WP13. No data is shown until the admin API behind it exists. */
export function PlaceholderPage({ title }: { title: string }) {
  return (
    <main className="pad">
      <h1>{title}</h1>
      <p className="muted">Coming in WP13.</p>
    </main>
  );
}
