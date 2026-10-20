import type { ReactElement } from 'react';

/**
 * Line icons for the statistics page (24 px grid, 2 px stroke). Decorative: the label next to each
 * icon carries the meaning.
 */
const PATHS = {
  bell: <path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15zM10 20.5a2 2 0 0 0 4 0" />,
  check: <path d="M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18zm-4 9.2 2.8 2.8L16.5 9.5" />,
  cross: <path d="M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18zM9 9l6 6m0-6-6 6" />,
  question: <path d="M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18zM9.6 9.4a2.5 2.5 0 1 1 3.4 2.3c-.6.3-1 .8-1 1.5v.6M12 16.8v.2" />,
  alert: <path d="M12 3.5 21.5 20h-19zM12 10v4.5M12 17v.3" />,
  clock: <path d="M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18zm0 4.5V12l3 2" />,
  target: <path d="M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18zm0 4.5a4.5 4.5 0 1 1 0 9 4.5 4.5 0 0 1 0-9zm0 3.5v2" />,
  drop: <path d="M12 3.5c3.5 4.6 6 8 6 11a6 6 0 0 1-12 0c0-3 2.5-6.4 6-11z" />,
  gauge: <path d="M4 17a8 8 0 1 1 16 0M12 17l3.5-5M8 17h8" />,
  pin: <path d="M12 21s-6.5-6-6.5-11a6.5 6.5 0 0 1 13 0c0 5-6.5 11-6.5 11zm0-8.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z" />,
  calendar: <path d="M4.5 6.5h15v13h-15zM4.5 10.5h15M8.5 4v4M15.5 4v4" />,
  table: <path d="M4 5h16v14H4zM4 10h16M4 14.5h16M10 10v9" />,
  bars: <path d="M5 20V12M10 20V6M15 20v-9M20 20V9M3 20h18" />,
} satisfies Record<string, ReactElement>;

export type StatIconName = keyof typeof PATHS;

export function StatIcon({ name, className = 'stat-icon' }: { name: StatIconName; className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      {PATHS[name]}
    </svg>
  );
}
