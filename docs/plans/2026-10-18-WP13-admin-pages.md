# WP13 Admin statistics, report, suggestions, review: TDD plan

Scope: replace the four "Coming in WP13" placeholders in `apps/admin` with pages that code to the frozen contract (`docs/api-contract.md`, `packages/shared/src/api/types.ts`). The backend (WP8) lands later, so tests stub `fetch`; the UI never imports mocks at runtime. No data from the API means an empty state, never an invented number.

## Decisions

- `confirmation_rate` and `stale_pct` are fractions 0..1 (mock: 0.42, 0.04); shown as percent.
- "Unverified" tile explains: "no answers yet, not a false alarm".
- Fixed notes: "Replay and demo data are excluded." Data-source note: "outcomes from news: N, from residents: M".
- Suggestion text always ends with "Screening suggestion; site survey needed." (appended if the API text lacks it).
- Charts are inline SVG with `role="img"` aria summaries and a table fallback (`<details>`).
- Print: `@media print` hides nav and buttons, `@page { size: A4 }`; "Print / Save as PDF" calls `window.print()`.

## Tasks (each: failing test, implement, green)

1. `lib/api.ts`: `stats(from,to)`, `report(month)`, `suggestions(from,to)`, `updateSuggestion(id,body)` (PATCH), `answers('pending')`, `reviewAnswer(id,body)` (PATCH). Test URL, method, body.
2. `lib/format.ts`: `pct`, `leadMin`, `ensureSuffix`. Unit tests.
3. `KpiTiles`: seven tiles, unverified explanation, median lead "n/a" when null.
4. `ByWeekChart`, `RainAtOnsetChart`: SVG with aria summary and table fallback; empty state.
5. `ByStreetTable`: sortable by column (click header, aria-sort).
6. `StationHealthTable`: stale % sorted high first; >= 50% flagged "mostly offline".
7. `Statistics` page: period filter refetches; sources note; replay note; error and empty states.
8. `Report` page: month picker refetches `/admin/report?month=`; sections; print button calls `window.print`; print CSS.
9. `Suggestions` page: ranked high, medium, low; evidence; status buttons PATCH with optional note; suffix.
10. `Review` page: pending queue, valid/spam PATCH, removed from list; photo thumbnail; demo label.
11. Wire routes in `App.tsx`, delete `Placeholder.tsx`; typecheck, build, `pnpm -r test`.
