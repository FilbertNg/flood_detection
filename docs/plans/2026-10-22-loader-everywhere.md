# Logo-fill loader on every resident and admin page

**Date:** 22 Oct 2026 · **Branch:** `feat/loader-everywhere` · **Base:** `d188988` (head of `feat/resident-onboarding-every-visit`) · Owner request: "the loading, please apply to all resident and admin pages".

## Where

| App | Place | Before | Now |
| --- | --- | --- | --- |
| Resident | Onboarding, "Find my street" | "Finding your street…" | `LogoFill` 32 beside it (the privacy line stays under it) |
| Resident | Change location sheet | "Finding your street…" | `InlineLoading` |
| Admin | Suggestions, Review, Street detail, Operations map, Statistics, Report | "Loading…" | `InlineLoading`: "Loading suggestions…", "Loading the review queue…", "Loading the street…", "Loading the map…", "Loading statistics…", "Loading the report…" |
| Admin | Street detail, a station's readings | "Loading {gid}…" | `InlineLoading`: "Loading readings for {gid}…" |

The splash, the street skeleton and the map / picker / report loaders were done in `feat/resident-loader`. Buttons that show a short busy label while they send (Save, Enable alerts, Confirm) keep it: those are actions, not loading screens.

## Decisions

- **The admin has its own `LogoFill`** (`apps/admin/src/components/LogoFill.tsx`, same drawing, timing and reduced-motion rules). The apps share no React code and `packages/shared` holds only types, mocks and theme tokens, so a shared component would mean adding React to that package; two small copies are simpler for now.
- Admin strings are English only (the admin app is not translated).

## Tests (TDD)

Admin: `LogoFill` (unique clip ids, hidden; the inline status), every admin page shows the loader while its data is pending (`routes/loading.test.tsx`), and a source scan that fails on a plain "Loading…". Resident: the onboarding locating step shows the loader.
