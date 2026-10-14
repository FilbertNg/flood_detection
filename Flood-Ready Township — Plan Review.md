# Flood-Ready Township — Plan Review

14 Oct 2026 · Review of *Flood-Ready Township — PRD* and *Flood-Ready Township — Training Data Spec* (v1)

> **Status:** the plan fixes (C1–C5, B1–B8, and A-06 to A-28 where they change the plan) are now written into **PRD v2** and **Training Data Spec v2**, which are the current documents. This review describes v1 and is kept as the record of why things changed; the v1 files are in `archive/`. Actions A-01 to A-05, A-07, A-08, A-11 and A-28 are work to *do*, not plan changes, and are still open. A-04 and A-05 are optional. **Timeline correction:** this review assumed 23 Oct was a paper proposal; it is the full MVP submission (deck, 5-minute video, code). The current plan is PRD v3 + `docs/superpowers/plans/2026-10-14-mvp-build-plan.md`.

## TL;DR

**The plan is strong for this hackathon.** Most teams will not have a problem grounded in a dated SDP residents' memorandum, named streets and station readings. The idea fits the Planet → Climate resilience track, ties into SDP's sales goals, and the two documents are well organised. On the story and product concept, this is a Top 10 contender as written.

**The data plan needs fixing before you build on it.** It is well structured, but I found five problems that would break the demo or the evaluation if left alone. Two of them I confirmed today by calling the live sources:

1. **The live river and rain feed you depend on looks frozen.** On 14 Oct 2026 the data.gov.my Flood Warning API returned 1,276 stations, and every one had last updated on 23 Feb 2024. The JPS Public Infobanjir website is live: Sg. Binjai at Pekan Meru read 3.21 m at 19:45 today. ING-1 and logger task T2 need to switch to it.
2. **The Outlook would be trained on forecasts it would never have in real use.** Open-Meteo's Historical Forecast API joins up the *first few hours* of each model run. That is close to observed rain, not a 6–24 h forecast, so training on it makes the Outlook look far better than it will be.
3. **The demo replay needs data you don't have.** "Sg Binjai rises toward 4.2 m" on 4 Jun 2023 needs 15-minute river history. The API has no history, and the news gives you one reading.
4. **The map validation is circular.** The memorandum streets are training labels, and the pitch then shows that "red streets match the memorandum streets".
5. **Training rain and live rain come from different sources.** The trigger model learns thresholds on smoothed ERA5 rain (~9–25 km grid) but runs live on spiky station rain, so it will over-fire.

There are also three label-leakage traps in Table B, and success metrics that 3 held-out events cannot measure. The fixes are cheap and you can build them; the action list is at the end.

| Area | Score now | After fixes | Comment |
| --- | --- | --- | --- |
| Problem & story | 9/10 | 9.5 | Real SDP township, dated events, named streets. Excellent. |
| Product concept | 8/10 | 8.5 | Two alert horizons + sensor + sales card is a full, believable product. |
| Technical design | 7/10 | 8.5 | Sound architecture; the trigger model is more ambitious than the labels can support. |
| Data plan | 6/10 | 8 | Good structure; dead live source, forecast leakage, label leakage. |
| Feasibility / scope | 5.5/10 | 8 | 18 Musts, 2 ML models, IoT, a bot and 3 UIs in about 3 weeks of build time is too much. |
| Evaluation & demo honesty | 5/10 | 8.5 | Circular map check; replay data you don't have; metrics too fine for 3 events. |

## Update (14 Oct, later): JPS station history is publicly available

After this review was first written, I found that **Public Infobanjir serves past station readings** through the endpoints behind its graph pages. Neither endpoint is documented, and neither needs a login:

| Data | Endpoint (under `publicinfobanjir.water.gov.my/wp-content/themes/enlighten/query/`) | History available |
| --- | --- | --- |
| Water level, 5–15 min | `searchresultwaterleveldtlead.php?station=<graph id>&from=DD/MM/YYYY HH:mm&to=…&datafreq=15` | From about **Apr 2024** (1 Mar 2024 empty, 1 Apr 2024 present) |
| Rainfall, 5–15 min | `searchresultrainfalldthourlylead.php?station=<graph id>&from=…&to=…&datafreq=15` | From about **Jan 2024** (1 Oct 2023 empty, 1 Jan 2024 present) |

