#!/usr/bin/env bash
# plants.sh - a gate that has never failed proves nothing. Every plant
# scripts/plant.py knows, on every committed copy of a real run, each through
# tests/e2e/run.sh as CI runs one: the run passes only if the gate catches
# the plant, and for that plant's own reason.
#
#   JOBS=4      how many at once
#   CLOUD=aks   one cloud's runs only
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT" || exit 1
LOGS="$ROOT/.cache/plants"
rm -rf "$LOGS" && mkdir -p "$LOGS"
# Once, before anything runs side by side: each run then finds both verified.
bash scripts/flagship.sh >/dev/null || exit 1
bash scripts/catalogs.sh >/dev/null || exit 1

one() {
  local dir="$1" plant="$2" log
  log="$LOGS/$(basename "$dir")-${plant//:/-}.log"
  if RUN_DIR="$dir" PLANT="$plant" bash tests/e2e/run.sh >"$log" 2>&1; then
    echo "caught  $(basename "$dir") $plant: $(grep -E '^== plant ' "$log" | sed -E 's/^== plant [^ ]+ caught: //')"
  else
    echo "MISSED  $(basename "$dir") $plant: $(tail -n 2 "$log" | tr '\n' ' ')"
  fi
}
export -f one
export LOGS

list="$(mktemp)"
for dir in tests/fixtures/runs/*/; do
  cloud="$(basename "$dir")"; cloud="${cloud%%-*}"
  [ -n "${CLOUD:-}" ] && [ "$cloud" != "$CLOUD" ] && continue
  python3 scripts/plant.py all "$cloud" | while read -r plant; do printf '%s\t%s\n' "${dir%/}" "$plant"; done
done >"$list"
total="$(grep -c . "$list")"
out="$(mktemp)"
# shellcheck disable=SC2016
tr '\t' '\n' <"$list" | xargs -n 2 -P "${JOBS:-4}" bash -c 'one "$0" "$1"' >"$out"
sort "$out"
missed="$(grep -c '^MISSED' "$out")"
ran="$(grep -c . "$out")"
rm -f "$list" "$out"
echo "== $((ran - missed)) of $total plants caught, each for its own reason, on $(find tests/fixtures/runs -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ') committed runs"
[ "$missed" -eq 0 ] && [ "$ran" -eq "$total" ] && [ "$total" -gt 0 ]
