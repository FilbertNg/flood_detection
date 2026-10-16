# Tide check: Open-Meteo vs independent Port Klang tide data

Improvement #13 (WP7). Checked 16 Oct 2026. Research only; no engine code was changed.

## Verdict

- **Timing: Open-Meteo agrees within +/- 1 h, with a consistent lead.** Its high and low water come **about 25 to 50 minutes too early** (median about 35 to 40 min) against every independent source we could reach. Nearly every individual high water is inside 1 h (observed gauge 86 of 86; news-relayed NHC forecasts 8 of 8, worst 54 min; tide-forecast.com 5 of 6, worst 62 min), so the series is usable, but it is not exact.
- **12 Nov 2024, 08:00 to 09:00 MYT is low water, not high water.** All independent evidence puts the day's high waters near 02:30 to 03:00 and 15:00 to 15:30, and low water near 09:00 to 09:30. The Open-Meteo series (lows 08:00 to 09:00) is only about 40 min early on this.
- **The news "high tide" claim is real but is about the week, not the hour.** Reports say spring-tide conditions that week; none of the reports we read gives a tide time for the flood. On the morning of 12 Nov the tide was near low water and rising.
- **Recommendation:** shift the Open-Meteo series later by about 40 min before computing `hours_to_high_tide` (details below).

## Sources

| # | Source | Kind | What we used | URL (accessed 2026-10-16) |
|---|---|---|---|---|
| S1 | UHSLC Research Quality hourly, station 140 Port Kelang (Pelabuhan Klang) | **Observation** (tide gauge) | Hourly levels 1 Jun 2022 to 6 Jan 2023 (the record ends there), UTC converted to MYT; saved in `data/reference/tide_port_klang_uhslc140_20220601-20230106.csv` | https://uhslc.soest.hawaii.edu/erddap/tabledap/global_hourly_rqds.html (uhslc_id=140); station listed by PSMSL: https://psmsl.org/data/obtaining/stations/1591.php |
| S2 | National Hydrographic Centre (PHN/NHC) forecasts, and Klang district disaster centre forecasts, as reported by news | **Prediction** (official, second-hand) | 8 high-water times and heights, 20 Sep to 16 Nov 2024; saved in `data/reference/tide_port_klang_news_nhc_20240920-20241116.csv` | The Star 2024-11-14 https://www.thestar.com.my/metro/metro-news/2024/11/14/high-tide-expected-over-next-two-days-in-klang ; The Star 2024-10-18 https://www.thestar.com.my/metro/metro-news/2024/10/18/sighs-of-relief-as-high-tide-phenomenon-passes-without-incident-in-klang ; Sinar Harian 2024-09-20 https://www.sinarharian.com.my/article/686610/edisi/selangor-kl/air-pasang-besar-keadaan-klang-terkawal-tiada-pemindahan |
| S3 | tide-forecast.com, Pelabuhan Kelang | Prediction (third-party model, MLLW datum) | High and low times 16 to 18 Oct 2026; saved in `data/reference/tide_port_klang_tideforecast_20261016-20261018.csv` | https://www.tide-forecast.com/locations/Pelabuhan-Kelang-Malaysia/tides/latest (shows only the coming 30 days, no past dates) |
| S4 | Harmonic prediction **we derived** from S1 | Derived estimate, not a published table | Predicts 12 Nov 2024 and other 2024 dates (method below) | n/a |

