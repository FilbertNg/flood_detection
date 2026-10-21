# Deployment

Since 21 Oct 2026 the backend runs on a Hetzner VPS. The two web apps stay on Cloudflare Pages ([docs/hosting.md](../docs/hosting.md)).

| Part | Where |
| --- | --- |
| Resident and Admin apps | Cloudflare Pages, `VITE_API_URL=https://floodready-api.tail36f260.ts.net` |
| API, live loggers, nightly JPS top-up, database | Hetzner CAX11 (2 Arm vCPU, 4 GB, Ubuntu 26.04), `/opt/floodready/app`, user `floodready` |
| Public HTTPS address | Tailscale Funnel on the VPS (node `floodready-api`) → `127.0.0.1:8000`. Only SSH is open in the firewall |

## Deploying a change

Merge to `main`. When CI passes, the **Deploy API** workflow (`.github/workflows/deploy.yml`) sends that commit to the server, and [`vps/deploy.sh`](vps/deploy.sh) does the rest:

- swaps the code in place; `data/`, `.env`, `.venv` and `logs/` are never touched;
- reinstalls Python packages only when `pyproject.toml` changed;
- restarts the API and loggers only when backend files changed (`floodready/`, `scripts/`, `config/`, `models/`, `assets/`, `data/reference/`, `data/events/`, `pyproject.toml`). A frontend or docs change doesn't restart anything, so a running replay survives it;
- waits up to 3 minutes for the API to answer, and puts the previous version back if it doesn't. The workflow run then fails, so a red run in the Actions tab means the server is still on the old code.

A restart stops a running replay and takes the API offline for about 15 seconds.

To redeploy by hand: Actions tab → **Deploy API** → Run workflow. To see what is deployed: `ssh root@<host> cat /opt/floodready/app/DEPLOYED`.

The deploy key (GitHub secret `VPS_SSH_KEY`) can only run `/opt/floodready/bin/deploy.sh`: it is a forced command in `/opt/floodready/.ssh/authorized_keys`, without a shell, port forwarding or agent forwarding. The script itself is root-owned, so a deploy can't change it; to update `deploy.sh`, `healthcheck.sh`, `backup.sh` or the systemd units, copy them over by hand (below). The server has no GitHub credentials (the repo is private).

## What runs on the server

| Unit | What it does |
| --- | --- |
| `floodready-api.service` | API and engine, `Restart=always` |
| `floodready-loggers.service` | JPS, MET and Open-Meteo every 15 min, `Restart=always` |
| `floodready-archive.timer` | 03:30 MYT: JPS history top-up (fills any gap in the live log), then restarts the API |
| `floodready-healthcheck.timer` | Every 5 min, [`vps/healthcheck.sh`](vps/healthcheck.sh): restarts the API if it stops answering for 10 min, restarts the loggers if the last good JPS fetch is over 40 min old (at most every 30 min), warns above 90% disk |
| `floodready-backup.timer` | 04:30 MYT: copy of `data/floodready.db` to `/opt/floodready/backups/`, last 7 kept |

Also on the server:
- the clock is set to Asia/Kuala_Lumpur, because the app reads local time as MYT;
- 2 GB of swap (the API uses about 1.1 GB);
- SSH is key-only, with fail2ban watching it;
- Ubuntu installs security updates automatically.

### Email alerts (optional)

`healthcheck.sh` can ping [Healthchecks.io](https://healthchecks.io) (free). Create a check with a 5-minute period and a 15-minute grace time, then put its ping URL on the server:

```bash
echo 'HC_URL=https://hc-ping.com/<uuid>' > /etc/floodready/healthcheck.env
```

Healthchecks.io then emails you when a check fails, or when the pings stop because the whole server is down.

## Everyday commands

Run these on the server as root (`ssh root@<host>`):

```bash
systemctl status floodready-api floodready-loggers       # running?
journalctl -u floodready-api -f                          # API log, live
journalctl -u floodready-healthcheck -n 20 -o cat        # recent health checks
cat /opt/floodready/app/data/raw/jps_live/_status.json   # last JPS fetch
systemctl restart floodready-api                         # restart by hand
tailscale funnel status                                  # public address
```

## Setting up a new server

These are the steps used on 21 Oct 2026. Run them from a laptop that has the repo, `data/` and `.env`.

1. Create the VPS with a public IPv4 address (Open-Meteo and github.com have no IPv6) and your SSH key.
2. As root, install the base tools and create the service user:
   ```bash
   apt-get install -y git curl sqlite3 ufw rsync fail2ban
   timedatectl set-timezone Asia/Kuala_Lumpur
   useradd --system --create-home --home-dir /opt/floodready --shell /bin/bash floodready
   su - floodready -c "curl -LsSf https://astral.sh/uv/install.sh | sh"
   ufw allow OpenSSH && ufw --force enable
   ```
3. From the laptop, copy the code, the data and `.env`:
   ```bash
   git archive origin/main | ssh root@<host> 'mkdir -p /opt/floodready/app && tar -x -C /opt/floodready/app'
   tar -cf - data/raw/jps_hist data/raw/jps_live data/raw/met_warnings data/raw/openmeteo_live data/raw/tide data/raw/osm \
       data/interim/stations.parquet data/interim/tide_hourly.parquet | ssh root@<host> 'tar -x -C /opt/floodready/app'
   scp .env root@<host>:/opt/floodready/app/.env
   ```
   For the database, copy a consistent snapshot rather than the live file: `sqlite3.connect(src).backup(dst)` in Python, then `scp`.
4. On the server, give everything to the service user (`chown -R floodready: /opt/floodready/app`, `chmod 600 .env`). Then create the venv with the laptop's package versions (`uv pip freeze` on the laptop → `/opt/floodready/constraints.txt`):
   ```bash
   su - floodready -c "cd app && ~/.local/bin/uv venv --python 3.12 .venv && \
     ~/.local/bin/uv pip install --python .venv/bin/python -c ../constraints.txt -e '.[ml,api,gis]'"
   ```
5. Install the scripts and units, then start everything:
   ```bash
   install -d -m 755 /opt/floodready/bin && install -m 755 deploy/vps/*.sh /opt/floodready/bin/
   install -m 644 deploy/vps/systemd/* /etc/systemd/system/ && systemctl daemon-reload
   systemctl enable --now floodready-loggers floodready-api floodready-archive.timer floodready-healthcheck.timer floodready-backup.timer
   echo "floodready ALL=(root) NOPASSWD: /usr/bin/systemctl restart floodready-api.service floodready-loggers.service" \
     > /etc/sudoers.d/floodready-deploy
   ```
6. Set up Tailscale and Funnel: `tailscale up --hostname=floodready-api`, open the login link in a private window and sign in with GitHub, then run `tailscale funnel --bg 8000`.
7. Set up the deploy key. Generate one (`ssh-keygen -t ed25519`) and add its public half to `/opt/floodready/.ssh/authorized_keys` as `command="/opt/floodready/bin/deploy.sh",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty ssh-ed25519 …`. Store the private half and `ssh-keyscan -t ed25519 <host>` as the GitHub secrets `VPS_SSH_KEY` and `VPS_KNOWN_HOSTS`, plus `VPS_HOST`. Then delete the local copy of the private key.

## Shutting down

Delete the server in the Hetzner console after judging; a powered-off server is still billed. Then point `VITE_API_URL` elsewhere, or take the apps offline.
