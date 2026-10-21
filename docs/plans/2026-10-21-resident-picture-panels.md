# Resident picture panels (street page)

**Date:** 21 Oct 2026 · **Branch:** `feat/resident-picture-panels` · **Checkpoint:** `99cbf52` (chore(resident): checkpoint before picture panels)
**Target:** `docs/design/panels-proposal.html` (sample numbers only; the app uses real data)

## Goal

On the white street page (below the hero card), every reading is drawn as a picture tile: a drop that fills, 12 rain bars, a river gauge pill, a scalloped street badge, a tide wave, a model ring, a clock. The hero card, `SkyHero`, the full-screen `SkyView` and their styles do not change; `SkyView` keeps the current panels and technical details.

## Decisions

- **Tide wave covers the hours the API sends, not 00:00 to 24:00.** `StreetDetail.tide` holds 13 hourly heights from the data hour to +12 h. Drawing a whole day would mean inventing heights (CLAUDE.md: never fabricate data), so the wave spans the real series, with the first, middle and last hour as axis labels. The 6 h / 12 h toggle is dropped: one 12 h picture needs no range switch (the toggle stays in `SkyView`'s tide chart).
- **River pill scale** reuses `riverScale()` (the river meter's scale), so the pill and the marks agree with the rest of the app, and negative river levels (datum below zero) still draw.
- **Model ring colours** (green < 20 %, amber < 50 %, orange above) are display only and use the ring and the % text; the note says alerts follow JPS. The tile is hidden when the probability is null.
- Rain last hour and the model chance move from the technical-details readings into the Rain now and Flood model tiles, so they are not shown twice on the page. JPS marks and the river forecast stay in Technical details as white wide tiles.
- No new dependencies: hand-written SVG. Pictures are `aria-hidden`; tile text carries the value and meaning.

## Tasks (TDD: test first, watch it fail, implement)

1. `lib/tiles.ts` + `lib/tiles.test.ts`: `dropFillTop`, `rainBars`, `heaviestHour`, `pillY` / `pillTicks`, `scallopPath`, `ringDash`, `ringTone`, `proneTone`, `nextHighWater`, `tideWave`, `clockHands`.
2. `components/PanelTiles.tsx` + test: `RainNowTile`, `RainNextTile`, `RiverTile`, `StreetTile`, `TideTile`, `ModelTile`, `UpdatedTile`, `WhyTile`, `TileGrid`.
3. `StreetView.tsx`: page uses the tile grids ("Right now", rain curve card, "Technical details"); `SkyView` keeps `skyPanels` / `skyTech`. Tests: sky view still renders its panels, ids unique.
4. EN + BM strings in `lib/i18n.ts`.
5. Styles: white tiles (22 px radius, 14 px padding) on `#f6f6f6`, water blue `#3b82c4 / #8fbbe3 / #dcebf8`, level tokens for state, SDP red only for now markers; stack value and picture below 360 px; 400 ms fill on first render, none with reduced motion.
6. Check in a 393 × 852 view (Normal live street, 12 Nov 2024 replay), EN and BM; PR into `main` with screenshots and the checkpoint hash.
