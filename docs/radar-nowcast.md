# Radar nowcast (improvement #16, WP8)

**Status:** prototype, informational only, **logger off by default**. Research date: 16 Oct 2026.

Rain-gauge signals cannot warn before it rains locally (12 Nov 2024, Pekan Meru: the river rose 1.12 m in 90 min after rain began). Radar sees cells approaching. This work package checks whether we can get Klang Valley radar automatically and, if so, turns it into one optional message: "rain cell 30 km to the E, heading this way, ETA ~45 min".

**The radar signal never changes an alert level.** There is no radar history to evaluate it against (see [Evaluation](#how-to-evaluate-it-later)). It is shown as a Reason with code `radar_approaching` and unit `min`, after the real reasons.

## Verdict

Technically feasible; **legally blocked until MET Malaysia gives written consent.** The code, tests and API hook are done and the logger is switched off (`radar.enabled: false` in `config/sources.yaml`). Recommended next step: the team (via SDP / the hackathon organisers) asks MET Malaysia for written permission to poll the composite image for research and for showing a derived "rain approaching" message. If the answer is no or late, nothing else in the product depends on it.

## Sources checked

| Source | What it gives | Update | Klang covered | History | Terms and automation | Verdict |
| --- | --- | --- | --- | --- | --- | --- |
| **MET Malaysia radar page** `met.gov.my/en/pencerapan/radar-semenanjung/`, image `https://www.met.gov.my/data/radar_peninsular.gif` | One GIF, 826x640: Peninsular composite (CAPPI, "COMP_PM", 2 km product, 518 km range, azimuthal equidistant), legend printed in **mm/h** (17 colours, 0.05 to >400), peak dBZ and a timestamp in the header. Not animated; no bounds published. | Image stamped 15:10 MYT was served with `Last-Modified` 15:21 MYT (about 11 min lag). I saw the same frame for 11+ minutes, so the cadence is **unverified**; MET does not state it. ETag and 304 are supported. | Yes: Klang is about 70 px from the image centre (KL polygon at x 289, y 363 px) | None. Only the current frame; we must archive it ourselves | Copyright notice (`/en/info/kenyataan-hak-cipta`): no part of the portal may be "copied, distributed, retransmitted, ... displayed, reproduced, published ... without the express prior written consent of the MET Malaysia". No robots.txt (404), no API terms for the image. Windy staff report this public web image is the only radar source MET provides to them, and users report frequent outages | **Best data, needs consent.** Chosen as the source |
| **MET Malaysia API** `api.met.gov.my/v2.1/data` | Forecasts, warnings, observations. No radar | | | | Needs a token (`401`, `WWW-Authenticate: METToken`) | Not a radar source (our warnings logger already uses the public warning feed) |
| **RainViewer** `api.rainviewer.com/public/weather-maps.json`, tiles `tilecache.rainviewer.com{path}/256/{z}/{x}/{y}/{color}/{smooth}_{snow}.png` | Web-Mercator tiles, **max zoom 7 (about 1.2 km per pixel)**, 13 past frames at 10 min steps (2 h), `nowcast` list empty on the free API | 10 min | Yes: echoes at 3.1 N, 101.5 E (z6 tile fetched) | 2 h | Free for "personal and educational" use only; availability not guaranteed; attribution link required; the data owners can ask for removal. Automation through the documented JSON is the intended use | **Fallback only.** Fetchable without consent issues of its own, but the colour scheme is not usable for rain rate: the docs name only scheme 2 "Universal Blue" and publish no dBZ table (the page's table is empty), and requesting scheme 0 returned the identical image. A rate from colours would be invented, so no mm/h from it. Also a repackaging of agency data (probably MET's), so it inherits MET's licence |
| Windy, Open-Meteo, others | Windy shows MET's image; Open-Meteo has model rain only (already used as a forecast logger); satellite rain products (GPM IMERG) arrive hours late | | | | | Not useful as a nowcast input |

## Method (`floodready/radar.py`)

1. **Fetch.** One conditional GET (`If-None-Match`) every 5 min (`radar.interval_min`), so most polls are a tiny 304. Frames are saved untouched as `data/raw/radar/YYYY-MM-DD/HHMM.gif` (gitignored; HHMM is `Last-Modified` in MYT). The image is checked for the composite layout (legend swatches) before saving, so a layout change is reported instead of silently misread. Run it with `python scripts/run_loggers.py --radar` (own process, to catch every 10 min frame) or as part of `--once`/the normal loop when `radar.enabled` is true.
2. **Colour to rain rate.** The legend is read straight from the image: 17 colours, each a bin; a pixel gets the **lower bound of its bin** (conservative). No Z-R conversion is needed because MET publishes mm/h. (If we ever use a dBZ source: Marshall-Palmer Z = 200 R^1.6.) Pixels near no legend colour (land, sea, borders, text) are "no echo".
3. **Georeference.** MET publishes no bounds, so the projection was **fitted**: a spherical azimuthal equidistant projection, centre pixel (284.5, 319.5) = 3.8403 N 101.6072 E, 1.8093 km per pixel. Fitted by matching the image's land/sea mask against Natural Earth 10 m land (3.6 % of land/sea pixels disagree; all fits from several starting points converge to the same scale). Check against a landmark that was not used: the Kuala Lumpur boundary polygon (black outline) projects to x 289.4, y 362.6 and appears at x 285-292, y 356-378, i.e. within about 2 px (about 4 km). Position error of a few km is small against the 10-50 km rings used here.
4. **Township numbers.** Max and areal-mean rate within 10, 25 and 50 km of the township centre (`township_stats`).
5. **Motion.** Phase correlation (numpy FFT, Hann window, square-root compressed rates, sub-pixel peak) on a 128x128 px window (about 230 km) around the township between the two newest frames. It is trusted only if the correlation peak is at least 0.15, both windows hold at least 30 echo pixels and the speed is under 120 km/h.
6. **Message.** Rain cells = connected echoes of at least 5 mm/h and 4 pixels within 80 km. A cell qualifies only if the motion carries it toward the township at least 8 km/h, its track passes within 12 km of the centre, it is not already overhead (< 3 km) and ETA is at most 90 min. The earliest ETA wins, otherwise **nothing is said**. `latest_reason()` reads the two newest archived frames and returns nothing if the newest is older than 25 min or the pair is not 5-30 min apart.
7. **API.** `EngineContext.radar` is called for `GET /streets/{id}` in live mode only (never replay) and the Reason is appended to `reasons`. A radar failure is logged and ignored. Contract: new code `radar_approaching`, unit `min`, documented in `docs/api-contract.md` and the comment in `packages/shared/src/api/types.ts` (comment-only change; no field or shape changes).

## Tests

Frames from MET are Malaysian Government copyright, so **no real frame is committed**. `tests/test_radar.py` builds synthetic frames with the exact layout and legend colours (blobs placed by latitude/longitude) and checks georeferencing round trip and landmark, legend decoding including GIF palette quantisation, ring statistics, motion recovery (a cell moving 36 km/h gave 42 km/h; the pixel resolution at 10 min is about 11 km/h), the approach / receding / off-track / stationary cases, the Reason, the logger (archive once, 304 handling, junk image rejected) and the archive reader. `tests/api/test_radar_api.py` checks the Reason shows only in live mode and the level stays `normal`.

What was checked on one **real** frame (16 Oct 2026 15:10, kept outside the repo): the layout check passes, all 17 legend colours decode to exact bins, the BBR rings read max 10 / 50 / 50 mm/h at 10 / 25 / 50 km. **Real motion between two frames has not been tested**: MET still served the same frame 12+ min after publishing it during the research window, so only one real frame was available.

## Limits

- **Legal:** see the verdict; frames must not be redistributed or committed.
- **Single point of failure:** one static URL with reported outages and an undocumented cadence. A stale frame silences the message (25 min limit).
- **Resolution:** 1.8 km pixels, composite maximum value across radars, uncorrected for beam height or attenuation; it is rain aloft, not rain at the gauge. Rates are lower bounds of coarse bins, and one isolated pixel can read very high (a lone 400 mm/h pixel exists in the sample), so use ring maxima as a hint only.
- **Motion:** one rigid shift for the whole window; storms that grow, decay, split or sit still are not handled. Frames are 10+ min apart and speed resolution is about 11 km/h. Convective initiation directly over Klang (no cell upwind yet) cannot be seen. Sea breeze storms in the Klang Valley often form locally, so expect many misses.
- **Time:** frame time is `Last-Modified` (about 11 min after the image time) and is only used for the spacing of two frames.
- **No skill numbers.** This is not validated; do not quote a hit rate.

## How to evaluate it later

Needs at least one full monsoon season of archived frames (about 4,300 frames per month at 10 min) plus the JPS rain gauges we already log.

1. **Calibrate:** at each gauge pixel compare radar rate with the gauge's 15 min rain (bias, correlation, lower-bound effect).
2. **Warning skill:** for every frame pair, record whether `radar_approaching` fired for each township and whether a gauge in that township reached 10 / 31 mm/h-equivalent within the next 90 min. Report hit rate, false alarm ratio and lead time against a persistence baseline ("it is raining 25 km away") and against the JPS rule baseline, with time-blocked splits.
3. **Floods:** check the memorandum events (for example 12 Nov 2024 style events) for how many minutes before the first gauge trigger radar would have spoken.
4. **Decide:** only if lead time and false alarms are acceptable, replace "informational" with a rule that can **raise** a level (never lower an official threshold, per the project rule).

## How it could enter the ML later

Compute per 15 min step, using only frames at or before t: `radar_max_10/25/50`, `radar_mean_10/25/50`, `radar_eta_min` (or NaN), `radar_speed_kmh`. Needs the archive to cover the training period, so these features can only be trained after a season of collection; backfilling past years is impossible (no history source), which is the main cost of waiting. Evaluate with time-blocked out-of-fold folds against the JPS rule baseline exactly as for the current model, and keep "ML may raise, never lower".
