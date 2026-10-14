# ML trigger feasibility

14 Oct 2026 · Script: `notebooks/spikes/ml_trigger_feasibility.py` (exploration code)

## Question

Can machine learning on JPS station data tell, ahead of time, that the river serving Bandar Bukit Raja will flood, and does it beat the station rain rules?

## Setup

- **Target:** Sg. Binjai at Pekan Meru (graph ID `PEKANMERU`), thresholds normal 2.8 / alert 3.8 / **warning 4.0** / danger 4.2 m.
- **Labels come from the data itself:** "the river crosses 4.0 m within the next 2 h". No news labels are needed.
- **Data:** JPS Infobanjir 15-min history, 1 Apr 2024 → 14 Oct 2026, 88,987 quarter hours, water level 94% complete; rain from 10 Klang stations (82–96% complete, except Kg. Delek at 63%).
- **Features:** water-level lags and rises; rain sums (1–24 h) at the 10 stations (max, mean, Kg. Perepat); hour; month. **No tide yet.**
- **Model:** scikit-learn `HistGradientBoostingClassifier`/`Regressor`, default-ish settings, `class_weight="balanced"`.
- **Validation:** two time folds (before / after 1 Apr 2025), each predicted by a model trained only on the other fold. 12 Nov 2024 is out-of-sample.
- **Event scoring:** a crossing counts as detected if the method fired 15 min to 3 h before it. A false alarm is an alarm episode with no crossing in the next 3 h.

## Results

There is plenty of data: Sg. Binjai crossed warning **50 times** (danger 24 times) in 2.5 years. Across the 102 river stations in Selangor and KL, a single pooled model could learn from hundreds of events.

**Will Sg. Binjai cross 4.0 m within 2 h?** (50 crossings, out-of-sample)

| Method | Detected | Median lead | False alarms / month |
| --- | --- | --- | --- |
| Rule: Watch (≥ 31 mm in 1 h or ≥ 40 mm in 2–4 h at any station) | 23 / 50 | 60 min | 4.9 |
| Rule: Warning (> 60 mm in 1 h or ≥ 60 mm in 2–4 h) | 10 / 50 | 75 min | 1.3 |
| ML classifier, p ≥ 0.3 | 23 / 50 | **90 min** | 8.5 |
| ML classifier, p ≥ 0.5 | 18 / 50 | **90 min** | 4.6 |
| ML classifier, p ≥ 0.7 | 16 / 50 | **90 min** | 2.6 |

**Level forecast vs "the level stays the same"** (mean absolute error):

| Horizon | During rises ≥ 0.3 m | When at or above alert |
| --- | --- | --- |
| 1 h | 0.39 m vs 0.51 m | 0.030 m vs 0.050 m |
| 2 h | 0.45 m vs 0.55 m | 0.081 m vs 0.116 m |

**12 Nov 2024:** ML put the chance of a crossing within 2 h at 0.51 at 08:30, before the rain rule's first Watch (08:45). It then fell to 0.24 before rising to 0.62 at 09:15. The river crossed 4.0 m at 09:30.

## What this means

- **ML is feasible.** The data is rich, the labels are free, and out-of-sample it gives about 30 min more warning than the rain rules.
- **It doesn't yet beat the rules** on detection or false alarms, and its probability is jumpy within an event.
- **About half the crossings come without heavy rain at these 10 stations,** so neither method catches them. They are probably driven by tide or by rain upstream: the obvious next features.

## Decision (adopted in the build plan)

**ML-first trigger, with JPS rules as a safety floor.** The street level is the higher of the ML level and the rule level. ML may raise a level but never lowers an official threshold.

**ML drives the alerts only if it passes this gate** on held-out folds; otherwise it shows its probability and forecast, and the rules decide the alert level:
- (a) it detects at least as many crossings as the Watch rule with no more false alarms, **or**
- (b) it detects as many with ≥ 20 min more median lead and ≤ 1.2× the false alarms.

**Planned improvements, in order:**
1. One model pooled across all river stations, with level measured against each station's own thresholds.
2. Tide height and time to high water.
3. Rain within 10–25 km, including upstream stations.
4. Smoothing the probability (e.g. the max over the last 30 min).
5. Calibration.
