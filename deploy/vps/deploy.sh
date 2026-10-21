#!/usr/bin/env bash
# Deploy a new version of the code to the VPS. Installed as /opt/floodready/bin/deploy.sh (root-owned) and run as the
# forced command of the GitHub Actions deploy key, so that key can do nothing else:
#   git archive HEAD | ssh floodready@<host> "deploy <sha>"
# Reads the repo tarball on stdin, swaps the code in place (data, .env, .venv, logs untouched), reinstalls Python
# packages only when pyproject.toml changed, restarts the services only when backend files changed, and rolls back
# if the API does not answer within 3 minutes.
set -euo pipefail

APP=/opt/floodready/app
PREV=/opt/floodready/prev
UV=/opt/floodready/.local/bin/uv
CONSTRAINTS=/opt/floodready/constraints.txt
STATUS_URL=http://127.0.0.1:8000/api/v1/status
# Paths that exist only on the server; never overwritten or deleted by a deploy.
KEEP=(--exclude=/.venv/ --exclude=/.env --exclude=/logs/ --exclude=/DEPLOYED --exclude='/*.egg-info/' --exclude=__pycache__/
      --exclude=/data/raw/ --exclude=/data/interim/ --exclude=/data/final/ --exclude=/data/uploads/
      --exclude='/data/floodready.db*')
# A change here needs the API and loggers restarted; apps/, packages/, docs/ and *.md do not.
BACKEND=(floodready scripts config models assets data/reference data/events pyproject.toml)

read -r action sha rest <<<"${SSH_ORIGINAL_COMMAND:-}" || true
if [[ "${action:-}" == "status" ]]; then
  cat "$APP/DEPLOYED" 2>/dev/null || echo "no deploy yet"
  systemctl is-active floodready-api.service floodready-loggers.service
  exit 0
fi
if [[ "${action:-}" != "deploy" || ! "${sha:-}" =~ ^[0-9a-f]{7,40}$ || -n "${rest:-}" ]]; then
  echo "usage: deploy <sha> (repo tar on stdin) | status" >&2
  exit 2
fi

stage=$(mktemp -d /opt/floodready/stage.XXXXXX)
trap 'rm -rf "$stage"' EXIT
tar -x -C "$stage"
[[ -f "$stage/pyproject.toml" && -d "$stage/floodready" ]] || { echo "tarball is not the floodready repo" >&2; exit 1; }

restart() { sudo -n /usr/bin/systemctl restart floodready-api.service floodready-loggers.service; }
install_deps() { (cd "$APP" && "$UV" pip install -q --python .venv/bin/python -c "$CONSTRAINTS" -e ".[ml,api,gis]"); }
healthy() {
  for _ in $(seq 1 36); do
    sleep 5
    curl -fs -m 5 "$STATUS_URL" | grep -q '"mode"' && return 0
  done
  return 1
}

# Keep the running version for a rollback.
rsync -a --delete "${KEEP[@]}" "$APP/" "$PREV/"

backend_changed=0
for p in "${BACKEND[@]}"; do
  if ! diff -rq -x __pycache__ "$APP/$p" "$stage/$p" >/dev/null 2>&1; then backend_changed=1; break; fi
done
deps_changed=0
cmp -s "$APP/pyproject.toml" "$stage/pyproject.toml" || deps_changed=1

rsync -a --delete "${KEEP[@]}" "$stage/" "$APP/"
[[ $deps_changed == 1 ]] && install_deps

if [[ $backend_changed == 0 ]]; then
  echo "$sha $(date -Iseconds) (no backend change, services not restarted)" > "$APP/DEPLOYED"
  echo "deployed $sha: no backend change, services not restarted"
  exit 0
fi

restart
if healthy; then
  echo "$sha $(date -Iseconds)" > "$APP/DEPLOYED"
  echo "deployed $sha: services restarted, API healthy"
  exit 0
fi

echo "API did not answer after deploying $sha: rolling back" >&2
rsync -a --delete "${KEEP[@]}" "$PREV/" "$APP/"
[[ $deps_changed == 1 ]] && install_deps
restart
healthy && echo "rolled back to the previous version" >&2 || echo "rollback did not bring the API back either" >&2
exit 1
