# Resident app in SDP style

Branch `feat/resident-sdp-style`. **Checkpoint before this work: `d8af1ca`** (`git checkout d8af1ca` returns to the dark-sky pager). Target: `docs/design/sdp-street-proposal.html`. Frontend only: no API, contract or `packages/shared` change, no new dependency. Presentation only, except the prone-row wording.

## Step 0

Tests were not green at first: 10 `prefs.test.ts` failures on Node 26 only (Node 26 defines its own global `localStorage`) and a flaky `SwipeHome` URL assertion (1 in 3 runs). Both fixed in `539c19d`; 235/235 then passed in 5 runs on Node 26 and 5 on Node 22. Checkpoint `d8af1ca` adds the proposal.

## Changes

1. Tokens and header comment in `styles.css`: flat SDP style everywhere; one exception, the street hero card (sky gradient and canvas). All glass, blur and the full-screen dark sky removed.
2. App shell: the red header with the `#DF6436` edge on every screen, the pager included (no longer full screen); the grey live line or the replay label under it; the live line stays off `/report` and `/streets` (earlier owner request). White bottom bar with outlined buttons and pill/dot page indicators.
3. Street page: hero card with the sky drawn inside it (about half the drops), "Your street", level pill, name, big word, headline, weather line; grey key tiles; "What to do now" with a level stripe and red check icons; blue rain curve with a red-ringed Now point; hairline rows with the new prone wording; closed Technical details with a red +/–; equal outlined answer buttons last.
4. Other screens (map, picker, report, verify, notifications, history, start screen) on the same white cards, grey inputs and red buttons.

## Decisions

- Sky stops stay dark enough for white text (>= 4.5:1, also with clouds over it); the proposal's light day blue is not used.
- Level colours are shapes only on white: Watch `#B26A00` and Warning `#E65100` fail 4.5:1 as text (4.24 and 3.79 on white) but pass 3:1 for shapes; levels keep their text labels.
- The answer buttons share one class and none is highlighted before a tap; the tapped one shows as selected so the resident sees their choice.

## Tests

Updated for the new markup and drop counts; new: replay label inside the hero, the prone wording, the three answer buttons share one style class.
