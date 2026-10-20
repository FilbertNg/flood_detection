# Hosting the apps: step by step

How to put Flood-Ready online for the phone test, the video and judging, from nothing to a working push notification on an Android phone. It follows the decisions in the [remaining-MVP plan](plans/2026-10-17-MVP2-remaining-mvp.md) (Cloudflare Pages Free + Tailscale Funnel). Daily start/stop after that is in [runbook.md](runbook.md).

Each step says who does it:

- **You:** needs your accounts, your browser, your phone or a password. Claude can't do it.
- **Ask Claude:** say the quoted sentence in Claude Code and it will do the step and report back.

## What you end up with

```text
Phone / judge's browser
   │  https://<resident>.pages.dev      https://<admin>.pages.dev        (static apps, Cloudflare Pages, always on)
   │            │                                │
   └────────────┴──── API calls ────────────────┘
                         │
                         ▼
   https://<laptop>.<tailnet>.ts.net   (Tailscale Funnel: public HTTPS, same URL every time)
                         │
                         ▼
   Laptop: API on 127.0.0.1:8000 + loggers + data/floodready.db + .env
```

- **Cloudflare Pages** hosts only the two apps (HTML/JS). They load even when the laptop is off, but show no data then.
- **The laptop** runs the API, the 15-minute engine tick, the loggers and the database. It must be on and awake for the phone test, recording and judging (see [runbook.md](runbook.md)).
- **Tailscale Funnel** gives the laptop's API a public HTTPS address that stays the same across restarts, so the apps never need rebuilding when the laptop restarts.

## Before you start

- Backfill loaded into `data/floodready.db` (HANDOFF §5), so the Admin statistics are not empty. *Ask Claude:* "Is the backfill loaded?"
- An **Android phone with Chrome** for the push test (iPhone push works only from an installed PWA and is harder to show).
- About 1 hour the first time.

## Step 1: Accounts (You, once)

1. **Cloudflare:** sign up at <https://dash.cloudflare.com/sign-up> (free plan). No credit card is needed for Pages.
2. **Tailscale:** sign up at <https://login.tailscale.com/start> (free Personal plan). Signing in with the same Google or GitHub account you use for GitHub is easiest.

## Step 2: Tailscale on the laptop (You, once)

