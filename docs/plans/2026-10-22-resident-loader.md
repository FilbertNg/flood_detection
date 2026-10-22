# Resident logo-fill loader and loading skeletons

**Date:** 22 Oct 2026 · **Branch:** `feat/resident-loader` · **Checkpoint:** `c78d081` (head of `feat/resident-onboarding`; no uncommitted code, so no checkpoint commit was needed. Cut from the onboarding branch because the skeleton must match the picture-tile grid and the splash sits in front of the new onboarding screen, both only there so far)
**Target:** `docs/design/loader-proposal.html`

## Goal

Every plain "Loading…" in the resident app becomes the Flood-Ready loader: water fills the pin logo like a cup. A splash covers the first load, a skeleton holds the street page's layout while its data loads, and small inline loaders sit next to short text elsewhere. Errors and empty states are unchanged. Frontend only.

## Where loading happens today

| Place | Today | New |
| --- | --- | --- |
| First open (App) | nothing waits | splash while the first `/status` request is pending, shown only after 300 ms |
| Street page (`StreetView`) | "Loading…" | skeleton: hero-shaped card with `LogoFill` 64 and "Loading your street…", then the tile grid with grey shimmering placeholders (4 half, 1 full) |
| Flood map (`Home`) | "Loading…" | `LogoFill` 32 + "Loading the flood map…" |
| Report form (`Report`) | "Loading…" | `LogoFill` 32 + "Loading the street list…" |
| Street picker (`PickStreets`) | an empty list while 450 KB of streets load | `LogoFill` 32 + "Loading the street list…" |

## Decisions

- **Splash gate:** the onboarding screen and the street pager render without the street list, so the splash covers the first status request only (it also tells the app whether this is a replay). It never outlasts that request; the status query retries once, so a down API reaches the screens' error messages quickly instead of hanging on the splash.
- **No "Loading…" left:** the generic `loading` string is removed; each place says what is loading. A test reads the resident sources and fails if `t(lang, 'loading')` or a "Loading…" / "Memuatkan…" string comes back.
- **Reduced motion:** no rise and no slide; the water sits at half and the logo pulses gently (1.6 s); no shimmer. The app's global reduced-motion rule (`animation: none !important` on everything) would also stop the pulse, so the pulse rule is more specific and `!important` too.
- `LogoFill` uses `useId` for its clip path, is `aria-hidden`, and the text beside it carries the meaning.

## Tasks (TDD)

1. `components/LogoFill.tsx` + test (unique clip ids, hidden), CSS (rise 2.6 s `cubic-bezier(.45,.05,.35,1)`, slide 1.1 s / 1.7 s, reduced motion) + a test on the reduced-motion rules.
2. Splash in `App.tsx` with a `useDelayed` hook + tests (appears after 300 ms of loading, gone when data arrives, never for fast loads).
3. Street skeleton in `StreetView` + tests (status "Loading your street", replaced by the real page).
4. Inline loaders in `Home`, `Report`, `PickStreets`; remove the `loading` string; source-scan test. EN + BM strings.
5. Check at 393 × 852 with a slow network (EN and BM): splash, skeleton, no jump to the loaded page; screenshots; PR with the checkpoint hash.
