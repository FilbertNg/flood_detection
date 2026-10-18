# WP11 — Resident verify, report, alert history (R5, RES-4/5/6)

Source: `docs/plans/2026-10-17-MVP2-remaining-mvp.md` WP11. Contract only (`POST /answers` multipart, `StreetDetail.active_alert/history`); no shared-type changes. WP4 (backend) is built in parallel, so tests stub `fetch`.

## Design

- `lib/api.ts`: `postAnswer(form: AnswerForm)` builds `FormData` (device_id, street_id, alert_id when present, answer, depth, lat, lon, photo); throws `AnswerError(status)` on non-2xx.
- `lib/geo.ts`: `round3()`, `currentPosition()` (consent-gated by the caller); coordinates are rounded to 3 decimals client-side.
- `components/VerifySheet.tsx`: `mode="verify"` (Yes / No / Not sure, depth after Yes, optional photo, optional location, alert_id) and `mode="report"` (answer=report, depth, photo, location, no alert_id). 409 shows "You already answered"; success shows a thank-you; the photo object URL is revoked on remove, after upload and on unmount.
- `routes/Report.tsx`: street select (followed streets first, `?street=` preset) plus `VerifySheet mode="report"`.
- `components/AlertHistory.tsx`: alerts with level badge, issued time, outcome badge (unverified = "no answers yet", never "false alarm"), Replay tag.
- `Street.tsx`: verify sheet while `active_alert` is warning/danger, otherwise a "Report a flood" link; alert history from `history`. `Home.tsx`: report link when no followed street has an alert. `App.tsx`: `/report` route, `deviceId` to StreetPage.

## TDD tasks (failing test first each time)

1. `postAnswer` multipart fields, 409 gives AnswerError.
2. VerifySheet verify: Yes + depth + photo + rounded location posted; No / Not sure send no depth; 409 message EN/MS with role=alert; thank-you with focus; object URL revoked.
3. VerifySheet report mode omits alert_id and has no Yes/No.
4. AlertHistory badges, unverified explanation, Replay tag, empty state.
5. Street integration (sheet only while Warning/Danger alert; report link otherwise), Report route, Home link.