Graph IDs come from the `stationid=` links in the live tables (Sg. Binjai @ Pekan Meru = `PEKANMERU`; Kg. Perepat = `26558`). Neither endpoint returned anything for 4 Jun 2023.

**12 Nov 2024 from the real series:** Kg. Perepat rain began at about 08:15 and reached **61.5 mm by 09:00** and **79 mm by 10:15**. Sg. Binjai went from **2.94 m at 08:00** to **4.21 m (danger) at 10:00** and peaked at **4.26 m at 11:45**. So JPS's own 60 mm rule would have fired at about 09:00, roughly an hour before the river reached danger level.

**What this changes:**
- **C3:** the demo can replay **12 Nov 2024 from real 15-min data**. It is already your planned held-out test event, so the demo is out-of-sample too. 4 Jun 2023 becomes a supporting slide using news numbers only.
- **C5:** for events from 2024 onward you can train and test the rule layer on **real station rain**, the same source the live system uses.
- **A-04 (JPS data request)** drops from critical to nice-to-have: it only adds events before 2024.
- **New risk:** these endpoints are undocumented and could change or start blocking. **Archive everything now** (A-28).

## Fit against the judging criteria

The official page gives six weighted criteria, and the PRD mentions them without listing them. Map the proposal to these headings explicitly, because the assessors score against them.

| Criterion | Weight | Plan today | Gap to close |
| --- | --- | --- | --- |
| Impact & Sustainability Value | 25% | Strong story; impact not quantified | Put numbers on it: homes in BBR Phase 1–2, residents covered, minutes of warning, RM of car/contents damage avoided per event (cite a source) |
| Innovation & Differentiation | 20% | Street-level, developer-run, sales card | Say clearly why JPS / MET / Infobanjir don't already do this. Add **resident flood reports** (A-22), which turn residents into sensors |
| Feasibility & Deliverability | 20% | Weakest area: big scope, live source dead | Cut scope (A-19). Show **working pieces** in the proposal: logger running, first BBR terrain map (A-07, A-08) |
| Strategic Fit & Theme Relevance | 15% | Good: Planet → climate resilience, SDP township | Use the page's own pitch structure: **Mechanism** (how it works, who benefits) and **Enabler** (technology and township-scale rollout) |
| Commercial & Value Multiplication | 10% | Good argument, no numbers | Cost per township (sensor BOM, VM), scaling story across 10 townships |
| Team, Evidence & Pitch Quality | 10% | Buyer survey planned | Survey plus 5–10 BBR resident interviews; report honest evaluation numbers |

## What is already strong (keep it)

- **Problem grounding.** The memorandum, the 4 Jun 2023 readings (98.5 mm, 4.38 m vs 4.2 m) and the 12 Nov 2024 road list are exactly the evidence judges want.
- **Susceptibility × trigger split.** Separating *where* from *when* is the right way to get street-level output from district-scale data.
- **A rule baseline first, ML second.** That is the correct order for this label count.
- **Alert levels that mirror JPS's four levels.** Residents and authorities read them the same way.
- **Honest risk table and "advisory only" footer.** It shows maturity.
- **Split by event date, never randomly.** Correct and often missed.
- **Seed incident table with source URLs and `checked_by`.** This is a good label discipline.
- **Licensing and PDPA handled up front.**

## Critical findings (fix before building)

### C1. The data.gov.my Flood Warning API is stale; use JPS Public Infobanjir

**Evidence (checked 14 Oct 2026, 20:20 MYT):**

- `https://api.data.gov.my/flood-warning/` returns 1,276 stations. The latest `water_level_update_datetime` / `rainfall_update_datetime` per station is in **Feb 2024 for 1,163 stations**. The rest are older or blank, and **none are from 2026**.
- The 46 stations within 25 km of Bandar Bukit Raja are all frozen at `2024-02-23 14:30/14:45`.
- The doc link used in both documents (`developer.data.gov.my/realtime-api/flood-warning`) returns **HTTP 404**.
- **JPS Public Infobanjir is live:** `publicinfobanjir.water.gov.my/aras-air/data-paras-air/aras-air-data/?state=SEL&district=ALL&station=ALL&lang=en` lists Selangor water levels with timestamps of 14/10/2026 19:30–20:00, plus thresholds. Sg. Binjai di Pekan Meru read **3.21 m**, with normal 2.80 / alert 3.80 / warning 4.00 / danger 4.20, matching the 4.2 m in the news. The page is server-rendered HTML, so it is easy to scrape.
- The rainfall table at `/hujan/data-hujan/?state=SEL` is loaded by JavaScript. Its data URL still has to be found with browser dev tools or Playwright.

