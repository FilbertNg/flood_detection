import type { Level } from '@floodready/shared';

const RANK: Record<Level, number> = { danger: 0, warning: 1, watch: 2, normal: 3 };
/** A saved street the API no longer lists goes after every known level. */
const UNKNOWN = 4;

/** Saved streets for the pager: Danger, Warning, Watch, Normal; the resident's own order within a level. */
export function orderStreets(saved: string[], levels: Partial<Record<string, Level>>): string[] {
  const rank = (id: string) => {
    const level = levels[id];
    return level ? RANK[level] : UNKNOWN;
  };
  // Array.prototype.sort is stable, so ties keep the saved order.
  return [...saved].sort((a, b) => rank(a) - rank(b));
}