1. Install Tailscale for Windows from <https://tailscale.com/download/windows> and sign in from the tray icon. The laptop now has a name like `filbert-laptop` in your "tailnet" (your private Tailscale network, named like `tail1234.ts.net`).
2. In the Tailscale admin console, open **DNS** (<https://login.tailscale.com/admin/dns>):
   - check that **MagicDNS** is on;
   - turn on **HTTPS Certificates**;
   - turn on **Funnel**. (If the console instead shows a "Funnel" step under Access controls, accept the suggested policy change; it adds the `funnel` attribute for your devices.)
3. Open PowerShell and run (the first run may print a link asking you to approve Funnel; open it and approve, then run it again):

   ```powershell
   tailscale funnel --bg 8000
   ```

   It prints your public address, for example `https://filbert-laptop.tail1234.ts.net`. **Write it down: this is your API URL** for the rest of this guide. It forwards public HTTPS on port 443 to `127.0.0.1:8000` on the laptop and keeps running in the background; with `--bg` it resumes on its own after a reboot. Check it any time with `tailscale funnel status`; turn it off with `tailscale funnel reset`.

## Step 3: Secrets in `.env` (Ask Claude, once)

The API reads its secrets from a file called `.env` in the repo folder. It is in `.gitignore`, so it never goes to GitHub. Never paste its contents into chats, issues or the deck.

*Ask Claude:* **"Create the production .env for hosting. My API URL is `https://…ts.net` and my contact email for push is `…`."** Claude will:

- copy `.env.example` to `.env`;
- fill `JWT_SECRET`, `UPLOAD_URL_SECRET` and `SENSOR_TOKEN` with long random values;
- run `scripts/gen_vapid.py --subject mailto:<your email>` to fill the three `VAPID_*` lines;
- leave `FLOODREADY_DEV_LOGIN` unset (it must never be set on a reachable machine: it enables a published admin password).

What each value is for:

| Setting | What it is | Where it is used |
| --- | --- | --- |
| `JWT_SECRET` | The key that signs Admin login tokens (after you log in, the browser keeps a signed token instead of your password). Anyone who has it can forge an admin login. Must be random and at least 32 bytes (256 bits); shorter counts as unset. Generate one with `.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"`; never a word or password. | API only |
| `UPLOAD_URL_SECRET` | Signs the 1-hour links to residents' photos in the Admin review queue. | API only |
| `SENSOR_TOKEN` | Password the (simulated) water-level sensor sends with each reading (`scripts/sim_sensor.py`). | API and the sensor script |
| `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` | Web Push keys (see below). | API only |
| `CORS_ORIGINS` | Which websites may call the API from a browser: your two Pages addresses (Step 6). | API only |

### What a VAPID key is (and why it is not a Cloudflare thing)

Push notifications don't go straight from our laptop to the phone. The API hands each message to the **browser vendor's push service** (Google's for Chrome on Android, Apple's for Safari, Mozilla's for Firefox), and that service delivers it to the phone. VAPID ("Voluntary Application Server Identification") is how the push service knows the messages come from *our* server:

- **The private key** stays on the laptop in `.env`. The API signs every push with it.
- **The public key** is given to the phone when the resident taps "Allow notifications". The Resident app fetches it from the API (`GET /api/v1/push/public-key`) on its own, so you don't put it anywhere by hand, and it is not a Cloudflare setting.
- **The subject** is a `mailto:` contact address the push service can use if our server misbehaves. It stays in `.env` too.

Unlike `JWT_SECRET`, VAPID is not a secret you can make up: the public and private keys are a matched pair (elliptic curve P-256) that `gen_vapid.py` generates together; a random string won't work. Keep the same key pair for the whole event: if you regenerate it, every phone that already allowed notifications must subscribe again.

## Step 4: Admin account (You, once)

Create the real Admin login. You type the password yourself, so it never appears in Claude's chat or your shell history. Run:

```powershell
.venv\Scripts\python.exe scripts\seed_admin.py --email you@example.com --role admin
```

The script then stops at a `Password:` prompt. Type the password and press Enter. **Nothing appears while you type** (no dots or stars); that is normal. It answers `admin you@example.com saved in …`.

- **The email is only a username.** It must contain `@`; nothing is ever sent to it, so it doesn't have to be a real inbox. It is stored in lowercase in `data/floodready.db`, never in git.
- **The password:** there is no minimum, so pick a strong one yourself (12+ characters); at most 72 bytes (longer ones are refused, not cut). Only its bcrypt hash is stored.
- For a teammate who only needs to look, use `--role viewer` (viewers can't change anything). Run it again with the same email to change a password or role.

## Step 5: Cloudflare Pages: two projects (You, once)

Cloudflare builds the apps from GitHub on every push to `main`. Do this twice, once per app.

1. Cloudflare dashboard → **Workers & Pages** → **Create application** → select the **Pages** tab (not Workers; if only Workers shows, use the small "Looking to deploy Pages? **Get started**" link) → **Import an existing Git repository**. Authorise GitHub, pick `FilbertNg/flood_detection`, **Begin setup**.

   **Check you are in Pages:** the form has **Build command** and **Build output directory** and no **Deploy command**. If you see a "Deploy command" (`npx wrangler deploy`), you are creating a *Worker*: it builds, then fails with "application detection logic has been run in the root of a workspace". Delete that project (its **Settings** → **Delete**) and start again with the Pages tab.
2. **Production branch:** `main`.
3. **Build settings** (Framework preset: **None**):

   | Field | Resident app | Admin app |
   | --- | --- | --- |
   | Project name (becomes the address) | e.g. `floodready-bbr` → `floodready-bbr.pages.dev` | e.g. `floodready-admin` → `floodready-admin.pages.dev` |
   | Build command | `pnpm -C apps/resident build` | `pnpm -C apps/admin build` |
   | Build output directory | `apps/resident/dist` | `apps/admin/dist` |
   | Root directory | *(leave empty: the repo root, so the whole pnpm workspace installs)* | *(leave empty)* |

4. **Environment variables** (Production), the same for both projects:

   | Variable | Value |
   | --- | --- |
   | `VITE_API_URL` | your API URL from Step 2, e.g. `https://filbert-laptop.tail1234.ts.net` (no trailing slash, no `/api/v1`) |
   | `PNPM_VERSION` | `9.15.0` (the repo's pnpm; Pages would otherwise use pnpm 10) |
   | `NODE_VERSION` | `22` (Pages also reads `.nvmrc`; setting it is just explicit) |

5. **Save and Deploy.** The first build takes a few minutes. Pages installs the workspace with `pnpm install` because it finds `pnpm-lock.yaml`, then runs the build command. A red build: open its log and *Ask Claude:* "The Pages build failed; here is the log: …".
6. **Save build minutes (recommended):** in each project → **Settings** → **Builds & deployments** → **Preview deployments**: set to **None** (or only `main`). Otherwise every push to every PR branch builds both apps, and the free plan has 500 builds a month.

Notes:

- `VITE_API_URL` is baked into the app at build time. If the API URL ever changes (only with the Quick Tunnel fallback below), change the variable and **Retry deployment**.
- Page links like `/street/BBR-…` work on reload: Pages serves `index.html` for unknown paths when the build has no `404.html`, which is the case here.

## Step 6: Tell the API which sites may call it (Ask Claude, once)

*Ask Claude:* **"Set CORS_ORIGINS to `https://floodready-bbr.pages.dev,https://floodready-admin.pages.dev`."** (Use your real project addresses, exact scheme and no trailing slash.) Without this, the browser blocks the apps' calls to the API and the apps show no data.

## Step 7: Start everything (Ask Claude, every session)

*Ask Claude:* **"Start the loggers and the API for hosting."** This is what [runbook.md](runbook.md) describes:

```powershell
.venv\Scripts\python.exe -X utf8 scripts\run_loggers.py   # window 1: JPS / MET / Open-Meteo every 15 min
.venv\Scripts\python.exe -X utf8 scripts\serve_api.py     # window 2: API on 127.0.0.1:8000 (reads .env)
tailscale funnel status                                   # Funnel should show https://…ts.net → 127.0.0.1:8000
```

The API listens only on `127.0.0.1`; the public reaches it only through Funnel.

## Step 8: Check it works (Ask Claude, then You)

*Ask Claude:* **"Check the hosted setup."** Claude will check:

1. `https://<your API URL>/api/v1/status` returns JSON (Funnel → API works).
2. `https://<your API URL>/docs` returns 404 (dev mode is off, as it must be).
3. A CORS preflight from each Pages origin is allowed.
4. **Rate limits see real client IPs.** The answer and login limits count requests per IP. Behind Funnel the API must see the phone's IP, not `127.0.0.1`. If every request in the API log shows `127.0.0.1`, all users would share one limit (10 answers a minute for everyone); Claude then fixes the API to read the forwarded address. Do this check before judging.

Then **You**, on the laptop browser:

1. Open `https://floodready-bbr.pages.dev`: the map loads with street colours.
2. Open `https://floodready-admin.pages.dev`, log in with the Step 4 account: the ops map, Statistics (from the backfill) and Suggestions load.

## Step 9: Phone end-to-end test (You + Claude)

This is the WP14 acceptance test. Take a screenshot at each step for the PR and the video.

1. **You:** on the Android phone, open `https://floodready-bbr.pages.dev` in Chrome → menu → **Install app** (or **Add to Home screen**). Open it from the home screen.
2. **You:** pick a street that alerts in the 12 Nov 2024 replay (*Ask Claude:* "Which streets reach Warning early in the 12 Nov replay?") and tap **Allow notifications**.
3. **Ask Claude:** "Start the 12 Nov 2024 replay at speed 120." **Warning:** every replay sends `[Replay]` push messages to *every* real subscriber, so tell teammates first.
4. **You:** a push arrives on the phone; tapping it opens that street's page.
5. **You:** on the street page tap **Is it flooding here?** → answer (Yes, a depth, optionally a photo).
6. **You:** in the Admin app (laptop) → **Review**: your answer is there; the photo opens.
7. **Ask Claude:** "Stop the replay." Then record the checklist and screenshots in the WP14 PR.

## Every session after this

- **Before the demo or judging:** laptop on AC, sleep disabled (runbook), then *Ask Claude:* "Start the loggers and the API for hosting" and "Check the hosted setup".
- **No rebuilds needed:** the Funnel address stays the same, and Pages redeploys on its own when code is merged to `main`.
- **When done:** stop the API and loggers (Ctrl+C or *Ask Claude:* "Stop everything"). The apps stay online but show no data until the laptop is back.

## Fallback: Cloudflare Quick Tunnel (if Funnel won't work)

No account needed, but **the address changes every time** it starts:

```powershell
winget install --id Cloudflare.cloudflared
cloudflared tunnel --url http://127.0.0.1:8000
```

It prints `https://<random-words>.trycloudflare.com`. Then:

1. Put that address in both Pages projects' `VITE_API_URL` and **Retry deployment** (about 3 minutes).
2. Phones must re-open the app (and subscribe again only if they reinstalled).
3. Quick Tunnels are for testing: no uptime guarantee. Use Funnel for judging if at all possible.

## Security checklist before sharing links

- [ ] `FLOODREADY_DEV_LOGIN` is not set anywhere; `/docs` answers 404 through Funnel.
- [ ] `JWT_SECRET` is long and random (32+ bytes); the Admin login is the Step 4 account, not a published demo password.
- [ ] `.env` is not in git (`git status` never lists it).
- [ ] Only the API port 8000 is funneled (`tailscale funnel status`; `tailscale funnel reset` turns all of it off).
- [ ] Teammates know a replay pushes `[Replay]` alerts to every subscriber.

## Troubleshooting

| Symptom | Likely cause | Fix |
| --- | --- | --- |
| Apps load but show no map data | API not running, Funnel off, or `CORS_ORIGINS` missing the Pages address | Step 7 and Step 6; browser dev tools → Console shows "CORS" errors |
| `…ts.net` doesn't open | Funnel not enabled or approved | Step 2.2–2.3; `tailscale funnel status` |
| Pages build fails at install | pnpm version | `PNPM_VERSION=9.15.0` in the project's variables |
| Deploy fails: "application detection logic has been run in the root of a workspace" | The project was created as a Worker, not Pages | Step 5.1: delete it and create it from the **Pages** tab |
| "Allow notifications" does nothing | VAPID keys missing, or the page isn't the installed app | Step 3 (*Ask Claude* to check `/api/v1/push/public-key`); install the app first |
| Push never arrives | Phone battery saver, Chrome notifications blocked, or no alert on the chosen street | Android settings → Chrome → Notifications on; pick a street that alerts in the replay |
| Admin login says "admin login not configured" (503) | `JWT_SECRET` missing or too short, or no admin user | Step 3 and Step 4 |
| Too many requests (429) for everyone | Rate limit sees the proxy, not the phone | Step 8 check 4: *Ask Claude* to fix |
| Statistics are empty | Backfill not loaded | HANDOFF §5 |