**Impact:** ING-1, TRG-1 river features, Dataset 3, T2 and the "≤ 20 min freshness" metric all depend on a feed that is no longer updating. Had the logger been started as specified, it would have collected weeks of identical 2024 readings.

**Fix:** Build T2 on Infobanjir (water level + rainfall pages for Selangor, every 15 min). Keep the data.gov.my client as a fallback. Add a **staleness check**: if a source timestamp is older than 2 h, mark the station missing. That check would have caught this, and it should also become a non-functional requirement.

### C2. Open-Meteo "historical forecast" is not a 6–24 h forecast

The Open-Meteo docs say the Historical Forecast API is "a continuous hourly timeseries built by stitching the first hours of each successive model run". Its values are effectively 0–6 h-ahead analyses, close to observed rain. Training `fcst_rain_next_3h/6h/12h` on it, and claiming an Outlook lead time of 6–24 h, overstates forecast skill.

**Fix:**

- For **Outlook features and evaluation**, use the **Previous Runs API**, for example `precipitation_previous_day1`, which is the value forecast 24 h earlier. Data starts **January 2024** for most models (GFS from March 2021). That covers 12 Nov 2024 and 23 Apr 2025.
- For events before 2024, either train the Outlook without forecast features (MET warning plus climatology) or say plainly that the forecast skill is untested for those events.
- Start **logging the live Open-Meteo forecast every hour now**, so you have your own archive of real 6–24 h forecasts by November.

### C3. The demo replay of 4 Jun 2023 needs data that doesn't exist in your plan

The demo script says that "Nowcast turns Jalan Makyong red as Kg Perepat rain climbs and Sg Binjai rises toward 4.2 m". You have **two numbers** for that day (a 98.5 mm total and 4.38 m at 12:00), not a 15-minute series. You cannot build a replay curve from them without inventing values, and a judge who asks "where is this curve from?" sinks the Feasibility score.

**Fix, in order of preference:**

1. **Request historical JPS station data now.** JPS's hydrology division supplies historical hydrological data on request, and it can take weeks. Ask SDP mentors to speed it up. Ask for Kg Perepat, Sg Binjai at Pekan Meru, Bandar Klang, Telok Gong and Rantau Panjang, at 15-minute resolution, for each labelled event.
2. **Catch a live event.** October–November is the inter-monsoon season, when Klang Valley gets frequent afternoon thunderstorms; the 12 Nov 2024 event was in this window. If the Infobanjir logger runs from today, there is a real chance of logging a flash flood in Klang end to end before 11 Nov. "Our system logged this one live" is the strongest possible demo.
3. **Fallback:** replay with gridded rain (Open-Meteo, or GPM IMERG at 30 min), and show the news-quoted station readings as **labelled annotation points**, not as a fake curve.

Also, **don't demo on an event the model trained on.** Hold out 4 Jun 2023 as the demo test event, or use leave-one-event-out so that every replay is out-of-sample.

### C4. The map validation is circular

Jalan Makyong, Jalan Sumazau, Persiaran Sungai Keramat and Persiaran Batu Belah are positive labels in Table A. Demo step 2 then says the "red streets match the memorandum streets". A map that was trained on those streets will of course mark them red.

**Fix:** **Hold out every memorandum street and every BBR point from map training.** Train on the other townships plus Sentinel-1 points, then show that the map *independently* turns those streets red. If it works, this is the best moment in the pitch; if it doesn't, you find out now rather than on stage.

### C5. Training rain and live rain come from different sources

The PRD's risk table says: "Use [ERA5] for training only; live system uses station rain". A gridded cell of 9–25 km averages a thunderstorm down. Your news-quoted 98.5 mm at Kg Perepat may appear as 30–40 mm in ERA5 (you will measure this in A-12). Thresholds learned on the smooth data will fire constantly on spiky station data.

