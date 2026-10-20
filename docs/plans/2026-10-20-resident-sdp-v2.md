# Resident SDP v2: no bottom bar, red map button, tap-to-expand sky

Branch `feat/resident-sdp-v2`. **Checkpoint before this work: `e8f5848`** (`git checkout e8f5848` returns to the SDP style with the bottom bar). Target: `docs/design/sdp-street-proposal-v2.html`. Frontend only, no new dependency.

## Changes

1. **Bottom bar removed.** Page dots move just under the hero card (`PageDots`, same aria labels; active = short red pill; Warning/Danger dots in the level colour). Swiping is unchanged.
2. **Red floating map button** (`MapFab`, 58 px, `#D71920`, "Flood map and location") on the pager and the single-street view, above the safe area; the page keeps bottom padding so the last card is never covered.
3. **Location card on `/map`.** A red header with "← Back" and "Flood map". A white card floats at the bottom of the map: "My location", a red pin, the current street (last viewed, else the first saved) and its level, "Use my location" (the on-device nearest-street flow) and "Choose another" (the street picker as a bottom sheet). Tapping a street line shows it in the card with "Set as my street" (no saved street yet) or "Add to my streets"; choosing goes to the pager on that street. `/streets` stays for deep links.
4. **Full-screen sky view.** The hero card opens it: a transparent `role="button"` layer over the card (Enter/Space, "Open full weather and flood details", a "Details ›" chip, a slight press effect). Not the card itself, so the street name stays a real heading for screen readers. The view (`SkyView`, a modal dialog): full-screen sky gradient and canvas at full drop count, × top left, level pill top right, name, 96 px word, headline, weather line, three glass chips, the rain-chance curve in the white-on-sky style. Grows from the card in about 350 ms (none with reduced motion). It opens with `?view=sky` (a history entry), so Back closes it; × and Escape close it too, and focus returns to the hero. Warning/Danger keep the still, dark sky. While it is open, the hero canvas pauses.
5. Glass and blur are allowed only in the hero card and the full-screen view (recorded in `styles.css`).

## Tests (written first)

No bottom bar; the FAB links to `/map`; dots render under the hero; the hero opens the full view by click and Enter and closes by ×, Escape and Back, restoring focus; the map's location card shows the current street and both buttons; picking a street on the map and saving it goes to `/street/:id`; "Use my location" fills the card.
