# Resident single-screen onboarding

**Date:** 21 Oct 2026 · **Branch:** `feat/resident-onboarding` · **Checkpoint:** `ed7ea99` (head of `feat/resident-picture-panels`; no uncommitted code, so no checkpoint commit was needed; tests passed there, 327)
**Target:** `docs/design/onboarding-proposal.html`

## Goal

The first-visit screen (`/` with no saved street, `routes/FindStreet.tsx`) becomes one screen that fits the viewport without scrolling: a wavy SDP-red illustration with a faint hint of roads and the white Flood-Ready logo in the top part, and a white card at the bottom with one line and two actions. No app header, no sky, no language switch on this screen. Behaviour stays: "Find my street" runs the use-my-location flow (nearest street on the phone, "Is this your street?", outside-BBR and error messages); "Choose from the list" opens the picker; saving goes to the street pager.

## Decisions

- **Illustration:** `components/OnboardingMap.tsx`, inline SVG, `aria-hidden`, copied from the proposal's `art()`: the diagonal base gradient, four wavy bands, four winding roads (7 px `#6e0004` at 14 % with a dashed `#ffb3a0` centre line at 16 %) and the dotted footpath. The proposal's river, side stream, flood pools and ripples are left out (the brief says roads only). Not real geometry.
- **Logo:** the existing `LogoMark` (white) at 92 px over a soft radial red fade, "Flood-Ready" under it. The logo and name form one `role="img"` labelled "Flood-Ready" for screen readers.
- **Privacy promise** ("Your location stays on this phone.") moves to the locating step: it shows with "Finding your street…" while the phone asks for the location, not on the start screen.
- **Language:** no switch here. On a first visit with no saved preference, the app starts in Malay when the phone's language is Malay (`navigator.language` starting with `ms`), otherwise English; a saved choice always wins. The switch stays on every other screen.
- **Replay:** when the API is in replay mode, a small white chip at the top left says "Replay of a past flood" (the existing string); the screen never says "Live".
- **Header:** `App.tsx` hides the red header only while the onboarding screen is showing (`/` with no saved street).

## Tasks (TDD)

1. `lib/prefs.ts`: phone-language default on first visit (test).
2. `components/OnboardingMap.tsx` + `routes/FindStreet.tsx` + tests: layout, both buttons keep their behaviour, privacy note in the locating step, replay chip, illustration hidden, logo labelled.
3. `App.tsx` + test: no header on the onboarding screen, header everywhere else.
4. EN + BM strings; styles (100dvh, safe-area padding, card with 28 px top corners and a 4 px `#df6436` top edge, 16 px button radius, visible focus outlines).
5. Check at 393 × 852 and 320 × 568 (EN and BM, live and replay): fits without scrolling; before/after screenshots; PR with the checkpoint hash.
