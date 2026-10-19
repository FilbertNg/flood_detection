# Findings: what the data says about flood prediction

A running log of facts we established while building, each with its evidence. Use it for the pitch and to understand why the system works the way it does. Started 16 Oct 2026; updated as work lands.

**Status of numbers:** final. Results come from the complete JPS archive of 17 Oct 2026 (310 station series: 79 river stations, 233 rain gauges; 64 river stations with thresholds in training, 4.54M training quarter hours, 9,128 positives) after the final QC rules (#32, #35) and tide fix (#34). Earlier 15-station numbers are superseded.

Sources: [ml-data-eda.md](ml-data-eda.md), [tide-check.md](tide-check.md), [data-qc-report.md](data-qc-report.md), [evaluation-report.md](evaluation-report.md), and the PR reviews (#15–#22).

## A. Rivers, tides and storms

### A1. A high river is not always a flood: there are two kinds of "crossing"
- **59% of warning-level crossings are tidal.** At the two tidal stations (Bandar Klang, Pandamaran), **96.5% of crossings happen within 1.5 h of high tide** (24% would be chance), at a median tide of 2.36 m (above the 90th percentile), and **62% come with no rain** (< 10 mm in 6 h within 25 km).
- Inland stations behave differently: 31% near high tide (about chance), crossings cluster in the evening storms.
- **So:** the system judges inland flash floods separately from spring tides. Pooled numbers would mostly measure tide prediction.
- **Pitch line:** "Not every high river is a flash flood. Our data shows 6 in 10 river alarms in Klang are spring tides, so we judge storms and tides separately."

### A2. One station can dominate the statistics
- **Sg. Klang at Bandar Klang holds 583 of 1,050 crossings (56%)** and spends 970 hours above warning, because its warning level (2.7 m) is reached by spring tides.
- **So:** our headline metric is inland stations only; pooled results are reported but not used to claim success.

### A3. A flat river level is not a fault by itself
- **Healthy gauges are flat most of the time.** Sg. Binjai at Pekan Meru stays within 1.5 cm for 6 h or more in **91% of its readings** (base flow). Yet on 12 Nov 2024 it rose **2.94 → 4.06 m in 90 minutes**. Flat means "nothing is happening", not "broken".
- **The fault signature is flat during heavy nearby rain.** On 12 Nov 2024, 07:00–11:00, the same storm (**67.5 mm in 1 h, 79 mm in 3 h** at gauges within 10 km of both stations) hit Pekan Meru and Kg. Perepat (Sg. Kapar Kechil, `26558`). Pekan Meru rose 1.32 m; **Kg. Perepat stayed at exactly −0.78 m** for the whole period.
- The Kg. Perepat gauge worked before July 2024 (see A3c): it has read up to 1.08 m (above its 1.0 m warning level) and was at alert on 27 days.
- **So:** a QC rule flags a river gauge as *unresponsive* when it stays flat while ≥ 30 mm/3 h falls nearby, and the engine treats it as stale rather than as "river normal" (PR #24).
- **The first version wasn't strict enough, then wasn't thorough enough.** A single wet gauge was enough to flag a river, which flagged Pekan Meru 247 times at base flow (one local cell). Requiring **two gauges ≥ 30 mm** cut that to 35, and the remaining 35 sit 0.9 m below alert.
- **Pitch line:** "We don't just read sensors, we check them against each other: a river that doesn't react to a 68 mm storm is a broken gauge, not a safe street."

### A3c. Some public JPS gauges have been dead for months, and nobody flags them
- **Kg. Perepat (`26558`) has been dead since about 28 Jul 2024.** It read −0.78 m, then 0.36 m from 22 Nov 2024 to today. In ~60 storms since, including two-gauge storms of 70/61 mm, it moved **at most 0.08 m**, while after the same storms the inland Pekan Meru gauge rose a median 0.58 m. Before Aug 2024 every one of its 13 storms with data raised it 0.3–1.2 m.
- Its daily range fell from **0.89 m (Q2 2024, tidal)** to **0.02–0.09 m every quarter since**. JPS Infobanjir still publishes it as a live reading.
- The full archive shows the same at five more river stations: `26376` read 5–6 m below its normal 28 m for months while neighbours rose 0.5–3.8 m; `26413` sat at 18.86–18.88 m for 7 weeks; `26353`, `3017107_` (Seri Kembangan) and `2717134_` (Salak Tinggi) had dead periods of weeks to months.
- **So:** QC now keeps a per-gauge **dead state**: after two unanswered two-gauge storms within 30 days (no movement ≥ 0.10 m within 8 h, while an inland river within 15 km did respond), every reading below alert is blanked until the gauge moves ≥ 0.2 m. On Kg. Perepat, the old rule blanked **13.8%** of the dead period; the dead state blanks **87.3%**. Nothing at or above an alert level is ever blanked, and 12 Nov 2024 at Pekan Meru and Pandamaran is untouched (PR #35).
- **Why it matters:** a dead gauge reading "normal" teaches the model that heavy rain leaves rivers calm, and tells a street "river normal". Across the archive the QC now blanks **193,723** river readings as unresponsive or dead.
- **Pitch line:** "Kg. Perepat's river gauge has been frozen since July 2024 and is still published. Our system noticed on its own, because in 60 storms it never moved while the river at Pekan Meru rose."

### A3b. Rivers answer rain late, and a stuck gauge at flood level must fail safe
- **The most dangerous moment looks like a broken gauge:** heavy rain has started and the river hasn't moved yet. A first version of the stuck-gauge rule would have blanked Pekan Meru for up to 1.5 h at the start of a flood if the river responded 90 min after the rain. The rule now requires the rain to have ended ≥ 90 min earlier and the level to have stayed flat for 4.5 h. In tests, Pekan Meru then has 0 flags at any response delay from 0 to 120 min, and Kg. Perepat keeps 98% of its flags (8,307 vs 8,521 on its own gauge).
- **A gauge that is flat at or above its alert level is never blanked.** A sensor stuck high, or a river plateauing over its banks, would otherwise turn an official Danger into "no data" after the 2 h forward-fill. Failing safe means keeping the last value.
- **So:** data-quality rules are safety-critical too; every QC rule is checked for whether it can *lower* an alert, not only whether it removes bad data.

### A4. Warning time is limited by when rain is first seen
- On 12 Nov 2024 rain at the gauges within 10 km started building at 08:00 (14 mm/h) and peaked at 67.5 mm/h at 09:15. The river crossed alert at 09:15, warning at 09:30, danger at 10:00.
- Rain-gauge signals cannot fire before rain reaches a gauge, so about 90 minutes is the ceiling for rain-driven warning on this kind of storm. Seeing storms *before* they arrive needs radar (§E2).

### A5. Rain alone is a weak predictor; the river's own state is strong
- Single-feature ROC-AUC for "crosses warning within 2 h": river rise over 120 / 60 / 15 min **0.90 / 0.89 / 0.88**; distance to warning level 0.88; **rain features 0.62–0.66**.
- **A quarter of inland crossings had no rain at nearby gauges** (cells between gauges, rain beyond 25 km, or backwater).
- Permutation importance: once the river is rising, rain adds little (best rain feature 0.011 vs river level 0.21).
- **So:** the ML watches river behaviour first and uses rain, tide and upstream rivers as context.

### A6. Gridded weather-model rain misses flash floods
- On 12 Nov 2024 the gridded model showed **≤ 6.8 mm** where the JPS gauge recorded **79 mm**. Everything in the system uses JPS station rain.

## B. Data quality: what raw sensor data gets wrong

### B1. Rain gauges report impossible values after gaps
- JPS rain is a counter diffed every 15 min. After a gap or the 1 Jan reset the difference jumps: values from **−3,275 to +2,747 mm in 15 minutes**; one gauge (27879) repeated 296.5 mm for three days.
- Before QC, these touched **6.2% of training rows** (through rolling sums up to 72 h) and made the JPS rule fire on **1,221 extra quarter hours**.
- A dip-and-restore is subtler: gauge 26352 read **−57.0 then +56.5 mm** between zeros; the +56.5 alone would have triggered a Watch. QC now removes both.
- Real storms survive QC: the largest rain value kept is 95 mm/15 min, and 22 readings ≥ 60 mm remain; nothing on 12 Nov 2024 is touched.

### B2. River gauges spike
- Sg. Penchala (`3016080_`) read **10.22 → 13.08 → 10.88 m**: a one-reading spike that would have been a false crossing of its 13.0 m alert level. QC compares each reading with both neighbours (132 spikes flagged, none on 12 Nov).

### B2b. Some rain gauges invent rain
- **Gauge 26405 (Kuala Lumpur) recorded 2,113 mm in May 2024** (raw readings in `data/raw/jps_hist/rf/26405.parquet`), with weekly totals of 365–820 mm while the Kuala Lumpur median was 56–92 mm. Four single readings were above 100 mm in 15 minutes (max 340 mm).
- **Gauge 26519 (Jambatan Petaling) reported ≥ 5 mm of rain on 48 of 50 days** (7 Jun–26 Jul 2026), 140–250 mm a week, while its daily totals correlated only 0.25 with its neighbours' median.
- **So:** a monthly rule flags a gauge whose rolling 30-day total is > 600 mm and > 3× its neighbours' median (196 readings at 3 gauges, all confirmed faults). It is a backstop; most of 26405's fault is already removed by the 100 mm/15 min rule.

### B3. The tide model is 40 minutes early
- Open-Meteo's global tide model vs the Port Kelang tide gauge (UHSLC station 140): **86 high waters, median 35 min early** (sd 10). Official forecasts relayed in the news: 48 min early; tide-forecast.com: 38 min. We shift high-water times by +40 min.
- **12 Nov 2024 08:00–09:00 was low water**, not high water. News talk of "high tide" referred to spring tides that week.
- **Pitch line:** say "tide was running high that week", never "the flood happened at high tide".

### B4. A feature can secretly identify the station
- "Number of rain gauges within 10 km" scored ROC-AUC 0.67 although a gauge count cannot predict a flood: it is constant per station, so the model used it to recognise stations. Removed.

## C. What the model's numbers really mean

### C1. Accuracy is the wrong metric
- Only **0.6% of quarter hours** precede a crossing. A model that always says "no flood" is **99.4% accurate**. We report detection, warning time and false alarms per crossing event instead.

### C2. Raw ML probabilities were 10× too confident
- Before calibration, a predicted 50–70% meant **4.6%** observed; 90–100% meant 57%.
- **The cause was the training setting, not the model:** `class_weight="balanced"` up-weights the rare positives ~80×. Trained without it, the model is calibrated on its own. On the full archive, out of sample: Brier 0.00118, calibration error 0.0003, PR-AUC 0.578 (balanced + isotonic: 0.567). A predicted 30–50% comes true 38.7% of the time; 50–70%, 63.4%.
- **So:** the probability shown to residents is calibrated, or not shown.

### C3. ML warns earlier; the rules catch more on their own
- Inland, out of sample, nested threshold, full archive (64 river stations, 890 inland crossings): rules alone detect **795 / 890** with **90 min** median warning and 6.56 false alarms per station-month; rules + ML Watch detect **823 / 890** with **135 min**, at 7.92 (1.21×). ML alone: 674 / 890, 105 min, but only 3.37 false alarms.
- On 12 Nov 2024 the out-of-sample probability at Sg. Binjai was **10% at 08:30, 31% at 09:00, 51% at 09:15**; the river crossed warning at 09:30.
- **So:** ML may raise a street to *Watch* only; Warning and Danger stay with JPS's official thresholds. This is enforced in code, not only in config.

### C3b. The pre-registered gate failed on unseen stations, so ML does not raise alerts
- Gate v2 was written down before the final run (16 Oct): ML may raise Watch only if, on inland stations, it adds **≥ 30 min** median warning at **≤ 1.5×** the false alarms, **and the same holds on stations the EDA never looked at** (if they have ≥ 30 crossings).
- Criteria 1–2 pass (+45 min at 1.21×). **Criterion 3 fails:** on the **49 fresh stations (467 inland crossings)** the rules already warn **105 min** ahead; rules + ML give **120 min**, only +15 min.
- **So:** `ml_drives_alerts` is **false**. The probability is shown to residents, the river forecast is shown, and the JPS rules alone set Watch/Warning/Danger. We did not move the threshold after seeing the result.
- **Pitch line:** "We set the bar before the test and our ML missed it on rivers it had never seen, so it informs but doesn't raise alerts. Judges can trust our other numbers because we report this one."

### C5. Adding rain gauges changes the rule baseline too
- As more gauges were archived (38 → 50 within 25 km), the rule floor's inland detections rose from **391 to 399 of 433** and its false alarms from **5.72 to 6.14** per station-month. ML alone stayed near 352–359.
- **So:** every comparison must use the floor from the *same* run and data; numbers from different days are not comparable.

### C6. The river forecast helps most where the tide drives the river
- Out of sample, mean absolute error vs "level stays the same", +1 h: **tidal stations 0.125 vs 0.255 m (−51%)**, **inland 0.040 vs 0.050 m (−20%)**. At some inland stations it is no better than persistence.

### C4. Forecasting the river level beats "no change", but under-forecasts flash rises
- Mean absolute error vs persistence, all 64 stations: **+1 h 0.045 vs 0.061 m (−27%); +2 h 0.069 vs 0.103 m (−33%)**. The p10–p90 range holds the actual level 80% of the time, as intended.
- On 12 Nov 2024 at 09:00 (3.52 m) it forecast 3.67 m (3.23–4.34) for 10:00; the river reached **4.21 m**. Flash rises are faster than the model learned; the forecast is information, not an alert trigger.

### C7. Tide values were up to 45 minutes stale
- The 15-minute features took the tide of the whole hour, so at 09:45 the model saw 09:00's tide. Measured on the harmonic tide curve at 15-minute steps (PR #34 review), the old hour value is off by **22.8 cm RMS (max 89 cm)**; evaluating at the exact time gives **2.3 cm RMS (max 7.6 cm)**.

## D. Streets and terrain

### D1. Gauge spacing decides how local an alert can be
- BBR's rain gauges sit **5–9 km apart**. With a 5 km radius **no street had two gauges**, so each street depended on one; on 12 Nov 2024 the memorandum streets then got **no Warning at 09:00**, because the storm cell was caught by the Kg. Perepat gauge ~8 km away.
- **10 km is the smallest radius that gives every street ≥ 2 gauges.** With it, the memorandum streets are at Warning by 09:00 (38 of 61 segments), as with the old township-wide alert.
- Per-street alerts cut Warning + Danger alerts in Nov 2024 by a third (**4,526 → 3,032**).

### D1b. Notification volume decides whether people keep listening
- In Nov 2024 (a stormy month), issuing Watch as well as Warning/Danger gives about **17.5 messages per street** (alerts + all-clears; max 34). Pushing only Warning and Danger gives **3.2 per street** (max 8). Longer Watch cooldowns barely help (8.7 → 8.3 alerts per street). *(Measured before the all-clear hold of D1d, which removes some of these messages.)*
- **So:** this is the cost of pushing Watch. The team decided (17 Oct 2026) to push Watch, Warning and Danger (`alerts.push_levels`); the numbers above are what residents should expect in a stormy month.


### D1d. The all-clear hold removes some flapping, not all of it
- When rain hovers around the Watch threshold a street used to get an all-clear on the first normal tick and then a new alert. `alerts.clear_after_min: 60` holds the all-clear until the alert is 60 min old, and the alert stays active in the app meanwhile.
- BBR, 1 Apr to 1 May 2024, full replay (rules + out-of-sample ML, per-street stations, 943 streets). "Fast re-alert" = an alert issued 60 min or less after an all-clear on the same street (measured by the #53 reviewer, who reproduced the alert counts):

| Hold | Alerts | All-clears | Re-alerts within 60 min of an all-clear |
|---|---|---|---|
| 0 (old behaviour) | 8,782 | 6,684 | 1,566 |
| 60 | 8,426 (-4%) | 6,205 | 1,123 (13% of alerts) |
| 180 | 8,426 | 5,420 | 369 |

- Watch 6,689 → 6,333; Warning (1,689) and Danger (404) unchanged. Median alerts per street stays 8; the maximum falls 76 → 65.
- **Why a longer hold does not cut the alert count (8,426 at both 60 and 180):** the hold counts from the alert's issue time, not from when the street went quiet. An alert older than the hold is cleared on the first Normal tick, and a same-level re-entry alerts again once the cooldown has passed. So the hold only removes flapping in the first hour of an alert; about 1,100 re-alerts a month still follow an all-clear within an hour.
- **Known limitation:** the full fix is to hold the all-clear until the street has been continuously Normal for `clear_after_min`, and not to re-alert at the same level while an alert is active. That needs per-street "normal since" state next to `last_alerts`, which changes a frozen engine interface, so it is deferred. The Watch push cap (D1e) limits what residents feel.

### D1c. 85 BBR streets take their river signal from the dead gauge
- The street→station mapping (`assets/geo/bbr_street_stations.json`) follows the flow path: **85 of 943 BBR streets** use Kg. Perepat (`26558`) as their own river (668 use Pekan Meru, 190 Pandamaran). With the gauge blanked, those streets keep their rain rules but have no river level or ML probability.
- **Open fix:** when a street's own river station is dead or stale, fall back to its next-nearest river station.

### D2. Flow paths on a 30 m DEM fail on the flat coast
- D8 flow tracing links inland stations correctly (Damansara → Sri Muda; Kuyoh, Penchala → Puchong Drop) but finds **nothing upstream of Bandar Klang**: the coastal plain is too flat. Same-river links there are added by name with stated evidence.
- Upstream gauges far away dilute the signal: for Bandar Klang, the max rise over all 28 upstream gauges correlates 0.09 with its own next-hour rise; over gauges within 12 km, 0.29. Upstream features are capped at 15 km (2 h × 1–2 m/s flood-wave speed).

### D3. Removing trees from the elevation map helps; distance to drains matters most
- Memorandum street segments in the top two susceptibility classes (40% = chance): GLO-30 38/61, FABDEM 43/61, FABDEM + new features 48/61. The shipped variant was **pre-specified**; this check confirms it, it does not measure an improvement. The segments are not independent (38 of 61 are Jalan Makyong; Jalan Sumazau went 80% → 75%), so do not quote "62% → 79%" as a gain.
- The gain comes mostly from **distance to the nearest drain or river** (dropping it → 59%).
- GLO-30 minus FABDEM over BBR: built-up cells drop ~1.9 m, non-built cells ~3.2 m, so the correction is mostly **vegetation canopy**, not buildings.
- Built-up share looks "wrong" on these streets only because the township is 83% built-up; it is kept for physical reasons, not tuned.

## E. Sources and constraints

### E1. The official flood API is frozen
- data.gov.my's flood API stopped at 23 Feb 2024; live and history come from JPS Public Infobanjir.

### E2. Radar exists but needs permission
- MET Malaysia publishes a radar composite (518 km range, covers Klang) but its copyright notice forbids reuse without written consent. The radar nowcast is built and off by default.