**Fix:**

- The **ML trigger** must train and run on the **same source**. The cleanest pairing is the Open-Meteo **Historical Forecast API for training** with the **live Forecast API (`past_hours` / current hours) in production**. They use the same models and the same format; the docs describe this as "data that matches the live Forecast API format exactly". ERA5 itself has a ~5-day delay, so it cannot run live anyway.
- **Station rain and river level** go into a **rule layer** with thresholds in physical units. JPS's own rainfall page states: *"Convective rain more than 60 mm in 2 to 4 hours duration (typical) may cause flash floods."* That is an official, citable rule baseline for TRG-2. River rules can use each station's own alert/warning/danger levels.
- The final level is the higher of the ML level and the rule level, and every alert shows which one fired, which keeps the explainability promise.

## Modelling and data blindspots

### B1. Too few labels for a per-street hourly XGBoost

You will probably have 10–30 dated events at street or taman precision. At hourly grain with 3 horizons, XGBoost will memorise them. Holding out 3 events means recall can only be 0%, 33%, 67% or 100%, so the "≥ 70% recall" target can't be measured meaningfully.

**Fix: change what the trigger model predicts.** The rain feature is a 9–25 km grid cell, so all BBR streets share the same rain. The honest question for the trigger is therefore **"will flash flooding be reported in this district in the next N hours?"**, and the street-level detail comes from susceptibility. That is exactly the PRD's formula, Risk = S × P. It also lets you use **every reported flash flood in Klang, Petaling, Shah Alam and Kuala Lumpur** as a positive, which could give 50–150 dated events across 2017–2026 instead of about 10. Start with logistic regression or rainfall intensity–duration thresholds, and keep XGBoost as a stretch goal (it is already a Should).

### B2. Most news articles give a day, not an hour

`label_flood_next_1h/3h/6h` needs an hour. "Pagi tadi" → `date_precision = day` is correct, but it means most positives can't produce hourly labels. Be careful not to **infer the start hour from the rain peak**: that makes the label a function of the input, which is circular.

**Fix:** Train on **day-level labels** (P(flood today | rain features up to hour h)). Use the hour-precision events (2017-11-07 at 05:00, 2023-06-04 at 12:00, 2025-04-23 at 05:44, Bomba call times) **only to measure lead time**.

### B3. Three leakage traps in Table B

| Feature | Why it leaks | Fix |
| --- | --- | --- |
| `met_warning_active` (historical) | It comes "from news". News mentions a MET warning mostly *on flood days*, so the feature is ≈ the label. | Leave it out of ML training; use it in the Outlook rule. The weather-warning API only returns current warnings (oldest returned today: 14 Oct 2026), so start logging it now. |
| `tide_flag` | It comes from `events.csv`, so it is known only for flood rows. | Replace it with **computed tide height** for every hour (B6). |
| `susceptibility_score` | Model A was trained on these same event points, so they score high in-sample. | Use out-of-fold scores, or drop it. The trigger already runs per location. |

Also: `river_margin_m` would be null in almost every training row but filled live, which is another training/live mismatch. Keep the river in the rule layer (C5) until you have historical JPS data.

### B4. Negative labels and false-alarm measurement

- "No news report" does not mean "no flood". Small floods go unreported, so some negatives are really positives. Label them `probable_negative` and say so.
- A fixed 5:1 negative-to-positive ratio sets the base rate artificially, so predicted probabilities won't be real probabilities. Calibrate on a continuous period.
- **"≤ 4 false Warnings per month" can't be measured from sampled negatives.** Run the model hour by hour over a **continuous period** (for example every hour from Oct 2024 to Mar 2025), count the Warnings, and check each one against news. Define the unit too: per township or per street?

### B5. Biases in the susceptibility map

