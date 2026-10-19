# Flood-Ready Township — Product Requirements Document

v3.1 · 14 Oct 2026 · @Filbert

> **v3.1 changes:** **ML-first trigger.** A gradient-boosted classifier trained on 2024–2026 JPS data pooled across all river stations predicts the chance that the river near each township crosses its warning level within 1–2 h. JPS's rules are a safety floor (the level is the higher of the two), and ML drives alerts only after passing an out-of-sample gate. Feasibility: `docs/ml-feasibility.md` (50 warning crossings at Sg Binjai; first model gave 90 vs 60 min median lead).
>
> **v3 changes:** the **full working MVP is due 23 Oct** (pitch deck ≤ 10 slides, 5-minute video or demo, prototype/code, optional documents), not a paper proposal. Timeline replaced by a dependency-ordered build plan for a team of five (`docs/plans/2026-10-14-mvp-build-plan.md`). No hardware or VPS before Top 10: the sensor is simulated (HTTP) and MVP hosting costs $0 (GitHub Actions tick, free Postgres, Cloudflare Pages). Priorities re-tiered: Must = in the 23 Oct submission.
>
> **v2.2 changes:** gridded model rain missed the 12 Nov 2024 storm almost completely (≤ 6.8 mm anywhere near Klang vs 79 mm at the Kg Perepat gauge), so the district model now uses **JPS station rain** (history from Jan 2024) and gridded forecasts are kept for the Outlook only. A one-hour intensity rule (JPS's own "heavy" / "very heavy" categories) has been added. Loggers and history archive are running.
>
> **v2.1 changes:**
> - Two **React + Leaflet** web apps replace the single dashboard: a **Resident app** (installable PWA with live push alerts, impact map, predicted time and reasons, and flood verification) and an **SDP Admin app** (statistics, auto-generated reports and street improvement suggestions).
> - Web Push is the main alert channel; Telegram becomes a fallback.
> - Resident verification feeds the benchmark and the training labels.
> - The sales card moves into the Admin app.
>
> **v2 changes:** live data now comes from JPS Public Infobanjir; a station rule layer has been added; the trigger predicts at district level; tide is a Must; the map is validated on held-out streets; the demo replays 12 Nov 2024 from real data; the metrics, the scope and the framing are revised. The reasons are in *Flood-Ready Township — Plan Review*.

## Overview

Flood-Ready Township predicts flash floods street by street, hours before they happen, and alerts residents on their phones. It is our entry for the [Sime Darby Property University Hackathon 2026](https://www.simedarbyproperty.com/universityhackathon) ("Township of Tomorrow"), **Planet track → Climate resilience**.

The system has four parts:

- a **flood susceptibility map** of where water collects, built once per township;
- a live **trigger layer** that predicts when flooding will happen. It refreshes every 15 minutes from JPS station rain and river levels, the rain forecast, MET warnings and the tide;
- **a water-level sensor** that confirms the prediction on the ground (simulated in the MVP; an ESP32 unit after Top 10);
- **resident verification**: residents tell us whether the flood really happened, which confirms alerts, measures our accuracy and becomes new training data.

The system has two web apps:

| App | Who | What it does |
| --- | --- | --- |
| **Resident app** (React + Leaflet, installable PWA) | Residents | Live push alerts; map of the impacted area; predicted time and reasons ("62 mm of rain in 2 h at Kg Perepat + high tide"); one-tap "Is it flooding here?" verification |
| **SDP Admin app** (React + Leaflet) | SDP township ops and management | Live ops map; statistics on recent warnings and accuracy; auto-generated reports; street improvement suggestions ("Jalan Makyong: drainage capacity review, 4 confirmed floods this year below the JPS 60 mm rain guide") |

**Why SDP should care:** 78% of Malaysian buyers weigh climate risk when buying, and floods are a top concern. A township that can show its streets are monitored, and that SDP acts on what it learns, gives buyers a reason to choose SDP.

| Milestone | Date |
| --- | --- |
| Registration closes | 21 Oct 2026 |
| **Submission: full working MVP**: pitch deck (≤ 10 main slides + appendix), 5-minute video or live demo link, prototype / code (GitHub), optional supporting documents | **23 Oct 2026, 11:59 pm** |
| Top 10 announced | 28 Oct 2026 |
| Mentoring sprint (add the hardware sensor and VPS) | 2–6 Nov 2026 |
| Final submission (improved build) | 11 Nov 2026 |
| Top 10 pitch day | 14 Nov 2026 |
| Final presentation & awards | 3 Dec 2026 |

## Problem statement

Bandar Bukit Raja residents say parts of their township flash-flood at least three times a year. Today's public warnings cannot tell them which street will flood, or when.

**Residents have asked for action.** In May 2024 the Bandar Bukit Raja residents' council handed a memorandum to the Selangor Menteri Besar. They said Phase 1 and 2, especially Jalan Makyong, had flash-flooded at least three times a year since December 2021, with water reaching kitchens and living rooms of homes worth over RM500,000. They asked Sime Darby Property, the Klang city council and JPS to add retention ponds at Jalan Makyong and Jalan Sumazau, and to enlarge drains along Persiaran Sungai Keramat and Persiaran Batu Belah ([Sinar Harian, 25 May 2024](https://www.sinarharian.com.my/article/666626/edisi/selangor-kl/penduduk-bandar-bukit-raja-hadap-banjir-kilat-tiga-kali-setahun)). This project is a way for SDP to show it listened and acted, and its Admin app turns flood data into the evidence for exactly those drainage decisions.

**A typical event (12 Nov 2024), from JPS's own 15-minute readings.** Rain at Kampung Perepat (Kapar) started at about 08:15. It reached 61.5 mm by 09:00 and 79 mm by 10:15. Sungai Binjai at Pekan Meru rose from 2.94 m at 08:00 to 4.21 m, its danger level, at 10:00, and peaked at 4.26 m at 11:45 ([JPS Public Infobanjir](https://publicinfobanjir.water.gov.my/)). That morning, Persiaran Sungai Keramat, Persiaran Batu Belah and five other Klang roads flooded 0.1–0.4 m, and the heavy rain coincided with a high tide ([RTM](https://berita.rtm.gov.my/nasional/senarai-berita-nasional/senarai-artikel/banjir-kilat-tujuh-laluan-di-klang-dinaiki-air/)). The 4 June 2023 event followed the same pattern: 98.5 mm at Kg Perepat, Sg Binjai at 4.38 m, high tide, and 50–100 homes flooded ([Sinar Harian / Bernama](https://www.sinarharian.com.my/article/262088/berita/semasa/rancangan-tebatan-banjir-di-klang-dilaksana-segera---nik-nazmi)).

**Why current warnings fall short.**

- JPS telemetry watches **rivers**, not housing-estate streets. Public Infobanjir reports river levels and rainfall per station, not per street.
- Flash floods hit fast. Selangor Bomba says some hotspots flood after only 1–2 hours of rain ([Kosmo](https://www.kosmo.com.my/?p=229246)), and JPS states that convective rain of more than 60 mm in 2–4 hours may cause flash floods.
- Residents learn about floods from social media or rising water, not from a timed, street-level alert.
- Nobody records **which streets actually flooded, and after how much rain**, so drainage upgrades are argued from complaints rather than data.

**Why it matters commercially.** Experts say floods can erode property values by around 30%, and buyers avoid "red zones" ([Bernama](https://bernama.com/en/news.php?id=2141696)). 78% of Malaysians weigh climate risk when buying ([PropertyGuru H1 2026](https://theiskandarian.com/propertyguru-sustainability-climate-risk-and-liveability-now-shape-how-malaysians-think-about-home/)).

**Problem statement:** *How might SDP give every resident a street-level flash-flood warning early enough to act, and turn what residents report into evidence for where to fix drainage, using only open data and minimal hardware?*

## How this plan scores against the judging criteria

The deck, the video and the pitch follow the official criteria and the page's **Mechanism / Enabler** structure.

| Criterion | Weight | Our answer |
| --- | --- | --- |
| Impact & Sustainability Value | 25% | Residents of BBR Phase 1–2 get street-level warnings with an action; SDP gets data-backed drainage priorities. Impact is put in numbers: homes covered, minutes of warning, floods confirmed, streets prioritised |
| Innovation & Differentiation | 20% | JPS and MET watch rivers and districts; we turn their data into a street-level alert with an action. An ML trigger trained on 2.5 years of JPS river data gave about 30 min more warning than rain rules in a first test, with JPS's own thresholds as a safety floor. Residents verify alerts, so the system measures and improves its own accuracy. The admin side turns floods into improvement suggestions |
| Feasibility & Deliverability | 20% | Open data only; working MVP in a public repo; live loggers running; replay on real JPS readings; two web apps sharing one API; $0 hosting |
| Strategic Fit & Theme Relevance | 15% | Planet → climate resilience, in an SDP township, answering a residents' memorandum |
| Commercial & Value Multiplication | 10% | Ops and drainage-planning value for SDP, "monitored street" sales card, one pipeline for every SDP township; cost per township |
| Team, Evidence & Pitch Quality | 10% | Buyer survey (30–50), 5–10 BBR resident interviews, an evaluation that reports N as well as %, and a live verification loop |

## Goals, non-goals and success metrics

The MVP must prove one thing: open data can warn an SDP street about a flash flood early enough for residents to act, and residents' answers can show whether it worked.

**Goals**

1. Give residents a live, street-level flood warning with an **Outlook** (6–24 h ahead) and a **Nowcast** (0–2 h ahead), showing the impacted area, the expected time and the reasons.
2. Let residents verify whether a flood really happened, and use that as both a benchmark and new training data.
3. Give SDP admins statistics, reports and street improvement suggestions built from the collected data.
4. Show the whole system working end to end on a replay of a real past flood that the model never trained on.

**Non-goals (MVP)**

- No hydraulic or drain-network modelling. Improvement suggestions are screening prompts for engineers, not designs.
- No dense sensor network and no hardware in the MVP: one simulated sensor; one ESP32 unit after Top 10.
- No integration with the real SDP App. The Resident app is a stand-alone PWA that could later be embedded.
- No official warning role; JPS/MET/NADMA remain the authority.
- No council access (cut from scope).
- Susceptibility map for Bandar Bukit Raja plus at most two other SDP townships; the rest only after the final submission.

**Success metrics.** All are measured on events or streets the model did not train on.

| Metric | MVP target | How measured |
| --- | --- | --- |
| Event detection | Report "X of N events flagged Warning or higher"; target ≥ 70% | Leave-one-event-out over all dated events |
| ML vs official rules | ML trigger passes the gate: detects at least as many river crossings as the Watch rule with no more false alarms, or the same number with ≥ 20 min more lead and ≤ 1.2× false alarms | Time-blocked out-of-sample evaluation over 2024–2026 (first spike: 23/50 detected by both, 90 vs 60 min lead) |
| Nowcast lead time | Median ≥ 30 min before first report | Hour-precision events only. Report time lags real onset, and we say so |
| Outlook lead time | Median ≥ 6 h before first report | Only with real day-ahead forecasts: Open-Meteo Previous Runs (2024+) or our own logged forecasts |
| False alarms | ≤ 4 Warning alerts per township per month with no flood | Continuous hour-by-hour run over a 6-month rainy season; each Warning checked against news |
| Map skill | AUC ≥ 0.75; top 20% of area holds ≥ 50% of held-out flood points | Map validation run trained **without** BBR labels, scored on BBR and memorandum streets |
| Pipeline freshness | Source timestamp ≤ 30 min old, otherwise the station is marked missing on screen | Source timestamps vs our clock |
| Alert delivery | Push received ≤ 2 min after a level change | Server send time vs device receipt in tests |
| Live benchmark (after launch) | Alert confirmation rate, missed-flood count and live lead time, shown in the Admin app | Resident "Yes / No" answers and unwarned reports (see *Live benchmark*) |

Targets are starting assumptions for the pitch; we will report the real numbers we get.

## Users and personas

Four users share one data pipeline; residents and SDP ops are the MVP priority.

| Persona | Who | Main need | What they get | App | MVP priority |
| --- | --- | --- | --- | --- | --- |
| Resident | Homeowner or tenant in an SDP township (e.g. Bandar Bukit Raja Phase 1) | Know early if *my street* will flood, when, and why, so I can move my car and lift belongings | Push alert in BM or English; map of impacted streets; expected time window; reasons; what to do; one-tap verification | Resident | Must |
| SDP township ops | SDP township management / facilities team | See where risk is rising and act; know which streets need work | Live ops map, statistics, reports, improvement suggestions, feedback review, ops notes | Admin | Must |
| SDP management / planning | Township GM, planning and engineering | Evidence for drainage and retention-pond investment; answers to residents' councils | Monthly report, street ranking, suggestion list with evidence | Admin | Must |
| SDP sales team + buyer | Sales gallery staff and prospective buyers | A credible answer to "does this street flood, and what is being done?" | "Monitored 24/7" street card with last event and mitigations; the 1–5 score stays internal unless SDP decides otherwise | Admin (card view) | Could |

## Solution overview

A street's flood level combines where water collects (a fixed susceptibility score) with how likely flooding is right now (a live trigger level), using an explicit risk matrix. The sensor and resident verification confirm it on the ground.

1. **Susceptibility map (where).** Built once per township on a 30 m grid from FABDEM ground height (buildings and trees removed), terrain features (slope, HAND, TWI, flow accumulation), distance to rivers and coast, and hard surfaces. A HAND + TWI index is the baseline; an ML classifier replaces it only if it scores better on held-out streets. Output: score 1–5 per cell, rolled up per street.
2. **Trigger layer (when): ML-first, with a safety floor.** Refreshes every 15 minutes.
   - **ML trigger** (gradient-boosted trees, scikit-learn): trained on 2024–2026 JPS data pooled across all river stations in Selangor and KL. Predicts the probability that the river near each township crosses its warning level within 1–2 h. The labels come from the river data itself, so there are many events to learn from (50 warning crossings at Sg Binjai alone). Features: river level against its thresholds, rises, rain within 10–25 km, tide.
   - **Safety floor: station rules** using JPS's own figures. Rain ≥ 31 mm in 1 h (JPS "heavy") or ≥ 40 mm in 2–4 h → Watch; > 60 mm in 1 h or ≥ 60 mm in 2–4 h → Warning. River alert / warning / danger → Watch / Warning / Danger.

   The trigger level is the **higher** of the ML level and the rule level. ML may raise a level but never lowers an official threshold, and every alert records which input fired. ML drives alert levels only once it passes an out-of-sample gate against the rules (see *Success metrics*). Until then its probability is shown, but the rules decide.
3. **Risk matrix.** Susceptibility (1–5) × trigger level (Normal / Watch / Warning / Danger) → street level, from a published 5 × 4 lookup table that is tuned on replay.
4. **Expected time.** Every alert carries a **time window**, never an exact minute.
   - **Nowcast:** the window comes from the typical lag between the rule firing and flooding on past events. On 12 Nov 2024 the rain rule fired at 09:00 and the river reached danger at 10:00. The window is shifted by the next high tide.
   - **Outlook:** the window is the forecast peak-rain hours, overlapped with high tide.
5. **Reasons.** Every alert lists its drivers in plain language, ranked by contribution. For example: "Heavy rain: 62 mm in 2 h at Kg Perepat", "Sg Binjai rising, 0.2 m below danger", "High tide at 11:40", "More heavy rain forecast in the next 3 h".
6. **Ground truth.** A water-level sensor reports over HTTP. The MVP uses a simulated sensor, clearly labelled; after Top 10 an ESP32 + waterproof ultrasonic sensor over a drain posts to the same endpoint. Residents answer "Is it flooding here?" on alerts and can report floods we didn't warn about. Sensor and resident answers mark alerts *confirmed* or *not confirmed*, feed the live benchmark and, once reviewed, become training labels.
7. **Improvement suggestions.** A rule-based engine in the Admin app reads confirmed floods, the rain at which each street flooded, tide timing, susceptibility and missed reports, and proposes actions per street with the evidence behind each one (see *Improvement suggestion rules*).

**Two alert horizons**

| Alert | Lead time | Driven by | Confidence | Resident message (example) |
| --- | --- | --- | --- | --- |
| Outlook | 6–24 h | Day-ahead rain forecast + MET thunderstorm warning for the district + high-tide timing + susceptibility | Medium | "Flash-flood risk in Bukit Raja Phase 1 this evening, 5–8 pm (heavy rain forecast near high tide). Park on higher ground tonight." |
| Nowcast | 0–2 h | ML trigger + station rain and river rules (safety floor) + susceptibility (+ sensor and resident confirmations) | High | "Flooding likely at Jalan Makyong between 9:30 and 10:30: 62 mm of rain in 2 h at Kg Perepat, Sg Binjai rising, high tide 11:40. Move your car now." |

**Alert levels per street:** Normal → Watch → Warning → Danger, the same four levels JPS uses for rivers, so residents and authorities read them the same way.

### Live benchmark (resident verification)

Every alert becomes a measurable prediction.

| Resident input | When | Counts as |
| --- | --- | --- |
| "Yes, flooding here" (+ depth: ankle / knee / above knee, optional photo) | Prompted with each Warning/Danger push (not with Watch), and on the street page during an active alert | Confirmation; first "Yes" time gives the live lead time |
| "No flooding here" | Same | Evidence of a false alarm |
| "Not sure" | Same | Ignored in scoring |
| "Report a flood" (no alert active) | Any time | **Missed flood**: the most important signal for improving recall |

**Scoring rules (starting values):**

- An alert is **confirmed** if the sensor rises above its threshold, or if at least 2 distinct devices say "Yes" (1 is enough with a photo) within 3 h of the alert.
- An alert is **not confirmed** if at least 3 devices say "No" and none say "Yes".
- An alert with no answers stays **unverified**, and is never counted as a false alarm.
- A **missed flood** is a report backed by 2 devices, or 1 with a photo, on a street that had no Warning or Danger in the previous 3 h.

**Anti-abuse:**

- One answer per device per alert.
- Answers carry the device's location if the resident allows it. Answers from more than 1 km away are weighted down.
- Admins can mark any report spam.

Reviewed confirmations and missed floods are added to the training labels with `source_type = app_report`.

### Improvement suggestion rules

Suggestions are generated per street over a chosen period (default: last 12 months). Each shows its evidence, a priority, and the note "Screening suggestion for SDP engineers; site survey needed". Thresholds are starting values that ops can adjust.

| ID | Pattern in the data | Suggestion | Evidence shown |
| --- | --- | --- | --- |
| SUG-1 Drainage capacity | ≥ 3 confirmed floods, and median station rain at flood onset **below** the JPS 60 mm / 2–4 h guide | "Street A needs a drainage capacity review / upgrade: it floods with less rain than the JPS guide." | Flood dates, rain at each onset, comparison with neighbouring streets |
| SUG-2 Tidal backflow | ≥ 2 confirmed floods and ≥ 70% of them within ±2 h of high tide | "Check outfall flap gates / backflow valves draining Street A." | Flood times vs tide curve |
| SUG-3 Blockage / maintenance | Street floods while neighbouring streets with similar susceptibility and rain don't; or floods this year ≥ 2 × last year | "Inspect and clear drains and culverts on Street A before the monsoon." | Neighbour comparison, year-on-year count |
| SUG-4 Storage / retention | Cluster of ≥ 3 adjacent high-susceptibility (4–5) streets with repeated confirmed floods | "Area around Streets A–C is a candidate for retention / on-site storage." | Cluster map, total flood-days, homes nearby |
| SUG-5 Pre-event readiness | Street reached Warning or Danger ≥ 5 times | "Add Street A to the pre-storm drain-clearing and staff deployment list." | Alert count and dates |
| SUG-6 Monitoring gap | ≥ 2 missed floods (reports without an alert) | "Our model under-predicts Street A: add a sensor or review its susceptibility score." | Missed-flood reports |
| SUG-7 Data health | A named station stale > 10% of the period | "JPS station X is often offline; consider a backup station or our own rain gauge." | Stale-hours chart |

Priority = High if the street had confirmed floods affecting homes (depth "knee" or above, or homes affected in reports), Medium for road-only flooding, Low for data and monitoring suggestions.

## Functional requirements

**Priority:** Must = in the 23 Oct submission; Should = before 23 Oct if time allows, otherwise for the 11 Nov final; Could = after Top 10. The MVP has 37 Must requirements across seven modules. Who builds what, in which order and with which acceptance tests is in the *MVP Build Plan* (`docs/plans/2026-10-14-mvp-build-plan.md`).

| ID | Module | Requirement | Priority |
| --- | --- | --- | --- |
| ING-1 | Ingestion | Scrape JPS Public Infobanjir live water-level and rainfall tables for Selangor (and KL) every 15 min; keep stations within 25 km of the pilot township plus the stations named in `townships.yaml`; store every reading with source timestamp | Must |
| ING-2 | Ingestion | Poll the data.gov.my Weather Warning API every 15 min; store all warnings; parse land thunderstorm / heavy-rain warnings that name Selangor or the township's district | Must |
| ING-3 | Ingestion | Fetch the Open-Meteo hourly forecast (precipitation, precipitation probability) for each township centroid every hour, and **store every forecast run** to build our own forecast archive | Must |
| ING-4 | Ingestion | Sensor readings via HTTP `POST /sensor/readings` (≤ 1 per minute, device ID, `simulated` flag). MVP: simulated sensor, labelled on screen; ESP32 hardware after Top 10 | Must |
| ING-5 | Ingestion | Treat `-9999`, station status OFF and repeated 5-min filler rows as missing, never as zero | Must |
| ING-6 | Ingestion | **Staleness check:** if a source timestamp is more than 2 h old, mark the station missing, lower alert confidence and notify the team | Must |
| ING-7 | Ingestion | **Archive JPS history** (15-min rain and water level, Jan 2024 → today) for all stations within 25 km of each township, done once with polite rate limits | Must |
| ING-8 | Ingestion | Compute **tide height** for Port Klang for every hour (past and next 48 h) | Must |
| MAP-1 | Susceptibility | Compute terrain features per 30 m cell from FABDEM (elevation, slope, HAND, TWI, TPI, flow accumulation, distance to river and coast) plus impervious share and building density | Must |
| MAP-2 | Susceptibility | HAND + TWI baseline index (1–5) per street (Must). ML classifier with dry samples along roads and spatial block cross-validation, kept only if it beats the baseline (Should) | Must |
| MAP-3 | Susceptibility | Roll cell scores up to each OSM street segment (max and mean) | Must |
| MAP-4 | Susceptibility | Validation run trained without BBR labels, scored on BBR and memorandum streets; the pitch map comes from this run | Must |
| MAP-5 | Susceptibility | Sentinel-1 December 2021 flood extent, shown as river-flood context only | Could |
| TRG-1 | Trigger | Build features every 15 min: station rain 1 h / 2 h / 3 h / 4 h / 24 h / 72 h (per station and district max), river level vs its thresholds and trend, forecast rain next 3/6/12 h (Outlook and display), tide height and hours to high tide, MET warning flag, hour of day | Must |
| TRG-2 | Trigger | **Safety floor:** station rules using JPS's own figures: **Watch** at ≥ 31 mm in 1 h (JPS "heavy") or ≥ 40 mm in 2–4 h; **Warning** at > 60 mm in 1 h (JPS "very heavy") or ≥ 60 mm in 2–4 h (JPS flash-flood guide); river alert / warning / danger mapped to Watch / Warning / Danger. Starting values, tuned per township on 2024+ events | Must |
| TRG-3 | Trigger | **ML trigger** (gradient-boosted trees) trained on 2024–2026 JPS data pooled across all river stations: probability that the river near each township crosses its warning level within 1–2 h. Level = max(ML, rules). Drives alert levels once it passes the out-of-sample gate; always shown as the flood probability | Must |
| TRG-4 | Trigger | Combine trigger level and susceptibility through the 5 × 4 risk matrix into a street level; record which input fired | Must |
| TRG-5 | Trigger | River-level forecast curve (quantile model, p50/p90, 1–2 h ahead) on Resident and Admin charts | Should |
| TRG-6 | Trigger | Every alert carries an **expected time window** (Nowcast: from rule-to-flood lag on past events, shifted by tide; Outlook: forecast peak-rain hours overlapped with high tide) and **ranked plain-language reasons** | Must |
| TRG-7 | Trigger | Street flash-flood classifier trained on news and resident labels (township-day); ships only with ≥ 20 labelled events and if it beats TRG-3 | Should |
| ALR-1 | Alerts | **Web Push** (PWA, service worker, VAPID) to residents subscribed to a street when it reaches Watch, Warning or Danger (`alerts.push_levels`; team decision 17 Oct 2026): level, street, time window, top reasons, action, link to the street page, and "Is it flooding here?" buttons. Text in BM or English | Must |
| ALR-2 | Alerts | Outlook push when 6–24 h risk is high | Must |
| ALR-3 | Alerts | No repeat alert for the same street within 60 min unless the level rises; "All clear" push when it returns to Normal, but not before the alert is `alerts.clear_after_min` (60 min) old; the alert stays active until then | Must |
| ALR-4 | Alerts | Alert status (confirmed / not confirmed / unverified) from the sensor and resident answers, using the *Live benchmark* rules; "Confirmed by neighbours" follow-up push | Must |
| ALR-5 | Alerts | Telegram bot fallback with the same messages, for iPhone users who don't install the PWA | Could |
| RES-1 | Resident app | Onboarding without an account: choose street(s) by search or by tapping the map, choose BM/EN, allow notifications; prompt to install as an app (needed for push on iPhone) | Must |
| RES-2 | Resident app | Live map (Leaflet): streets coloured by level, the impacted area highlighted, my streets pinned, JPS stations with latest readings | Must |
| RES-3 | Resident app | Street page: current level and confidence, expected time window, ranked reasons, next 12 h rain chart, tide, what to do, data time and the "JPS/MET/NADMA are official" footer | Must |
| RES-4 | Resident app | **Verify:** "Is it flooding here?" Yes / No / Not sure, depth (ankle / knee / above knee), optional photo, optional location; one answer per device per alert | Must |
| RES-5 | Resident app | **Report a flood** at any time when no alert is active (location, depth, optional photo), recorded as a possible missed flood | Must |
| RES-6 | Resident app | Alert history for my streets, with each alert's outcome (confirmed / not confirmed / unverified) | Should |
| ADM-1 | Admin app | Login for SDP staff (email + password; roles: admin, viewer) | Must |
| ADM-2 | Admin app | Live ops map: all streets by level, stations (stale greyed), sensor, resident answers and reports as pins, replay slider | Must |
| ADM-3 | Admin app | Street detail: rain / river / sensor charts with threshold lines, drivers, risk-matrix cell, alert and answer history, ops notes (e.g. "drain cleared") | Must |
| ADM-4 | Admin app | **Statistics** for a chosen period: alerts by level, week and street; confirmation rate; false alarms; missed floods; median live lead time; top flooded streets; rain at flood onset; station health; subscribers and answer rate | Must |
| ADM-5 | Admin app | **Report**: weekly / monthly report page built from collected data (summary, events, performance, top streets, suggestions, data health); exported to PDF by printing. Every number comes from the database | Must |
| ADM-6 | Admin app | **Improvement suggestions** per street from rules SUG-1 to SUG-7, each with evidence and priority; ops can mark a suggestion accepted, dismissed or done, with a note | Must |
| ADM-7 | Admin app | Review queue for resident reports and photos: mark valid or spam; valid reports go into the training labels | Should |
| ADM-8 | Admin app | Optional LLM-written summary paragraph in the report, generated only from the computed statistics and clearly labelled | Could |
| ADM-9 | Admin app | Sales street card view (monitored badge, last event, mitigations), printable | Could |
| DEM-1 | Demo | Replay mode over **12 Nov 2024** using archived JPS 15-min data at accelerated speed, driving both apps; must run **offline** from cached data | Must |
| DEM-2 | Demo | Evaluation report: leave-one-event-out detection, lead time, continuous false-alarm run, map skill on held-out streets, one honest failure case | Must |
| DEM-3 | Submission | **5-minute video** of the working MVP (replay with push, verify, Admin statistics and suggestions, live mode); link in README | Must |
| DEM-4 | Submission | **Pitch deck**, ≤ 10 main slides + appendix | Must |
| DEM-5 | Submission | **Public GitHub repo** with README: what it is, screenshots, video link, setup in ≤ 5 commands, data credits | Must |
| DEM-6 | Submission | Live demo links (Resident app, Admin app, API) | Should |

## Data sources and ML approach

All inputs are open data; the full schema and scraping plan are in *Flood-Ready Township — Training Data Spec*.

| Data | Source | Used for | Notes |
| --- | --- | --- | --- |
| River level, rainfall per station (5–15 min), live | [JPS Public Infobanjir](https://publicinfobanjir.water.gov.my/) | Rule layer, both apps | Live HTML tables; includes normal/alert/warning/danger thresholds |
| River level, rainfall per station, history | JPS Public Infobanjir graph data endpoints | Rule tuning, replay, evaluation, rain-at-onset statistics | Rain from about Jan 2024, water level from about Apr 2024; undocumented, so archived once |
| River level (old feed) | data.gov.my Flood Warning API | Fallback only | Frozen since Feb 2024; kept behind the staleness check |
| Weather warnings | [data.gov.my Weather API](https://developer.data.gov.my/realtime-api/weather) (MET) | Outlook, reasons | Current warnings only, no history, so we log them ourselves |
| Hourly rain forecast | [Open-Meteo Forecast API](https://open-meteo.com/en/docs) | Outlook, 12 h rain chart | Free tier is non-commercial; we log every run (4 models) |
| Gridded rain, history | [Open-Meteo Historical Forecast API](https://open-meteo.com/en/docs/historical-forecast-api) | Bias study only | **Not a model input:** on 12 Nov 2024 the best of 8 gridded sources showed ≤ 6.8 mm in 06:00–14:00 anywhere in a 30 km box around Klang, while the Kg Perepat gauge recorded 79 mm |
| Day-ahead forecasts, history | [Open-Meteo Previous Runs API](https://open-meteo.com/en/docs/previous-runs-api) | Outlook evaluation | `previous_day1` = forecast made 24 h earlier; from Jan 2024 |
| Rain bias check | Open-Meteo archive (ECMWF IFS 9 km, 2017+) and NASA GPM IMERG (0.1°, 30 min) | Evaluation only | Shows how much gridded rain underestimates station peaks |
| Tide | Harmonic prediction for Port Klang (pyTMD / utide) or JUPEM tide tables; Open-Meteo Marine as a cross-check | Trigger, time window, SUG-2 | Computed for every hour |
| Ground height | FABDEM (hackathon); Copernicus GLO-30 (production) | Susceptibility | 30 m |
| Streets, rivers, buildings | OpenStreetMap | Susceptibility, street roll-up, map layers | |
| Land cover | ESA WorldCover 10 m | Susceptibility | Impervious share |
| Flood labels | News, Bomba statements, JPS/Bomba hotspot lists, SDP incident logs (requested), BBR residents' groups, **app reports and verifications** | Training, validation, live benchmark | Every label hand-checked, with an evidence quote |

**Models**

- **Susceptibility:** HAND + TWI index as the baseline; Random Forest / XGBoost on terrain features if it beats the baseline under spatial cross-validation ([ISPRS 2022](https://isprs-archives.copernicus.org/articles/XLVI-4-W3-2021/305/2022/)).
- **Trigger (ML-first):** a gradient-boosted classifier on JPS station data, pooled across all river stations (Jan 2024 →), predicts river warning crossings 1–2 h ahead. Labels come from the river data itself, and the model is validated on time-blocked folds (12 Nov 2024 always held out). It is compared against the JPS rain and river rules, which stay as a safety floor. Gridded model rain is excluded because it misses short tropical storms. Street-level flash-flood labels from news and residents feed a second, optional classifier (TRG-7). Feasibility: `docs/ml-feasibility.md`.
- **No leaking features:** historical MET warnings, tide flags taken from news, and in-sample susceptibility scores are not used for training.
- **Learning from residents:** reviewed app confirmations and missed floods are added to the labels before each retrain; the street rain-at-onset statistics also tune the station rule thresholds per township.
- **Explainability:** every alert shows its ranked reasons and which input fired.

## System architecture and tech stack

Live feeds pass through one ingest layer into a database. The ML trigger, the rule floor and the susceptibility map meet in one risk matrix. Both apps read through one FastAPI service, and resident answers flow back into the database as benchmark data and labels.

```text
 JPS Infobanjir (live + history) ─┐
 MET warnings (data.gov.my) ──────┤               ┌─ ML trigger ─────┐
 Open-Meteo forecast ─────────────┼─► Ingest ─► DB┤                  ├─► Risk matrix + time window + reasons
 Tide (computed) ─────────────────┤   (15 min)    └─ Rules (floor) ──┘              │
 Sensor (simulated, HTTP) ────────┘        ▲          Susceptibility map ───────────┤
                                           │          (FABDEM + OSM, once)          ▼
                                           │                                     FastAPI ──► Web Push (+ Telegram fallback)
                                           │                                        │
                    answers, reports ──────┴──── Resident app (React + Leaflet PWA) ◄┤
                                                 Admin app (React + Leaflet) ◄──────┘
                                                   stats · reports · suggestions
```

The GIS path runs once per township; everything else refreshes every 15 minutes. The loggers run on an always-on machine, never a laptop.

| Layer | Choice | Why |
| --- | --- | --- |
| Ingest | Python. MVP: GitHub Actions cron every 15 min (`scripts/tick.py`: ingest → engine → push). After Top 10: systemd on a VPS | No always-on machine needed for the MVP |
| Sensor | MVP: `scripts/sim_sensor.py` posting to the API, labelled "simulated". After Top 10: ESP32 + waterproof ultrasonic sensor (mounted above its ~20–25 cm blind zone) posting over HTTPS | No hardware needed for the MVP |
| Storage | Supabase Postgres (free) in the MVP; SQLite for development and tests (SQLAlchemy Core keeps both working); Postgres on the VPS later | One database for readings, streets, alerts and answers |
| GIS | rasterio, WhiteboxTools or pysheds, GeoPandas | HAND, TWI, flow accumulation without hydrology expertise |
| Tide | pyTMD or utide | Deterministic tide for any hour |
| ML | scikit-learn `HistGradientBoostingClassifier` (ML trigger), quantile regressor (forecast curve, Should); joblib artifact + model card | Fast on a CPU, handles missing readings, explainable through its drivers |
| API | FastAPI: REST for both apps, Server-Sent Events for live map updates, offline replay mode from cached data | One service for both apps |
| Push | Web Push with VAPID keys (`pywebpush` on the server, service worker in the Resident app); Telegram Bot API as fallback | Free; works on Android browsers and on iPhone once the PWA is added to the Home Screen (iOS 16.4+) |
| Frontend | **React + Leaflet** (react-leaflet), Vite. One repo, two apps: `apps/resident` (PWA) and `apps/admin`, sharing `packages/shared` (map layers, level colours, API client, BM/EN strings) | Shared map components avoid building everything twice |
| Charts | One React chart library shared by both apps | Rain, river, tide and statistics charts |
| Auth | Residents: no account (random device ID); admins: email + password with roles | PDPA-light for residents; access control for SDP data |

### Deployment and keeping the loggers running

| Phase | Where it runs | How the loggers keep running |
| --- | --- | --- |
| **MVP (now → 23 Oct, $0)** | GitHub Actions cron every 15 min runs `scripts/tick.py` (ingest → engine → push); Supabase Postgres (free); FastAPI on a free host, or locally with a tunnel for the demo; both apps on Cloudflare Pages | Actions cron (public repo, free). The laptop logger stays on as a backup, and a JPS history top-up backfills any gaps |
| **After Top 10** | VPS (`deploy/README.md`): loggers, API, Postgres; apps stay on Cloudflare Pages; Cloudflare Worker watchdog | systemd `Restart=always` + nightly archive timer; watchdog alerts the team if logging stops for more than 30 min |

The first DevOps check is whether JPS Infobanjir answers requests from GitHub's runners outside Malaysia. If it doesn't, the tick runs on a teammate's always-on PC instead. GitHub Actions cron can start a few minutes late, which is acceptable for the MVP; the demo uses replay. MET warnings and forecasts can't be backfilled, so gaps in those stay gaps.

## User flows and screens

### Resident app (React + Leaflet PWA)

**Resident flow**

1. Resident opens the link or scans a QR code in the township, picks BM or English, chooses their street(s) on the map or by search, and allows notifications. iPhone users are guided to "Add to Home Screen" first.
2. An **Outlook** push arrives the day before, or that afternoon, when 6–24 h risk is high: area, time window, reasons.
3. A **Watch** push arrives when the street reaches Watch (rain building, river rising), then a **Nowcast** push when it reaches Warning: street, time window, top reasons, action ("Move your car to \[nearest higher car park set by SDP ops\]") and "Is it flooding here? Yes / No".
4. Tapping the push opens the street page: map of the impacted area, level, time window, ranked reasons, next 12 h rain, tide, what to do.
5. During and after the event, the resident answers Yes / No / Not sure, adds depth and optionally a photo.
6. A "Confirmed by neighbours" or "All clear" push follows.
7. At any time without an alert, the resident can **Report a flood**.

**Resident screens**

| Screen | Key elements |
| --- | --- |
| Onboarding | Language, street picker (map + search), notification permission, install prompt, privacy note |
| Home map | Leaflet map: streets by level, impacted area, my streets pinned, stations; banner for any active alert |
| Street page | Level badge + confidence, expected time window, ranked reasons, 12 h rain chart, tide, what to do, data time, official-source footer |
| Verify sheet | Yes / No / Not sure, depth picker, photo, location toggle |
| Report a flood | Location (map pin / GPS), depth, photo |
| My alerts | History with outcomes (Should) |

### SDP Admin app (React + Leaflet)

**SDP ops and management flow**

1. Admin logs in and sees the **live ops map**: every street by level, stations (stale greyed), sensor, resident answers and reports.
2. Admin clicks a red street: charts with thresholds, drivers, risk-matrix cell, alert and answer history; adds an ops note.
3. Admin opens **Statistics** for the last week, month or year: alerts, confirmations, false alarms, missed floods, lead time, top flooded streets, rain at flood onset, station health.
4. Admin opens **Reports**, picks a month and prints the report to PDF for the township GM or the residents' council.
5. Admin opens **Suggestions**: a ranked list per street with evidence, and marks each one accepted, dismissed or done.
6. Admin reviews resident reports and photos (Should).

**Admin screens**

| Screen | Key elements |
| --- | --- |
| Login | Email + password |
| Ops map | Street layer, stations, sensor, answer/report pins, filter by level, replay slider |
| Street detail | Rain / river / sensor / tide charts with thresholds, drivers, matrix cell, alert + answer history, notes, suggestions for this street |
| Statistics | KPI tiles (alerts, confirmation rate, missed floods, median lead time); charts by week and street; rain-at-onset chart; station health; period filter |
| Reports | Weekly / monthly report, print to PDF; optional labelled LLM summary (Could) |
| Suggestions | Ranked list (priority, street, suggestion, evidence, status), map view of streets with suggestions |
| Review queue | Reports and photos to mark valid or spam (Should) |
| Street card | Sales view: monitored badge, last event, mitigations (Could) |

## Non-functional requirements

The system must be fresh, honest about uncertainty, and safe with resident data.

| Area | Requirement |
| --- | --- |
| Freshness | Source timestamps ≤ 30 min old, otherwise the station is shown as stale; push sent ≤ 2 min after a level change |
| Availability | Loggers run as a systemd service (`Restart=always`, start at boot) with a nightly archive top-up that backfills JPS gaps; an external watchdog alerts the team if logging stops for more than 30 min. Ingest jobs retry 3× with backoff; a missing or stale source lowers the level's confidence and is never silently treated as Normal |
| Mobile-first | Resident app works on a 360 px wide phone screen, loads in ≤ 3 s on 4G, and shows the last known status offline (service worker cache) |
| Language | Resident app and push text in BM and English; Admin app in English |
| Scraping etiquette | Infobanjir: one request every few seconds at most, history archived once and cached, a clear User-Agent, JPS credited on every screen |
| Rate limits | data.gov.my Weather API: 4 requests/min without a token; we poll once per 15 min. *(Token request is optional.)* |
| Transparency | Every alert shows its data time, ranked reasons, which input fired and a time *window*; a footer says JPS/MET/NADMA remain the official source |
| Privacy (PDPA) | Residents: random device ID, push subscription, chosen streets, language, and per answer an optional location (stored rounded to ~100 m) and photo (EXIF removed). No names, phone numbers or home addresses; delete everything on unsubscribe; photos not shown publicly. Admins: accounts with roles; resident data visible only to logged-in SDP staff |
| Security | HTTPS everywhere (required for push and PWA); admin passwords hashed; API rate limits on answers and reports |
| Licensing | Open-Meteo free tier and FABDEM are non-commercial → fine for the hackathon; production needs a paid plan, MET data and GLO-30. Credit JPS, OpenStreetMap (ODbL), Copernicus and ESA on map screens |
| Reproducibility | All data pulls and model training run from scripts in the repo; raw files are versioned with a date stamp |
| Demo resilience | Replay runs fully offline from cached data; push tested on the demo phone at the venue; a backup video exists |
| Cost | MVP runs on a free-tier VM or always-on PC; sensor from low-cost hobby parts; exact bill of materials to be priced |

## Business case

Flood-Ready Township turns a known resident concern into a selling point and a planning tool: "the township that warns you street by street, learns from every flood, and fixes what floods."

**Why buyers choose SDP**

- 78% of Malaysians consider climate risk when buying, with flooding and landslides the key concerns ([PropertyGuru H1 2026](https://theiskandarian.com/propertyguru-sustainability-climate-risk-and-liveability-now-shape-how-malaysians-think-about-home/)).
- Official flood hazard maps still have limited public access in Malaysia ([EdgeProp](https://www.edgeprop.my/content/1916824/flood-risk-does-not-always-sink-property-values)), so a developer that monitors streets visibly stands out.
- Floods hurt resale: Taman Sri Muda prices fell 14.3% after the 2021 flood, against 6.1% in nearby non-flooded areas ([EdgeProp](https://www.edgeprop.my/content/1910792/)).

**Value to SDP**

| Value | How |
| --- | --- |
| Residents | Street-level warnings with time and reasons; a voice through verification |
| Trust | Answers the Bandar Bukit Raja memorandum with action and a monthly report SDP can share with the residents' council |
| Operations | Ops sees where to clear drains and deploy staff before an event |
| Planning | Suggestions backed by confirmed floods and rain-at-onset evidence prioritise drainage upgrades and retention ponds |
| Data | SDP builds its own street-level flood record over time |
| Sales | "Monitored 24/7" street card |
| Scale | One pipeline and two apps cover all SDP townships; each new township needs only its terrain run, its station list and optional sensors |

**Cost model (MVP → pilot)**

| Item | MVP | Pilot (1 township) |
| --- | --- | --- |
| Data | Free open data | Same + paid forecast API and licensed DEM if used commercially |
| Compute | Always-on PC / free-tier VM | Small cloud VM + database |
| Sensors | Simulated (MVP), then 1 hobby unit | A handful of industrial units at known hotspots |
| Alerts | Web Push (free) + Telegram fallback | Web Push, or embedded in the SDP App |

Exact pilot costs will be quoted with SDP during mentoring.

## Risks, assumptions and mitigations

The biggest risk is too few labelled flood events; every other risk has a cheaper fallback.

| Risk / assumption | Impact | Mitigation |
| --- | --- | --- |
| Few labelled events at street level | Weak model; metrics too coarse to mean much | District-level trigger trained on all Klang/Petaling/KL flash floods; station rules don't need labels; report "X of N"; ask SDP for incident logs; resident verification adds labels over time |
| Infobanjir endpoints are undocumented and may change or block | Live feed or history lost | Archive the full history now; staleness check; data.gov.my as fallback; credit JPS and scrape politely |
| No station history before 2024 | 2017, 2021 and 2023 events can't be used to train the trigger | They serve as map labels and news-quoted checks; the trigger trains on 2024+ events; the demo replays 12 Nov 2024. *(Optional: request older history from JPS.)* |
| Gridded rain misses short storms (confirmed: 12 Nov 2024 and 23 Apr 2025) | Outlook under-predicts; gridded data useless for the Nowcast | Nowcast, ML trigger and rules use station rain only; Outlook leans on MET warnings and is labelled medium confidence; gridded skill measured with our logged forecasts |
| Thunderstorm forecasts are uncertain | Outlook false alarms; wrong time windows | Outlook labelled medium confidence; windows, never exact times; Warning needs observed rain |
| Tide drives coastal Klang floods | Missed driver | Computed tide height is a Must input; SUG-2 tests it per street |
| DEM (30 m) misses drains and kerbs; Klang is very flat | Street score noise | FABDEM; HAND baseline; roll up per street; validate on held-out streets; never claim house-level accuracy |
| Push on iPhone needs the PWA installed (iOS 16.4+) | iPhone users miss alerts | Install prompt in onboarding; Telegram fallback (ALR-5); test on both platforms |
| Few residents answer, or answers are wrong or malicious | Weak or biased benchmark | Unanswered alerts count as unverified, not false; 2-device / photo rule; one answer per device; location weighting; review queue |
| Suggestions read as engineering advice | Liability; wrong investment | Labelled "screening suggestion; site survey needed"; evidence always shown; thresholds editable |
| Two frontends double UI work | Late or unpolished apps | One repo with a shared map/components package; build the Resident app first (it drives the demo), then the Admin app on the same components |
| News locations are vague and biased to main roads | Label noise; map learns "roads flood" | Geocode to street/taman only; dry samples drawn on roads too; every positive checked with an evidence quote |
| Alert fatigue | Residents ignore alerts | 60 min cooldown; two horizons; false-alarm rate measured continuously |
| Liability | Resident relies on us instead of the authorities | Footer: advisory only; JPS/MET/NADMA are official |
| Sensitive framing to the sponsor | Pitch reads as "SDP's township floods" | Frame as "SDP listened and acted"; score internal unless SDP chooses otherwise; share findings with SDP before publishing |
| JPS Infobanjir blocks GitHub runners (foreign IPs) | Live tick fails | Checked first (build plan D2); fallback: tick on a teammate's always-on PC; JPS history backfills gaps |
| Free tiers: Actions cron delay, API cold start, database limits | Late alerts, slow first load | Acceptable for the MVP; the demo uses replay; warm the API before recording; VPS after Top 10 |
| No hardware before Top 10 | Sensor can't be shown for real | Simulated sensor, labelled on screen; ESP32 during the mentoring sprint |
| Five people building in parallel in 9 days | Merge conflicts, integration surprises | Contracts frozen at M0, mocks for the frontends, small PRs, one owner per directory, CI on every PR |
| Pitch-day failure (Wi-Fi, push, sensor) | Demo breaks on stage | Offline replay, push tested at the venue, backup video |

## Build plan, milestones and team

Everything is due 23 Oct, so all five people build in parallel, ordered by dependency rather than by date: start any task as soon as what it needs is merged. Contracts, tasks with files and acceptance tests, git rules, the cut list and the submission checklist are in **`docs/plans/2026-10-14-mvp-build-plan.md`**.

| Milestone | Done when |
| --- | --- |
| **M0 Foundations** | Contracts as code (API, DB, engine types, rules config), monorepo + CI, design tokens, mocks; everyone is unblocked |
| **M1 Engine replay** | `scripts/replay.py --event 2024-11-12` prints Watch 08:45 → Warning 09:00 → Danger 10:00 for BBR from real JPS data |
| **M2 Vertical slice** | Resident app on a phone shows replay levels from the API, and the push arrives |
| **M3 Full MVP** | Verify / report, Admin statistics, report and suggestions on the 2024–2026 backfill, live tick, simulated sensor, BM/EN, deployed links |
| **M4 Ship** | Freeze ≥ 36 h before the deadline, bug bash on Android + iPhone, video + deck final, submitted ≥ 6 h early |

**Already done:** live loggers (JPS, MET, forecasts) running since 14 Oct; JPS history archive from Jan 2024; parsers with tests; public repo with git workflow; deployment units for the VPS phase.

| Person | Role | Owns |
| --- | --- | --- |
| Filbert | Backend + AI/ML, integration lead | Engine (features, rules, risk matrix, levels, alerts, Outlook, replay, backfill), GIS susceptibility, tide, flood labels + evaluation report, suggestions; approves contract changes |
| Michael | Backend | Database layer, FastAPI (public + admin + auth), Web Push, answers and outcomes, statistics and report endpoints, live tick, sensor endpoint + simulator |
| Darrell | Frontend + UI/UX | Design system and screens for both apps, Admin app lead, deck design, video edit |
| Christian | Frontend | Resident app: PWA, map, street page, push subscription, verify and report, BM/EN |
| Chingiz | DevOps + frontend | Monorepo, CI, branch protection, GitHub Actions tick, Supabase, hosting, secrets, shared map components, Admin statistics pages |

**After Top 10 (28 Oct → 11 Nov):** ESP32 sensor at a real drain, VPS + watchdog, district ML model, more townships, and the SDP mentors' input (incident logs, drain specs, which suggestions they find useful).

## Demo script and evaluation plan

The pitch replays a real Bandar Bukit Raja flood from JPS's own 15-minute readings, on an event the model never trained on. The phone buzzes before the water rises, residents confirm it, and SDP sees what to fix.

**5-minute video (23 Oct submission; the 14 Nov Top 10 pitch shows the same flow live)**

1. **(0:00–0:40) Problem:** the residents' memorandum on Jalan Makyong, and how SDP can answer it with action.
2. **(0:40–1:30) Resident app tour + map:** pick a street; the BBR susceptibility baseline (built without any flood labels) and where the memorandum streets fall.
3. **(1:30–2:45) Replay 12 Nov 2024 in the Resident app:**
   - Kg Perepat rain climbs; Watch at about 08:45, then Warning at 09:00 (61.5 mm), near high tide. The street page shows the ML flood probability alongside the official thresholds (values from the final, out-of-sample model).
   - The phone on stage receives the push: "Flooding likely at Persiaran Sungai Keramat between 9:30 and 10:30: heavy rain at Kg Perepat, high tide." Tapping it opens the street page with the map, time window and reasons.
   - Sg Binjai reaches danger (4.21 m) at 10:00, about an hour after the alert.
4. **(2:45–3:15) Verify:** the simulated sensor rises (labelled "simulated") and a second phone taps "Yes, flooding (knee)"; the alert turns *confirmed*.
5. **(3:15–4:15) Admin app:** statistics, monthly report and suggestions from the 2024–2026 backfill (the engine run over archived JPS data with out-of-fold ML probabilities, outcomes matched to news reports), e.g. "Persiaran Sungai Keramat: check outfall backflow, floods coincide with high tide", with its evidence.
6. **(4:15–4:40) Live mode:** today's levels from the 15-minute tick.
7. **(4:40–5:00) Enabler + ask:** one pipeline and two apps for every SDP township; cost per township; buyer survey result; pilot ask.

**Pitch deck (≤ 10 main slides):**
1. Problem
2. Why current warnings fail
3. Solution
4. How it works
5. Evidence: 12 Nov 2024 replay
6. Evaluation
7. Admin value
8. Enabler and scale
9. Business case
10. Team and ask

Appendix: data sources, the gridded-vs-station rain finding, roadmap.

**Evaluation plan**

- Leave-one-event-out over all dated events; 12 Nov 2024 is always a test event and is used for the demo.
- Report detection as "X of N", median lead time on hour-precision events, false alarms per township per month from a continuous 6-month run, and map AUC / top-20% hit rate on held-out BBR streets.
- Show one failure honestly and what data would fix it.
- Explain the live benchmark: from launch, every alert is scored by residents, and the Admin app tracks confirmation rate, missed floods and lead time.
- Run a 30–50 person buyer survey ("Would a monitored street make you choose this home? How much more would you pay?") and 5–10 resident interviews in BBR, including whether they would answer "Is it flooding here?".

## Sources

- [SDP University Hackathon 2026 — official page and judging criteria](https://www.simedarbyproperty.com/universityhackathon)
- [Sinar Harian — Bandar Bukit Raja residents face flash floods three times a year (25 May 2024)](https://www.sinarharian.com.my/article/666626/edisi/selangor-kl/penduduk-bandar-bukit-raja-hadap-banjir-kilat-tiga-kali-setahun)
- [Sinar Harian / Bernama — Klang flood mitigation, 4 Jun 2023 event (6 Jun 2023)](https://www.sinarharian.com.my/article/262088/berita/semasa/rancangan-tebatan-banjir-di-klang-dilaksana-segera---nik-nazmi)
- [Utusan — Flash floods in Selangor, 12 Nov 2024 (13 Nov 2024)](https://www.utusan.com.my/berita/2024/11/hujan-lebat-luar-biasa-punca-banjir-kilat-di-selangor-semalam/)
- [RTM — Seven roads in Klang flooded incl. Persiaran Sungai Keramat (12 Nov 2024)](https://berita.rtm.gov.my/nasional/senarai-berita-nasional/senarai-artikel/banjir-kilat-tujuh-laluan-di-klang-dinaiki-air/)
- [JPS Public Infobanjir — live and historical station data](https://publicinfobanjir.water.gov.my/)
- [data.gov.my — Weather API](https://developer.data.gov.my/realtime-api/weather)
- [Open-Meteo — Historical Forecast API](https://open-meteo.com/en/docs/historical-forecast-api) · [Previous Runs API](https://open-meteo.com/en/docs/previous-runs-api) · [Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)
- [Kosmo — Bomba Selangor flash-flood hotspots](https://www.kosmo.com.my/?p=229246)
- [Bernama — Floods erode property value by 30%](https://bernama.com/en/news.php?id=2141696)
- [The Iskandarian — PropertyGuru H1 2026 study](https://theiskandarian.com/propertyguru-sustainability-climate-risk-and-liveability-now-shape-how-malaysians-think-about-home/)
- [EdgeProp — Flood risk and property values](https://www.edgeprop.my/content/1916824/flood-risk-does-not-always-sink-property-values)
- [EdgeProp — Taman Sri Muda price impact](https://www.edgeprop.my/content/1910792/)
- [ISPRS — ML flash-flood susceptibility, Tetouan](https://isprs-archives.copernicus.org/articles/XLVI-4-W3-2021/305/2022/)
