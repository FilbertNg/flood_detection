# Admin suggestion card redesign

**Date:** 21 Oct 2026 · **Branch:** `feat/admin-suggestion-card` · **Checkpoint:** `2e52f9b` (`main`, Feat/resident sdp v2 #62; no uncommitted code, so no checkpoint commit was needed. The branch is cut from `main` rather than the unmerged resident branches, so its PR carries only this work)
**Target:** `docs/design/suggestion-card-proposal.html` (one SUG-5 example with sample numbers)

## Goal

`apps/admin/src/components/SuggestionCard.tsx` matches the proposal: header with the street, a priority chip, the rule id and a status chip; the action as the headline with the screening caveat under it; stat tiles from structured evidence; the dates drawn as a month strip; "How this was ranked" folded; the note saved automatically; buttons for the next step only. Frontend only, no API or contract change.

## What the backend sends (`floodready/stats/suggestions.py`)

No suggestions are stored locally yet (the backfill they are built from is not loaded), so there is no live `/admin/suggestions` response to read; the evidence keys below come from the code that builds it.

| Rule | Structured evidence used for tiles / strip |
| --- | --- |
| SUG-5 | `rank`, `eligible_streets`, `episode_dates`, `river_station_name`, `eligible_streets_on_same_river_station` (also `episodes`, `danger_episodes`) |
| SUG-1 | `flood_dates`, `rain_at_onset_mm`, `max_depth` |
| SUG-2, SUG-3 | `flood_dates`, `max_depth` |
| SUG-4 | `flood_dates` (distinct flood days across the cluster), `max_depth` |
| SUG-6 | `flood_dates` (first reports of resident-reported floods with no Warning or Danger before them) |
| SUG-7 | none of the above (station health); no tiles, no strip |

## Decisions

- **Tiles only from structured keys**, each shown only when its value is present and well-typed: rank ("5 of 79", Rank among eligible streets), episodes (`episode_dates.length`, Separate alert episodes), floods (`flood_dates.length`), deepest depth, heaviest rain at onset (the highest mm), river station (wide; "shared by N eligible streets" only when N is sent). Nothing is parsed out of `notes`.
- **Flood tile label follows what the dates are:** "Confirmed floods" (SUG-1..3), "Days with confirmed floods" (SUG-4: the dates are distinct days across several streets, not one street's floods), "Resident-reported floods" (SUG-6: reports, not confirmations). SUG-5 episode dates are never called floods.
- **Headline / caveat:** split `s.text` on the contract suffix "Screening suggestion; site survey needed."; when it is missing, the whole text is the headline and the caveat line still shows.
- **Note:** saved on blur and after 800 ms without typing (PATCH with the current status and the note), only when it differs from the last saved note; a small green "Saved" shows inside the field on success; the page's existing error message on failure.
- **Buttons:** next step only. Open → Accept, Dismiss · Accepted → Mark done, Back to open · Dismissed → Reopen · Done → Reopen. Disabled while a save is pending.
- `EvidenceList` (used by the monthly report) and the `.seg` buttons (used by the review page) are left as they are.

## Tasks (TDD)

1. `lib/suggestion.ts` + tests: `splitText`, `statTiles`, `dateMonths` (one strip per month, list beyond three), `datesInWords`, `NEXT_STEPS`.
2. `components/SuggestionCard.tsx` + `routes/Suggestions.tsx` (save returns a promise so the card can show "Saved"); update `routes/Suggestions.test.tsx`.
3. Styles in `styles.css` (card with 4 px `#df6436` top edge and 20 px radius, chips, tiles, strip, footer, focus outlines; phones: two tile columns, the station tile spanning).
4. Check at 1280 px and 390 px; before/after screenshots; PR into `main` with the checkpoint hash.