**Not reachable:** the official PHN "E-Tide" page (https://etide.hydro.gov.my) lists Port Klang but showed only an old demo day (August 2021) and points to a paid tide-table purchase; JUPEM and hydro.gov.my have no free downloadable Port Klang table for 2024; tide-forecast.com, tideschart and archive.org have no snapshot for November 2024. So **no published official table for 12 Nov 2024 was found**. S4 stands in for it and is labelled as derived everywhere.

S4 method: least-squares fit of 26 tidal constituents (M2, S2, N2, K2, K1, O1, P1, Q1, M4, MS4, M6, MN4, MU2, NU2, L2, T2, J1, OO1, S1, M3, MK3, MF, MM, MSF, 2N2 and a mean) to the 5,272 hourly S1 values. Test: fitted on Jun to Oct 2022 only, it predicted Nov to Dec 2022 with hourly RMSE 0.14 m (gauge standard deviation 1.09 m, correlation 0.99); its high-water times were within 60 min of the gauge for all 118 highs (median -10 min, standard deviation 26 min). Weaknesses: only 7 months of data (no annual terms), no nodal correction for 2024 (small), and it sits about 25 min earlier than the NHC forecasts (below), so treat it as +/- 30 min.

## Comparison

All times MYT. "Open-Meteo" is our `data/interim/tide_hourly.parquet` (hourly, so peak times are refined with a parabola through the three hourly points). Offset = Open-Meteo minus reference, so negative means Open-Meteo is early.

### A. Against the observed gauge (S1), 23 Nov 2022 to 6 Jan 2023

This is the only window where Open-Meteo Marine archive and the gauge overlap (the API returns nothing for earlier 2022 dates). Same point (2.95, 101.25).

| Measure | Result |
|---|---|
| High waters compared | 86 |
| Offset (Open-Meteo minus gauge) | median -35 min, mean -33, standard deviation 10, range -60 to +20; 100% within 1 h |
| Best hourly lag | gauge series moved 30 min earlier gives correlation 0.992 (rmse 0.15 m after removing means); no shift gives 0.969 (so Open-Meteo leads the gauge) |
| Amplitude | gauge swings about 1.09 times Open-Meteo (std 1.09 m vs 0.96 m): Open-Meteo is about 10% too small |

### B. Against news-relayed official forecasts (S2), 2024

| Date | Reference high water | Open-Meteo high (refined) | Offset | Our derived harmonic (S4) | S4 offset |
|---|---|---|---|---|---|
| 20 Sep 2024 | 07:23, 5.8 m (forecast) | 06:29 | -54 min | 06:53 | -30 |
| 21 Sep 2024 | 07:56, 5.6 m (forecast) | 07:05 | -51 | 07:26 | -30 |
| 21 Sep 2024 | 20:11, 5.0 m (forecast) | 19:19 | -52 | 19:46 | -25 |
| 18 Oct 2024 | 05:53, 5.9 m (**observed**, Fire and Rescue) | 05:27 | -26 | 05:50 | -3 |
| 19 Oct 2024 | 06:54, 5.7 m (forecast) | 06:01 | -53 | 06:25 | -29 |
| 20 Oct 2024 | 07:29, 5.5 m (forecast) | 06:38 | -51 | 06:58 | -31 |
| 15 Nov 2024 | 05:07, 5.5 m (forecast) | 04:20 | -47 | 04:46 | -21 |
| 16 Nov 2024 | 05:50, 5.5 m (forecast) | 05:02 | -48 | 05:25 | -25 |
| **Mean (standard deviation)** | | | **-48 (9)** | | **-24 (9)** |

Heights are above chart datum; Open-Meteo is relative to MSL (peaks near +3.0 m), so heights are not comparable (datum offset about 2.7 to 2.9 m, plus the amplitude shortfall above). Compare timing only.

### C. Against tide-forecast.com (S3), 16 to 18 Oct 2026

6 high waters: offset mean -38 min (worst -62); 6 low waters: mean -45 min. Overall -41 min, standard deviation 9.

### D. Summary of high-water offsets (Open-Meteo minus reference)

| Reference | n | Offset |
|---|---|---|
| S1 gauge observation (2022) | 86 | -35 min median |
| S4 harmonic from gauge (all of 2024) | 707 | -24 min median, 98% within 1 h, monthly medians between -20 and -29 min |
| S2 official forecasts (2024) | 8 | -48 min mean |
| S3 tide-forecast.com (2026) | 6 | -38 min mean |

The offset is systematic (same sign everywhere, small spread). The gauge is the best evidence of truth (about -35 min); NHC forecasts say about -50 min; the gap of about 15 min is within what we can resolve from hourly data and a 7-month gauge fit.

## 12 Nov 2024 in detail

| | High | Low | High | Low |
|---|---|---|---|---|
| Open-Meteo, as is (hourly) | 02:00, 2.09 m | 08:00 to 09:00, -0.39 m | 14:00, 1.64 m | 20:00, -0.54 m |
| Open-Meteo, +40 min | about 02:40 | about 09:10 | about 14:40 | about 20:40 |
| Derived harmonic (S4, gauge datum) | 02:30, 5.29 m | 09:08, 2.59 m | 14:57, 4.89 m | 21:10, 2.30 m |
| Same, +25 min (S4 vs NHC bias) | about 02:55 | about 09:30 | about 15:20 | about 21:35 |

So at 08:00 to 09:00 MYT the water was at or just past low water (rising from about 09:00 to 09:30). Neighbouring official forecasts show the springs building that week: 5.5 m at 05:07 on 15 Nov and 5.5 m at 05:50 on 16 Nov, and S4 gives a rising high of 4.85, 5.29 and 5.74 m (gauge datum) on 11, 12 and 13 Nov.

### News reports on the 12 Nov 2024 Klang flood

- Utusan Malaysia's follow-up lists the high-tide phenomenon as a contributing factor: it names "fenomena air laut pasang besar yang berlaku pada minggu ini" (the big-tide phenomenon "this week"). It gives no hour or height. https://www.utusan.com.my/berita/2024/11/hujan-lebat-luar-biasa-punca-banjir-kilat-di-selangor-semalam/
- Kosmo (https://www.kosmo.com.my/2024/11/12/tujuh-laluan-di-klang-dinaiki-air/) and Sinar Harian (https://www.sinarharian.com.my/article/696105/berita/semasa/bomba-pantau-situasi-banjir-kilat-di-selangor) report the flooding in the morning (published about 12:40) and do not mention tide.
- A search summary also credited MetMalaysia with warning that heavy rain plus high tides could worsen flooding; we did not open that source, so do not cite it.

## What the pitch may and may not say

May say:
- "Tide was running high that week (spring-tide phenomenon, forecast peaks around 5.5 m above chart datum in mid-November), and a news follow-up named it as a contributing factor."
- "Our tide feature comes from a global model (Open-Meteo Marine). We checked it against the Port Klang tide gauge and official forecasts: its high and low water run about 30 to 50 minutes early, and we correct for that." (Only after the shift is applied.)
- "Tide is one input to the ML trigger and it never lowers an official threshold."

May not say:
- That 12 Nov 2024 was flooded "at high tide", "at the peak of the tide" or "tide caused the 09:00 flooding": the best evidence says the tide was near low water and rising at 08:00 to 09:00, with high water about 02:30 to 03:00 and 15:00 to 15:30.
- That the model "proves" or "quantifies" the tide effect on this event (the news names tide as a factor, it does not quantify it; our ML has not been scored on this).
- Any tide height in metres from Open-Meteo as if it were chart-datum height (it is relative to MSL and about 10% low in amplitude).
- That the tide table for 12 Nov is an official one: it is derived (S4).

## Recommendation for `floodready/tide.py` (do not change code in this PR)

1. **Shift the series later by 40 min** after `series_from_marine`: re-index each hourly value to `t + 40 min` and interpolate back onto the hourly grid (or compute high-water times on a 5 or 10 min interpolation, add 40 min, and derive `hours_to_high_tide` from those). Evidence range for the shift is 25 to 50 min; 40 is the median of the four sources (35, 24, 48, 38). A 1 h whole-hour shift would over-correct.
2. Use sub-hourly (parabolic) peak times; with whole-hour peaks `hours_to_high_tide` has about +/- 30 min of quantisation noise, comparable to the bias.
3. Keep `tide_height_m` as an anomaly feature only; do not show it as a height in the UI. If a tide height must be shown, scale by about 1.1 and say "relative to mean sea level".
4. Retrain after the shift (feature `hours_to_high_tide` changes by about 0.7 h) and re-check that ML metrics do not move for the worse; the 12 Nov replay will change slightly.
5. To confirm, ask PHN (Pusat Hidrografi Nasional, phone number on https://www.hydro.gov.my) or JUPEM for the Port Klang hourly or high/low table for 12 Nov 2024; one real row would replace S4.

## What we could not verify

- An official published table for 12 Nov 2024 (no free source found), so 12 Nov times rest on S4 (+/- 30 min) and the bias seen on other dates.
- Open-Meteo's 2022 vs 2024 behaviour: the gauge comparison is from Nov 2022 to Jan 2023 only; the 2024 evidence is forecasts (S2) and S4, which agree on sign and size to about 25 min.
- The exact hour the 12 Nov rain and flooding began (reports say "morning"); we did not check this against our JPS rainfall readings here.
- Whether the news "high tide" reports mean the actual tide level mattered at the flooded locations (drainage backwater is plausible but not shown).