- **Reporting bias:** news-geocoded positives sit on main roads and named places. If dry samples are drawn at random over the whole buffer (fields, forest), the model learns that "roads and buildings = flood". **Fix:** draw dry samples from the **same kind of places**, i.e. along the OSM road network and inside built-up areas, at least 200 m from known floods.
- **Spatial autocorrelation:** neighbouring points are near-duplicates. Use **spatial block cross-validation** (for example 1 km blocks, or one township left out).
- **Unsupervised baseline:** with about 50 positive points the ML map may be no better than **HAND alone**. Compute a HAND + TWI index as a baseline and show that ML beats it. If it doesn't, ship the index, which is still a defensible map.
- **DEM in flat terrain:** Klang's coastal plain is very flat, and GLO-30's vertical error (a few metres) is similar to the real relief. **Use FABDEM** (buildings and trees removed; the non-commercial licence is fine for the hackathon), and check HAND visually against the memorandum streets before training anything.
- **Sentinel-1 in towns:** radar change detection misses flooded built-up areas, because double-bounce off walls often *raises* backscatter. S1 points will fall mostly in open land, and the Dec 2021 event was a multi-day **riverine** flood, not a flash flood. Use S1 for river-flood validation only and give it a low weight, or cut it (it is already a Should).
- **Metric:** "≥ 60% of hotspots in risk 4–5 cells" can be gamed: if 50% of the area is 4–5, a random map scores about 50%. Report **AUC** and the **hit rate in the top 20% of area** (lift).

### B6. Tide should be a Must for Bandar Bukit Raja

Both headline events (4 Jun 2023 and 12 Nov 2024) coincided with high tide, and BBR drains toward the tidal Sg. Klang / Kapar. Tide is free to compute and deterministic, so you have it for every hour of history and the future without leakage.

**Options:** the Open-Meteo Marine API `sea_level_height_msl` at an offshore point near Port Klang (the docs warn that coastal accuracy is limited, and archive depth needs checking); a harmonic tide prediction (pyTMD / utide); or JUPEM's published Pelabuhan Klang tide tables. Feature: `tide_height_m` and `hours_to_high_tide`.

### B7. Smaller data-spec issues

