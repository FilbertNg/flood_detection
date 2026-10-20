# R5: street page as a weather app, plain language first

Branch `feat/resident-street-sky` (stacked on `feat/resident-ui-polish`, whose street-sky checkpoint it builds on). Target look: `docs/design/street-sky-prototype.html`. Frontend only: no API, contract, level or engine changes.

## Order on the page

1. Canvas sky (3-stop gradient per `skyFor()` result, drifting clouds, sparse rain 45 / 90 / 170 drops, rare soft storm flash; still frame for reduced motion; stops on unmount and hidden tab). Warning and Danger keep the still, dark `alert` sky.
2. Hero: street name, level pill with dot, big instruction word (Safe / Be alert / Get ready / Move now), one headline sentence, weather line with a phrase from the hourly rain chance.
3. Three key-point chips: Rain, River, Flood.
4. "What to do now" checklist per level and street (`lib/advice.ts`).
5. Rain curve: Open-Meteo rain chance over `rain_next_12h` hours, Catmull-Rom, gaps break the line.
6. "Right now on your street": plain rows, no metres.
7. "Technical details" (`<details>`, closed): river metres and JPS meter, marks, gauge mm, ML chance and note, tide, reasons, river forecast, data time and sources.
8. Alert history.
9. Last: "Is it flooding here?" (verify sheet during Warning/Danger, report card otherwise).

## Decisions

- Headlines stay within what the system knows: Normal says "no flood warning right now", not a 12-hour promise; Danger says the street "may be flooding" (Danger is the river above its danger mark, not a confirmed flood).
- Skies stay dark enough for white text at >= 4.5:1 on every stop (tested); the prototype's light day sky is not used.
- Relief centres: no official machine-readable BBR list found, so generic "nearest relief centre (PPS)" wording with a TODO. No invented place names.
- Glass and blur are allowed on `.sky-page` only (owner decision, 20 Oct 2026); the rest of the app stays flat.

## Tests (vitest, written first)

`lib/plain.test.ts` (big word, headline, key points, river status, weather phrase), `lib/advice.test.ts` (per level and susceptibility), `lib/curve.test.ts` (points, gaps, path), sky gradient contrast in `lib/weather.test.ts`, `SkyHero.test.tsx`, `StreetTiles.test.tsx`, `Street.test.tsx` (new order, report/verify card last, technical words only inside Technical details).
