# WP6 news labels (L1): draft run, 17 Oct 2026

Draft of `data/events/events.csv`. **Every row is `status = draft` with `checked_by` empty; a human must open each URL, confirm the quote, date and place, then set `checked_by` and `status = checked`.** `evaluate_events.py` (L2) is not built yet.

## Schema

Training-data-spec Dataset 1 columns, plus three additions the spec lacks:

- `event_date`: ISO date (`YYYY-MM` when `date_precision = month`). The spec only has the date inside `event_id`.
- `street_ids`: matched `assets/geo/bbr_streets.geojson` ids, `;`-separated. Filled only when the article names the street; empty otherwise.
- `status`: `draft` or `checked`. Draft rows must leave `checked_by` empty; checked rows must fill it.

`lat` / `lon` are empty (geocoding is a later step). `evidence_quote` holds one to three verbatim fragments joined by ` [...] `, at most 300 characters. Each fragment was machine-checked against the fetched page text when the file was built. Numeric fields come from the same article; values converted from feet (2 ft = 0.6 m, 3 ft = 0.91 m) are marked here so the checker can review them.

## Search queries used

Malay and English web searches, then each cited URL fetched and the quote copied from the page text:

- `banjir kilat Bandar Bukit Raja Klang`; `flash flood Bandar Bukit Raja Klang 2025`; `banjir kilat Klang Meru Kapar Setia Alam 2026`
- `Bukit Raja Klang banjir Persiaran Sungai Keramat Jalan Makyong dinaiki air 2025`; `Bandar Bukit Raja banjir 2024 Jun OR Julai ... Jalan Makyong Sumazau`
- `banjir kilat Klang Julai OR Ogos OR September OR Oktober 2024 Bukit Raja Meru Kapar`; `banjir kilat Klang 2025 Meru Kapar Telok Gadong Pandamaran ...`
- `Klang flash flood 2026 January ... August Bukit Raja Meru Kapar Setia Alam`; `Klang banjir air pasang Kapar Meru Bukit Raja Disember 2025 OR Januari 2026 ...`
- `Flash floods hit Klang following heavy downpour 7 Nov 2017 Bandar Bukit Raja ...` (seed source check)

## Coverage (11 rows)

| Event id | Date | Place | Street ids | Source |
| --- | --- | --- | --- | --- |
| BBR-2024-11-12-01 | 2024-11-12 | Persiaran Batu Belah, Persiaran Sungai Keramat, Klang | yes (3 ids) | RTM |
| BBR-2024-11-28-01 | 2024-11-28 | Setia Alam-Meru road, Pekan Meru, Bukit Kapar | none | Utusan |
| BBR-2025-04-11-01 | 2025-04-11 | Jalan Meru, Taman Sri Jaya | none | Kosmo |
| BBR-2026-05-08-01 | 2026-05-08 | Bukit Raja, around Kapar | none | Harian Metro |
| BBR-2026-05-08-02 | 2026-05-08 | Meru, Jalan Haji Manan, Klang Sentral, Setia Alam | none | Utusan |
| KLG-2026-09-30-01 | 2026-09-30 | Taman Rashna, Klang (not BBR) | none | Media Selangor / Bernama |
| USJ-2025-04-23-01 | 2025-04-23 | USJ 23 Badminton Centre (seed, Subang Jaya) | none | The Vibes |
| BBR-2024-05-memorandum | 2024-05 | Jalan Makyong, Jalan Sumazau, Persiaran Sungai Keramat, Persiaran Batu Belah (seed, chronic hotspot) | yes | Sinar Harian |
| BBR-2023-06-04-01 | 2023-06-04 | Bandar Baru Bukit Raja, Mutiara Bukit Raja, Pekan Meru (seed) | none | Sinar Harian / Bernama |
| BBR-2021-12-17-01 | 2021-12-17 | Setia Alam, Bukit Raja, Meru (seed, river flood) | none | The Star |
| BBR-2017-11-07-01 | 2017-11-07 | Bandar Bukit Raja, Taman Rasah (seed) | none | NST |

All six spec seed incidents are present. The spec's 2021 seed cites a Wikipedia summary; The Star report that names Setia Alam, Bukit Raja and Meru is used instead because a quote must come from the page. The 2017 seed uses NST rather than SAYS (SAYS did not resolve from this machine).

## Decisions for the human checker

- `BBR-2024-05-memorandum` is a chronic-hotspot label (`date_precision = month`), not a dated flood; keep it out of detection-time evaluation. The Jalan Makyong and Jalan Sumazau ids are every numbered BBR street starting with that name, because the article names the road, not a numbered lane. Prune if too broad.
- Persiaran Batu Belah maps to both `BBR-persiaran-batu-belah` and `BBR-persiaran-batu-belah-ku5`.
- "Persiaran Aman Perdana" (2024-11-12) and "Jalan Haji Manan" (2026-05-08) have no exact match in the street file, so they are not mapped.
- Jalan Meru, Taman Sri Jaya (2025-04-11) may not be the same road as `BBR-jalan-meru`; not mapped. Meru and Kapar rows carry `sdp_township = Bandar Bukit Raja (adjacent)`; confirm.
- `BBR-2024-11-28-01` is tagged `mixed` (heavy rain plus Sungai Binjai over danger level); `BBR-2024-11-12-01` rain 45 mm at Kampung Perepat appears in the RTM article and the Kosmo article.
- `BBR-2021-12-17-01` is a multi-day river flood (16-19 Dec); the row is dated by the article night. Exclude from the district flash model.
- `KLG-2026-09-30-01`: the article is stamped 2:59 PM but quotes a 7 pm call, so no time is recorded. Taman Rashna is Klang but not a BBR area; kept as a district-level row only.
- Same-event second sources were not given their own rows: Utusan 29 Nov 2024 (161 victims moved, Sungai Binjai, SK Sungai Binjai relief centre), Utusan 12 Apr 2025 (tide plus 5 h rain, 0.5-1 m at Meru), Star 13 Nov 2024 (photo caption "Flooding at Bandar Bukit Raja in Klang").

## Gaps

- **Utusan 14 Nov 2024** says it reported Shah Alam and Klang flash floods "Isnin lalu" (Monday 11 Nov) with Setia Alam, Bukit Raja and Meru up to 0.6 m. This may be the same event as 12 Nov (a Tuesday) or a separate one; not resolved, no row.
- **No Bandar Bukit Raja or Klang reports found** for Jan-Oct 2024 (except the May memorandum), mid-2025 to Sept 2026 apart from the rows above. A resident blog (puteribukitraja.com, "Banjir kilat April 2024") and Berita Harian Sept 2026 ("Bukit Raja junction toward i-City") could not be fetched, so they were not used.
- Kampung Bukit Kapar mud floods (Utusan 2 May 2025) have no stated flood dates; not added.
- 24 Nov 2025 Klang Valley flash floods (The Star) name Klang but no place, so no row.
- Search tools are US-based and general; no Google News RSS/GDELT sweep, Bomba or MBDK social posts, or SDP incident logs were used. SDP/MPK incident logs (spec source 1) should be requested from the mentors.
- A Star story headed "Flash floods reported in parts of Klang Valley following heavy rain on Saturday" appeared on 17 Oct 2026; its content was not retrieved.
- Facebook/TikTok resident posts were not used (no raw social content stored).