- **Station radius:** `station_rain_1h_max` uses RF stations ≤ 10 km away, but **Kg. Perepat (Kapar)**, the station quoted in both headline events, is about **12 km** from my approximate BBR centre. Name the stations per township in `townships.yaml` instead of relying only on a radius.
- **Station thresholds are inconsistent in places.** Example: one Pahang station has warning 133.33 < alert 133.93. Check that normal < alert < warning < danger, and flag rows where it isn't.
- **Resolution inconsistency:** the PRD says ERA5-Land is "~11 km" and the spec says "~25 km". Open-Meteo documents ERA5 at 0.25° (~25 km), ERA5-Land at 0.1° (~9–11 km), and **ECMWF IFS at 9 km from 2017**. For 2017+ events, request `models=ecmwf_ifs` explicitly (or record which model `best_match` returned in `source_model`).
- **GPM IMERG** is worth moving up from optional for *training and validation*: 0.1° / 30-min rain shows thunderstorm peaks much better than ERA5. Its Early run has about a 4 h delay, so it can't drive the live nowcast; that's fine if it's used only to check rain bias.
- **Soil moisture** at 0–7 cm says little under concrete. Keep it, but expect it to rank low.
- **News scraping scope:** 10 townships × 4 keywords × 12 years through a search engine is slow and easily blocked. Use Google News RSS or GDELT queries by keyword and date, plus manual searches for the top 3 townships. Drop `air naik` (too noisy).
- **LLM extraction (T5):** require the prompt to return an **evidence quote** for every extracted number and time; reject any field without one. This keeps invented values out.
- **Weather warnings:** the API returns national text (today's warning was about marine waters). You need a parser for *land thunderstorm warnings* that name Selangor or the Klang / Petaling districts.

### B8. Better label sources you haven't listed

These are probably better than news, and two of them come through SDP:

1. **SDP township management complaint and incident logs.** Ask the mentors in week 1, not week 2. They are dated, street-level and owned by the sponsor.
2. **BBR residents' Facebook groups and the residents' council** that wrote the memorandum: dated photos and videos of floods at Jalan Makyong. This also gives you user interviews for the 10% evidence criterion.
3. **MBDK and Bomba Selangor Facebook posts** for call times.
4. **Resident flood reports in your own bot** (A-22): a `/report` button with location and photo. This is long-term label collection, and judges will see it as innovation.

## Scope, timeline and delivery blindspots

- **The proposal (23 Oct) is the gate.** Top 10 is chosen from it, so the next 9 days matter most. Assessors score feasibility and evidence, so show **working pieces**, not only mock-ups: the logger running, a first BBR HAND map with the (held-out) memorandum streets overlaid, and a rain chart of 4 Jun 2023 vs ordinary rainy days.
- **18 Musts is too many** for about 3 weeks of build time alongside classes. Proposed cuts are in A-19.
- **Pick one frontend now.** "React + Leaflet (or Streamlit)" will become both. Use whichever your frontend person already knows; a FastAPI + plain Leaflet page is enough for a demo.
- **The logger must not run on a laptop.** Laptops sleep. Use an always-on machine (a free-tier VM, a Raspberry Pi, or a teammate's desktop), with a GitHub Actions cron as backup. Scheduled workflows can run late, but at 15-minute polling that's acceptable.
- **Pitch-day failure modes:** venue Wi-Fi, Telegram delays, a sensor that won't connect. Record a **backup video** of the full demo and give replay mode an **offline flag** that serves cached data.
- **Sensor detail:** waterproof ultrasonic sensors (for example the JSN-SR04T) have a blind zone of about 20–25 cm. Mount the sensor high enough above the container or drain.
- **Team of 3 vs 5 roles:** if you register 3, merge "Data engineer + ML 2" and "Backend/IoT + Frontend".

## Product and pitch blindspots

- **You are pitching to the developer whose township floods.** The PRD opens with residents petitioning SDP. Frame it as *"SDP listened and acted"*, not *"SDP's township floods"*. The spec already warns about this, but the PRD's demo script opens with it.
- **The sales card may be a liability.** Showing a buyer "risk 4/5" is something sales won't want, and publishing it may create disclosure obligations. Suggestion: give the **buyer-facing card** "monitored 24/7, last event, mitigation in place (retention pond, drain upgrade)", and keep the **1–5 score internal** for ops and planning. Ask the mentors which they prefer.
- **WhatsApp vs Telegram:** most Malaysian residents use WhatsApp. Telegram is fine for the MVP; say in the pitch that production uses SDP App push or WhatsApp Business.
- **Language:** alerts in **BM and English** at least, since the memorandum and the local news are in BM.
- **Use a risk matrix, not a multiplication.** Replace `Susceptibility × P` with an explicit 5 × 4 lookup (susceptibility 1–5 × trigger level). It is easier to explain, tune and defend than a product of a score and a probability.
- **Differentiation statement:** have a one-line answer to "how is this different from Infobanjir / the MET app?". For example: *"They watch rivers and districts. We turn their data into a street-level alert, with an action, for the people who live there."*

## Revised success metrics

| Metric | Current target | Problem | Proposed |
| --- | --- | --- | --- |
| Event detection | ≥ 70% recall on held-out events | 3 events can't measure 70% | Leave-one-event-out on all dated events; report "X of N events flagged" with N |
| Nowcast lead time | Median ≥ 30 min before first report | Fine, but "first report" lags real onset | Keep; only hour-precision events; state that report time lags onset |
| Outlook lead time | Median ≥ 6 h | Not testable with stitched forecasts (C2) | Measure only with Previous Runs `previous_day1` (2024+) or your own logged forecasts |
| False alarms | ≤ 4 Warnings/month | Undefined unit; needs continuous data | ≤ 4 Warnings per township per month over a continuous 6-month rainy season |
| Map match | ≥ 60% hotspots in risk 4–5 | Can be gamed; circular (C4) | AUC ≥ 0.75 and top-20%-area hit rate ≥ 50%, on **held-out** BBR / memorandum streets |
| Freshness | Data ≤ 20 min old | Didn't detect a 2-year-stale API | Source timestamp ≤ 30 min, else the station is marked missing and shown on screen |

## Action list

**Owner** uses the PRD roles. **Claude** marks tasks Claude Code can do end to end; for the others, Claude can draft and you check. Effort: S ≤ half a day, M 1–2 days, L 3+ days.

### Now (14–16 Oct): unblock the data

| ID | Action | Fixes | Owner | Effort | Claude |
| --- | --- | --- | --- | --- | --- |
| A-01 | Rewrite T2: scrape **JPS Public Infobanjir** water-level and rainfall pages (Selangor) every 15 min; find the rainfall data URL with dev tools or Playwright; keep data.gov.my as fallback | C1 | Data eng | M | ✅ |
| A-02 | Add a **staleness check** to every source (source timestamp older than 2 h → missing + alert to the team); add it to the NFR table | C1 | Data eng | S | ✅ |
| A-03 | Run the loggers on an **always-on machine**, with a GitHub Actions cron as backup; also log the weather warnings (T3) and the **hourly Open-Meteo forecast** | C1, C2, C3 | Data eng | S | ✅ |
| A-28 | **Archive Infobanjir history now:** 15-min rain + water level for every station within 25 km of each township, Jan 2024 → today; polite rate (1 request every few seconds), cached, date-stamped under `data/raw/jps_hist/` | C3, C5 | Data eng | S | ✅ |
| A-04 | *(Optional, was critical.)* Email JPS for 15-min history **before 2024** (needed only for 4 Jun 2023, 2017 and 2021 events); ask SDP mentors to help speed it up | C3 | Team lead | S | Draft |
| A-05 | *(Optional.)* Request the data.gov.my token: it only raises the weather-API rate limit, and 1 call per 15 min is far below the no-token limit. Report the stale flood feed as a courtesy | C1 | Team lead | S | Draft |
| A-06 | Update the PRD and spec: replace the dead flood-API link; ING-1 source → Infobanjir; fix the ERA5 resolution wording; tide → Must for BBR | C1, B6, B7 | Any | S | ✅ |

### Before the proposal (17–23 Oct): show evidence, not only plans

| ID | Action | Fixes | Owner | Effort | Claude |
| --- | --- | --- | --- | --- | --- |
| A-07 | **First BBR terrain map:** FABDEM → HAND + TWI for BBR only; overlay the memorandum streets **not used in training**; one screenshot for the proposal | C4, Feasibility | GIS/ML 1 | M | ✅ |
| A-08 | **Rain evidence chart:** hourly rain (ECMWF IFS 9 km + IMERG) for 4 Jun 2023 and 12 Nov 2024 vs 10 ordinary rainy days in BBR; mark the JPS 60 mm / 2–4 h line | C5, B7 | ML 2 | S | ✅ |
| A-09 | Restructure the proposal around the **6 weighted criteria** and the page's **Mechanism / Enabler** pitch structure; add impact numbers | Judging fit | Pitch | M | Draft |
| A-10 | Reframe the story to "SDP listened and acted"; decide whether the **buyer card shows a score** (ask mentors; default to "monitored + mitigations") | Pitch | Pitch | S | Draft |
| A-11 | Post in BBR residents' FB groups / contact the residents' council: dated flood photos + 5–10 short interviews | B8, Evidence | Pitch | S | — |

### Data and map (24 Oct – 1 Nov)

| ID | Action | Fixes | Owner | Effort | Claude |
| --- | --- | --- | --- | --- | --- |
| A-12 | Change the trigger target to **district-level** "flash flood reported in district within N h"; widen labels to all Klang / Petaling / Shah Alam / KL flash floods 2017–2026 | B1 | ML 2 + Data eng | L | ✅ (scraping + LLM extraction with evidence quotes) |
| A-13 | **Day-level labels** for training; hour-precision events only for lead time; never infer the start hour from rain | B2 | ML 2 | S | ✅ |
| A-14 | Match training and live rain: **Historical Forecast API → training**, **live Forecast API → production**; ERA5/IMERG only to measure bias | C5 | ML 2 | S | ✅ |
| A-15 | **Rule layer** for station rain (JPS 60 mm / 2–4 h) + river (station alert/warning/danger); final level = max(ML level, rule level), and show which fired | C5, TRG-2 | ML 2 | S | ✅ |
| A-16 | Remove leaking features: historical `met_warning_active`, `tide_flag` from events, in-sample `susceptibility_score`; add **computed tide height** for all hours | B3, B6 | ML 2 | M | ✅ |
| A-17 | Susceptibility: dry samples **on roads / built-up areas**, spatial block CV, **HAND+TWI baseline**, all BBR points held out; report AUC + top-20% hit rate | B5, C4 | GIS/ML 1 | M | ✅ |
| A-18 | Outlook: use **Previous Runs API `precipitation_previous_day1`** (2024+) and your own logged forecasts; no stitched forecasts for Outlook features | C2 | ML 2 | S | ✅ |
| A-19 | **Cut scope:** map for BBR plus at most 2 more townships; drop ADM-1 and the QR code; S1 → appendix only; XGBoost only if the rule + logistic baseline is finished by 2 Nov | Feasibility | Team | S | — |

### Mentoring sprint (2–6 Nov)

| ID | Action | Fixes | Owner | Effort | Claude |
| --- | --- | --- | --- | --- | --- |
| A-20 | Ask mentors for **SDP incident / complaint logs**, drain specs, retention-pond plans; add the logs as labels | B8 | Team lead | S | — |
| A-21 | **Evaluation harness:** leave-one-event-out recall, lead time on hour-precision events, **continuous 6-month false-alarm run**, calibration plot; one honest failure case | B1, B4 | ML 2 | M | ✅ |
| A-22 | Add a `/report` button to the Telegram bot (location + photo → `events_candidates.csv`), with BM + EN messages | B8, Innovation | Backend | S | ✅ |
| A-23 | Sensor: mount above the 20–25 cm blind zone; MQTT → API; "confirmed" flag | ALR-4 | IoT | M | Code ✅ |

### Final build (7–11 Nov)

| ID | Action | Fixes | Owner | Effort | Claude |
| --- | --- | --- | --- | --- | --- |
| A-24 | Replay demo on a **held-out** event, using real logged or JPS-supplied series only; news readings as annotations. If the logger caught a live Klang flood, lead with it | C3 | Frontend + ML 2 | M | ✅ |
| A-25 | Replace `S × P` with an explicit **5 × 4 risk matrix**, shown in the ops detail view | Explainability | Backend | S | ✅ |
| A-26 | **Offline replay mode** + recorded backup video of the full demo | Pitch risk | Frontend | S | ✅ (offline mode) |
| A-27 | Final evaluation slide using the revised metrics table (report N, not just %) | Evidence | Pitch | S | Draft |

## Appendix: what I checked and how

| Claim | Check | Result |
| --- | --- | --- |
| Flood API is stale | `GET https://api.data.gov.my/flood-warning/` on 14 Oct 2026, 20:20 MYT | 1,276 stations; latest update month Feb 2024 (1,163), none in 2026; BBR-area stations all at 2024-02-23 |
| Flood API doc link | `developer.data.gov.my/realtime-api/flood-warning` | HTTP 404 |
| Infobanjir is live | `publicinfobanjir.water.gov.my/aras-air/data-paras-air/aras-air-data/?state=SEL…` | Readings timestamped 14/10/2026 19:30–20:00; Sg. Binjai @ Pekan Meru 3.21 m, thresholds 2.80 / 3.80 / 4.00 / 4.20 |
| JPS flash-flood rule of thumb | Infobanjir rainfall page text | "Convective rain more than 60 mm in 2 to 4 hours duration (typical) may cause flash floods." |
| Weather warning history | `GET api.data.gov.my/weather/warning/?timestamp_start=2015-01-01…&sort=warning_issue__issued` | Oldest result returned was issued 14 Oct 2026, i.e. current warnings only, so no usable history |
| Historical Forecast API method | Open-Meteo docs | "Each run's first few hours are stitched into a continuous hourly timeseries"; coverage starts about 2021–2022 |
| Previous Runs API coverage | Open-Meteo docs | Fixed lead offsets of 1–7 days; data from January 2024 (GFS from March 2021, JMA from 2018) |
| Historical Weather API models | Open-Meteo docs | ERA5 0.25° (1940+), ERA5-Land 0.1° (1950+), ECMWF IFS 9 km (2017+) |
| Judging criteria | simedarbyproperty.com/universityhackathon | Impact 25%, Innovation 20%, Feasibility 20%, Strategic fit 15%, Commercial 10%, Team/evidence/pitch 10% |

The station distances use an approximate BBR centre (3.06° N, 101.45° E); recompute them from the T1 polygon. I did not check the township list against SDP's site or verify the news sources.
