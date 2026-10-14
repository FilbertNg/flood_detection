# Deployment

Where each part runs, and how the loggers keep running.

| Part | Runs on | Why |
| --- | --- | --- |
| Loggers, history archive, FastAPI, PostgreSQL, MQTT broker, models | **VPS** (Ubuntu, 1 vCPU / 1–2 GB is enough) | Python with pandas/pyarrow, local files and long-running jobs. A Cloudflare Worker has no local disk, so the loggers would need rewriting for R2/D1 |
| Resident app and Admin app (React + Leaflet) | **Cloudflare Pages** (or the VPS behind nginx) | Static builds, free HTTPS (required for PWA and Web Push) |
| Watchdog *(to do)* | **Cloudflare Worker** with a Cron Trigger every 15 min | Runs outside the VPS, so it can alert the team when the VPS or the loggers stop |

## Keeping the loggers running (systemd)

- `floodready-loggers.service`: `Restart=always`, starts at boot, never stops retrying.
- `floodready-archive.timer`: runs the history archive nightly at 03:30 MYT. That tops up the current month, retries failed chunks, and **backfills any gaps in the JPS live log** (the Infobanjir history has the same 15-min readings). MET warnings and forecasts can't be backfilled, so the loggers service matters most.

```bash
# on the VPS, as root
adduser --system --group floodready
git clone https://github.com/FilbertNg/flood_detection.git /opt/floodready
cd /opt/floodready
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv .venv && uv pip install --python .venv/bin/python -e .
chown -R floodready:floodready /opt/floodready

cp deploy/systemd/floodready-*.service deploy/systemd/floodready-*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now floodready-loggers.service floodready-archive.timer

# check
systemctl status floodready-loggers
journalctl -u floodready-loggers -f
cat /opt/floodready/data/raw/jps_live/_status.json
```

To move data collected on a laptop, copy `data/raw/` to `/opt/floodready/data/raw/` before starting. Files are per day and de-duplicated, so overlapping copies are safe.

## Still to do

- [ ] **Watchdog:** a Cloudflare Worker cron (every 15 min) that calls the API's `/health` (age of the last `_status.json`) and sends a Telegram message to the team if it is older than 30 min or `ok` is false.
- [ ] **Backups:** nightly sync of `data/raw/` to object storage (e.g. Cloudflare R2 with rclone).
- [ ] **Updates:** `git pull && systemctl restart floodready-loggers` after merging to `main`.
