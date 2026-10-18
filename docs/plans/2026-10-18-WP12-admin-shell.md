# WP12 plan: Admin app shell, login, ops map, street detail

Source: `docs/plans/2026-10-17-MVP2-remaining-mvp.md` WP12 (A1, A2). English only. No contract changes: reuses `@floodready/shared` types and the existing endpoints.

## Design

- `apps/admin` copies the resident tooling (Vite, Vitest, React 19, react-router 7, react-query, react-leaflet), minus the PWA.
- `src/auth.ts`: token held in memory and mirrored to `sessionStorage`; `subscribe` for React; `logout()` clears both.
- `src/lib/api.ts`: fetch wrapper adding `Authorization: Bearer`; any 401 calls `logout()`, so the App renders Login.
- `src/lib/chart.ts`: pure helpers (linear scale, rolling 1 h rain sum, time shift in MYT) so the SVG chart is testable.
- `StationChart.tsx`: inline SVG, no chart library. Rain: 15-min bars plus a rolling 1 h total with the JPS intensity lines (31 mm/h heavy, 60 mm/h very heavy, from `config/rules.yaml`). River: level line with the station's alert / warning / danger lines from `Station.thresholds`.
- Routes: `Login`, `OpsMap` (streets by level, stations with stale ones greyed, legend, credits + Sources, replay controls), `StreetDetail`, placeholders (Statistics, Reports, Suggestions, Review: "Coming in WP13").
- Replay control: `POST /admin/replay {event: 2024-11-12, speed: 60}`, `DELETE /admin/replay`; ribbon when `GET /status` has mode `replay`.

## Tasks (each: failing test first, then code)

1. auth: login stores token in memory + sessionStorage; restores from sessionStorage; logout clears both.
2. api: sends bearer; 401 logs out; other errors throw.
3. chart helpers: scale, rolling sum, time shift.
4. StationChart: rain bars and threshold lines; river line and three threshold lines; empty series message.
5. Login page: submit calls `/admin/login`; wrong password shows the API message.
6. App shell: logged out shows Login; logged in shows nav Map / Statistics / Reports / Suggestions / Review; a 401 returns to Login; placeholders say "Coming in WP13".
7. OpsMap: legend, credits + Sources, level counts, stale stations marked, replay start/stop calls, replay ribbon.
8. StreetDetail: level, reasons, window, river forecast; fetches `/stations/{id}/series` for the street's stations only; one chart per station.
9. Wiring: root `dev:admin`; CI web job runs the admin typecheck, test and build.

Verification: `pnpm -C apps/admin test`, `typecheck`, `pnpm -r test`, browser screenshots.
