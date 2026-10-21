#!/usr/bin/env bash
# Every 5 min (floodready-healthcheck.timer, as root). systemd already restarts a crashed process; this catches the
# cases it cannot see: an API that is running but not answering, and loggers that run but stopped getting data.
# Optional: put HC_URL=https://hc-ping.com/<uuid> in /etc/floodready/healthcheck.env to get an email from
# Healthchecks.io when a check fails or when the pings stop (the whole server down).
set -uo pipefail

APP=/opt/floodready/app
STATE=/run/floodready-healthcheck
HC_URL=${HC_URL:-}
mkdir -p "$STATE"
problems=()

# API: two failed checks in a row (10 min) → restart. One miss can be a slow start or a heavy request.
if curl -fsS -m 10 http://127.0.0.1:8000/api/v1/status | grep -q '"mode"'; then
  rm -f "$STATE/api_failed"
elif [[ -f "$STATE/api_failed" ]]; then
  problems+=("API not answering for 10 min: restarted")
  rm -f "$STATE/api_failed"
  systemctl restart floodready-api.service
else
  touch "$STATE/api_failed"
  problems+=("API not answering")
fi

# Loggers: the last JPS fetch must be under 40 min old (they run every 15 min) and succeed.
age_min=$(python3 - "$APP/data/raw/jps_live/_status.json" <<'EOF'
import json, sys
from datetime import datetime
try:
    s = json.load(open(sys.argv[1]))
    age = (datetime.now() - datetime.fromisoformat(s["run_at_local"])).total_seconds() / 60
    print(int(age) if s.get("ok") else 9999)
except Exception:
    print(9999)
EOF
)
if (( age_min > 40 )); then
  # A restart fetches at once, so restart at most every 30 min: if JPS itself is down, keep to its 15-min pace.
  if [[ -z $(find "$STATE/loggers_restarted" -mmin -30 2>/dev/null) ]]; then
    problems+=("last good JPS fetch ${age_min} min ago: loggers restarted")
    touch "$STATE/loggers_restarted"
    systemctl restart floodready-loggers.service
  else
    problems+=("last good JPS fetch ${age_min} min ago (JPS down or loggers stuck)")
  fi
fi

# Disk: warn above 90 % on /.
disk=$(df --output=pcent / | tail -1 | tr -dc 0-9)
(( disk > 90 )) && problems+=("disk ${disk}% full")

if (( ${#problems[@]} )); then
  msg=$(IFS='; '; echo "${problems[*]}")
  echo "UNHEALTHY: $msg"
  [[ -n "$HC_URL" ]] && curl -fsS -m 10 --retry 3 --data-raw "$msg" "$HC_URL/fail" >/dev/null
  exit 1
fi
echo "ok (JPS fetch ${age_min} min ago, disk ${disk}%)"
[[ -n "$HC_URL" ]] && curl -fsS -m 10 --retry 3 "$HC_URL" >/dev/null
exit 0
