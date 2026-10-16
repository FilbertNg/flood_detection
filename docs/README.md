# Documents

Every plan and document lives in this folder. Status and next tasks are in [HANDOFF.md](../HANDOFF.md) at the repo root.

## Plans: what to build, and who builds it

| Document | What it is |
| --- | --- |
| [plans/2026-10-14-mvp-build-plan.md](plans/2026-10-14-mvp-build-plan.md) | **The build plan.** Task IDs (F, E, ML, B, R, A, D, P…), owners, dependencies, frozen contracts (§4), git rules (§9) |
| [plans/](plans/) | Also holds each person's step-by-step task plan. Save new plans here as `YYYY-MM-DD-<task-id>-<short-name>.md` |

## Product: what we build, and why

| Document | What it is |
| --- | --- |
| [product/prd.md](product/prd.md) | Product requirements (v3.1): users, requirements, demo script, timeline |
| [product/training-data-spec.md](product/training-data-spec.md) | Data sources, table schemas, scraping plan, data tasks T1–T17 |
| [product/plan-review.md](product/plan-review.md) | Review of v1 and why the plan changed |

## Technical reference: how it works, and how well

| Document | What it is |
| --- | --- |
| [api-contract.md](api-contract.md) | API contract between backend and frontend (frozen; changes need a `contract` PR) |
| [evaluation-report.md](evaluation-report.md) | ML vs rule-floor results and the gate verdict (rewritten by `scripts/train_trigger.py`) |
| [ml-feasibility.md](ml-feasibility.md) | First ML spike: why we use JPS station data and how the gate is defined |
| [radar-nowcast.md](radar-nowcast.md) | Radar nowcast (improvement #16): source research and verdict, terms, method, limits, how to evaluate it |
| [findings.md](findings.md) | **Facts for the pitch:** what the data says about flood prediction, each with its evidence (running log) |
| [terrain-v2.md](terrain-v2.md) | Street susceptibility v2: FABDEM + waterway distance, slope, built-up share; evaluation and licences |
| [ml-data-eda.md](ml-data-eda.md) | ML features and why, data shape, EDA, data-quality defects, experiments and recommended improvements |

## Archive

[archive/](archive/) holds superseded v1 versions of the PRD and the data spec, kept for reference only.
