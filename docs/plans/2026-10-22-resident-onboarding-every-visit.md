# Resident onboarding on every visit

**Date:** 22 Oct 2026 · **Branch:** `feat/resident-onboarding-every-visit` · **Base:** `0a86e2b` (head of `feat/resident-loader`) · Owner request: "when the user arrives at the website, it goes through the onboarding page first, then the home page".

## Behaviour

- `/` opens on the onboarding screen once per visit, also for a resident who already saved a street; after it, the home page (their street) for the rest of the visit. A visit is the browser tab or the reopened PWA: the flag lives in `sessionStorage` (`lib/visit.ts`), so a reload in the same visit goes straight home and a new tab shows onboarding again.
- **New resident** (no street saved): the card is unchanged (Find my street / Choose from the list); saving a street (here or in the picker) ends the onboarding for the visit.
- **Returning resident:** the card's primary button is "Open {street}" (BM "Buka {street}"; "Open my street" until the street list has loaded) and the link is "Choose another street" (the picker).
- **Street links open directly:** `/street/:id` (a push notification, a share) never waits behind the onboarding screen, so an alert is one tap away.
- The header is hidden whenever the onboarding screen shows (`App.tsx`).

## Tests (TDD)

`StreetHome.test.tsx`: onboarding first with a street saved and "Open {street}" ends it; a street link opens directly. `App.test.tsx`: onboarding with no header, Open goes home, the same visit opens home directly, a new visit shows onboarding again.
