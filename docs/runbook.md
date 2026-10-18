# Runbook: starting Flood-Ready on the laptop

How to bring everything back after the laptop was off or asleep, run the demo, and shut down. Windows PowerShell, from the repo root (`C:\Main Storage\Hackathon\sime-daby-hackathon`). One-time setup (venv, `pnpm install`, data folder) is in [HANDOFF.md §2 and §5](../HANDOFF.md).

## What runs where

| Process | What it does | Needed for |
| --- | --- | --- |
| Live loggers (`scripts/run_loggers.py`) | Every 15 min: JPS river/rain tables, MET warnings, Open-Meteo forecast; tide table once a day | Live mode, fresh data |
| API (`scripts/serve_api.py`, port 8000) | Engine (live every 15 min + replay), all `/api/v1` endpoints | Both apps |
| Resident app (port 5173) | Resident web app (dev server) | Demo |
| Admin app (port 5174) | Admin web app (dev server), once `apps/admin` is merged | Demo |

When the laptop is off nothing is collected. JPS readings you missed can be refilled from JPS history (step 2); MET warnings and forecasts for those hours cannot.

## 1. Start (about 2 minutes)

Open **four PowerShell windows** in the repo root, one command each, and leave them open:

```powershell
# Window 1: live loggers (fetches once immediately, then every 15 min)
.venv\Scripts\python.exe -X utf8 scripts\run_loggers.py

# Window 2: API → http://localhost:8000/docs
.venv\Scripts\python.exe -X utf8 scripts\serve_api.py

# Window 3: Resident app → http://localhost:5173
npx pnpm@9.15.0 dev:resident

# Window 4: Admin app → http://localhost:5174 (after the Admin app PR is merged)
npx pnpm@9.15.0 dev:admin
```

Prefer one window? This starts the first three in the background and writes logs to `logs\`:

```powershell
$env:PYTHONUNBUFFERED = "1"
Start-Process .venv\Scripts\python.exe -ArgumentList "-u","-X","utf8","scripts\run_loggers.py" -RedirectStandardOutput logs\loggers.stdout.log -RedirectStandardError logs\loggers.err -WindowStyle Hidden
Start-Process .venv\Scripts\python.exe -ArgumentList "-u","-X","utf8","scripts\serve_api.py" -RedirectStandardOutput logs\api.log -RedirectStandardError logs\api.err -WindowStyle Hidden
Start-Process cmd.exe -ArgumentList "/c","npx pnpm@9.15.0 dev:resident > logs\resident.log 2>&1" -WindowStyle Hidden
```

## 2. Refill the JPS gap (optional)

Only if the laptop was off for a while and you want the live period complete (statistics, charts). The archive is cached in monthly chunks; a chunk that ended before today is re-downloaded (the current month on a new day, and last month's chunk if the gap crosses a month boundary), the rest comes from the cache. Requests are polite (≥ 3 s apart), so expect roughly 3 s per station-month fetched (about 310 series): tens of minutes, not hours:

```powershell
.venv\Scripts\python.exe -X utf8 scripts\archive_jps_history.py
```

Restart the API afterwards (Ctrl+C in window 2, run it again) so it reads the refreshed archive.

## 3. Check it works

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/status          # mode "live", data_time within the last ~30 min
Get-Content logs\loggers.log -Tail 3                           # "jps_live ... 'ok': True" (the loggers always write this file)
```

Then open http://localhost:5173 and check the map shows coloured streets.

## 4. Demo: replay the real 12 Nov 2024 flood

```powershell
.venv\Scripts\python.exe scripts\demo_replay.py --event 2024-11-12 --speed 120                 # play 06:00 → 14:00, 2 replay-minutes per second
.venv\Scripts\python.exe scripts\demo_replay.py --event 2024-11-12 --speed 0 --stop-at 09:30   # jump straight to 09:30
.venv\Scripts\python.exe scripts\demo_replay.py --stop                                         # back to live
```

What to show: at 08:45 Watch from rain at Kg. Perepat; at 09:00 Warning; at 09:30 the river at Sg. Binjai passes its warning level; at 10:00 Danger. A memorandum street: http://localhost:5173/street/BBR-jalan-makyong-1-ku5

## 5. Phone and public link

Not set up yet: hosting (Cloudflare Pages for the apps, Tailscale Funnel for the API) comes with work package WP14 of [the remaining-MVP plan](plans/2026-10-17-MVP2-remaining-mvp.md), and its steps will be added here. Until then the apps run on this laptop only.

## 6. Stop

Ctrl+C in each window. For background processes:

```powershell
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -match "run_loggers|serve_api" } | ForEach-Object { Stop-Process -Id $_.ProcessId }
Get-NetTCPConnection -State Listen -LocalPort 5173,5174 -ErrorAction SilentlyContinue | ForEach-Object { Stop-Process -Id $_.OwningProcess }
```

## Troubleshooting

| Problem | Fix |
| --- | --- |
| `address already in use` on 8000 / 5173 | An old copy is still running: run the Stop commands in §6, then start again |
| Map loads but streets are grey or empty | The API isn't running or is still starting (first start takes ~30 s); check §3 |
| `data_time` is hours old | Loggers aren't running or JPS was unreachable: check window 1 / `logs\loggers.log` |
| Streets show no river level | That station's gauge is stale or dead (QC blanks it); see `docs/findings.md` A3c |
| `ModuleNotFoundError` | Run from the repo root with `.venv\Scripts\python.exe`, not a global Python |
| Laptop went to sleep mid-demo | Everything stops; start again from §1. Settings → System → Power: set "sleep when plugged in" to Never before a demo |
