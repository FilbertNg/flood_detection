# WP10 — Resident push permission + install guide (R4)

Source: `docs/plans/2026-10-17-MVP2-remaining-mvp.md` WP10. Contract only (GET /push/public-key, POST /subscriptions, DELETE /subscriptions/{device_id}); no shared-type changes. Tests stub `fetch` and `navigator.serviceWorker`.

## Design

- `push/subscribe.ts`: `pushSupport()` (`ok` | `needs-install` | `unsupported`), `enablePush()`, `syncPush()`, `stopPush()`, `isSubscribed()`, `urlBase64ToUint8Array()`.
- `push/swHandlers.ts`: pure `showPushNotification()` and `focusOrOpen()`, used by `sw.ts` so they are testable without Workbox.
- `push/usePushSync.ts`: re-posts when streets or language change and the device is already subscribed.
- `components/NotificationOffer.tsx`: shown by `PickStreets` after Save. Explains why (EN/MS), Enable / Not now, denied explanation, Stop control, unsupported message, InstallGuide on iPhone Safari outside the installed PWA.
- `components/InstallGuide.tsx`: Add to Home Screen steps, EN/MS.
- `lib/api.ts`: `pushPublicKey`, `subscribe`, `unsubscribe`.

## TDD tasks (each: failing test, watch it fail, implement)

1. subscribe.ts: support detection (iPhone Safari not standalone -> needs-install; no PushManager -> unsupported).
2. enablePush: granted -> subscribe with decoded server key, POST `SubscriptionRequest {device_id, subscription, street_ids, lang}`; denied -> no POST.
3. syncPush re-posts only when subscribed; stopPush calls DELETE and unsubscribes.
4. swHandlers: notification from PushPayload; click focuses an open window or opens `data.url`.
5. NotificationOffer + InstallGuide UI (EN and MS), PickStreets integration, usePushSync in App.
6. Typecheck, full test run, PR.
