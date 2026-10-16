# Findings: what the data says about flood prediction

A running log of facts we established while building, each with its evidence. Use it for the pitch and to understand why the system works the way it does. Started 16 Oct 2026; updated as work lands.

**Status of numbers:** results come from the JPS archive as of 16 Oct 2026 (15 river stations, 1.05M training quarter hours). They will be re-measured after the full archive (~100 river stations) and retrain; entries marked *(provisional)* will change.

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
- The Kg. Perepat gauge does work at other times: it has read up to 1.08 m (above its 1.0 m warning level) and was at alert on 27 days.
- **So:** a QC rule should flag a river gauge as *unresponsive* when it stays flat while ≥ 30 mm/3 h falls nearby, and the engine should treat it as stale rather than as "river normal". (Follow-up to WP1.)
- **Pitch line:** "We don't just read sensors, we check them against each other: a river that doesn't react to a 68 mm storm is a broken gauge, not a safe street."

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
- Before calibration, a predicted 50–70% meant **4.6%** observed; 90–100% meant 57%. After isotonic calibration: **54%** and **97%** *(provisional; a consistency fix is in progress, #22)*.
- **So:** the probability shown to residents is calibrated, or not shown.

### C3. ML warns earlier; the rules catch more on their own
- Inland, out of sample (nested threshold, pre-registered gate v2): rules alone detect **391 / 433** crossings with **90 min** median warning; rules + ML Watch detect **413 / 433** with **135 min**, at 1.33× the false alarms (limit 1.5×). Gate passes *(provisional; fresh-station check pending the full archive)*.
- The extra false alarms concentrate at a few stations (Sg. Damansara at Kg. Melayu Subang: 5.6 → 16.4 per month).
- **So:** ML may raise a street to *Watch* only; Warning and Danger stay with JPS's official thresholds.

### C4. Forecasting the river level beats "no change", but under-forecasts flash rises
- Median forecast error vs persistence: **+1 h 0.049 vs 0.097 m; +2 h 0.083 vs 0.173 m**; during rises 0.144 vs 0.392 m *(provisional)*.
- On 12 Nov 2024 at 09:00 (3.52 m) it forecast 3.70 m (3.37–4.14) for 10:00; the river reached **4.21 m**. Flash rises are faster than the model learned; the forecast is information, not an alert trigger.

## D. Streets and terrain

### D1. Gauge spacing decides how local an alert can be
- BBR's rain gauges sit **5–9 km apart**. With a 5 km radius **no street had two gauges**, so each street depended on one; on 12 Nov 2024 the memorandum streets then got **no Warning at 09:00**, because the storm cell was caught by the Kg. Perepat gauge ~8 km away.
- **10 km is the smallest radius that gives every street ≥ 2 gauges.** With it, the memorandum streets are at Warning by 09:00 (38 of 61 segments), as with the old township-wide alert.
- Per-street alerts cut Warning + Danger alerts in Nov 2024 by a third (**4,526 → 3,032**).

### D2. Flow paths on a 30 m DEM fail on the flat coast
- D8 flow tracing links inland stations correctly (Damansara → Sri Muda; Kuyoh, Penchala → Puchong Drop) but finds **nothing upstream of Bandar Klang**: the coastal plain is too flat. Same-river links there are added by name with stated evidence.
- Upstream gauges far away dilute the signal: for Bandar Klang, the max rise over all 28 upstream gauges correlates 0.09 with its own next-hour rise; over gauges within 12 km, 0.29. Upstream features are capped at 15 km (2 h × 1–2 m/s flood-wave speed).

### D3. Removing trees from the elevation map helps; distance to drains matters most
- Memorandum street segments in the top two susceptibility classes (40% = chance): **GLO-30 62% → FABDEM 70% → FABDEM + new features 79%** *(61 segments, 38 from Jalan Makyong; 95% interval about 67–87%)*.
- The gain comes mostly from **distance to the nearest drain or river** (dropping it → 59%).
- GLO-30 minus FABDEM over BBR: built-up cells drop ~1.9 m, non-built cells ~3.2 m, so the correction is mostly **vegetation canopy**, not buildings.
- Built-up share looks "wrong" on these streets only because the township is 83% built-up; it is kept for physical reasons, not tuned.

## E. Sources and constraints

### E1. The official flood API is frozen
- data.gov.my's flood API stopped at 23 Feb 2024; live and history come from JPS Public Infobanjir.

### E2. Radar exists but needs permission
- MET Malaysia publishes a radar composite (518 km range, covers Klang) but its copyright notice forbids reuse without written consent. The radar nowcast is built and off by default.
